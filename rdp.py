'''
parse fixrank files output by classifier.jar
'''

import csv, re, itertools, yaml

rank_abbreviations = ['k', 'p', 'c', 'o', 'f', 'g']
rank_abbr_map = {'k': 'domain', 'p': 'phylum', 'c': 'class', 'o': 'order', 'f': 'family', 'g': 'genus'}

class FixrankRank:
    taxon_table = str.maketrans(' ', '_', '"')  # change space to underscore; remove quotes

    def __init__(self, name, taxon, confidence):
        self.name = name
        self.taxon = taxon.translate(self.taxon_table)
        self.confidence = float(confidence)

    def __eq__(self, other):
        return all([self.name == other.name, self.taxon == other.taxon, self.confidence == other.confidence])

    def __repr__(self):
        return 'FixrankRank("{}", "{}", {})'.format(self.name, self.taxon, self.confidence)

    def __str__(self):
        return self.taxon


class FixrankLineage:
    def __init__(self, ranks, min_confidence=None):
        self.ranks = ranks

        # try to recast lists as ranks
        for i in range(len(self.ranks)):
            if type(self.ranks[i]) is list:
                self.ranks[i] = FixrankRank(*self.ranks[i])

        if min_confidence is not None:
            self.trim_at_confidence(min_confidence)

    def __repr__(self):
        return "FixrankLineage([" + ", ".join(['["{}", "{}", {}]'.format(rank.name, rank.taxon, rank.confidence) for rank in self.ranks]) + "])"

    def __str__(self):
        return ";".join([str(rank) for rank in self.ranks])

    def __eq__(self, other):
        '''lineages are equal if all their ranks are'''
        return len(self.ranks) == len(other.ranks) and all([x == y for x, y in zip(self.ranks, other.ranks)])

    def ranks_at_confidence(self, min_confidence):
        '''return my entries trimmed to a confidence'''
        return list(itertools.takewhile(lambda rank: rank.confidence >= min_confidence, self.ranks))

    def trim_at_confidence(self, min_confidence):
        '''trim my entries to a confidence'''
        self.min_confidence = min_confidence
        self.ranks = self.ranks_at_confidence(min_confidence)

    def ranks_to_rank(self, name):
        '''return ranks down to a certain level'''
        out = []

        for rank in self.ranks:
            out.append(rank)

            if rank.name == name:
                break

        return out

    def trim_at_rank(self, name):
        '''trim my entries to a rank'''
        self.ranks = self.ranks_to_rank(name)

    def lineage_at_rank(self, name):
        return FixrankLineage(self.ranks_to_rank(name))


class FixrankParser:
    @staticmethod
    def parse_triplet(triplet):
        '''parse a 3-mer list into a Rank object'''
        return FixrankRank(triplet[1], triplet[0], triplet[2])

    @staticmethod
    def parse_sid_entry(entry):
        '''remove annotations from a field'''
        return entry.split(';')[0]

    @classmethod
    def parse_entries(cls, entries):
        '''break up entries into sid entry and triplet'''
        # first entry is sequence id
        sid_entry = cls.parse_sid_entry(entries[0])

        # second entry should be blank
        assert entries[1] == ""

        # the rest of the entries should divide into triplets
        if (len(entries) - 2) % 3 != 0:
            raise RuntimeError("could not parse fixrank with fields {}".format(entries))
        
        entry_triplets = zip(*[iter(entries[2:])] * 3)
        ranks = [cls.parse_triplet(t) for t in entry_triplets]

        return sid_entry, FixrankLineage(ranks)

    @classmethod
    def parse_line(cls, line):
        '''parse a line into seq id and lineage'''
        entries = line.rstrip().split("\t")

        # if the second entry is a dash (rather than blank), RDP used the reverse complement
        # to do the classification, which is probably a bad sign, so throw out that seq
        if entries[1] == '':
            return cls.parse_entries(entries)
        elif entries[1] == '-':
            return None
        else:
            raise RuntimeError("don't recognize field 2 '{}' in fixrank line: '{}'".format(entries[1], line))

    @classmethod
    def parse_lines(cls, lines, min_confidence=None, rank=None):
        '''turn lines into a dictionary seq id => lineage string'''

        mapping = {}
        for line in lines:
            res = cls.parse_line(line.rstrip())

            # parse_line gives none if RDP used reverse complement
            if res is not None:
                sid, lineage = res

                if min_confidence is not None:
                    lineage.trim_at_confidence(min_confidence)

                if rank is not None:
                    lineage.trim_at_rank(rank)

                mapping[sid] = str(lineage)

        return mapping

    @classmethod
    def parse_lines_all_ranks(cls, lines, min_confidence=None):
        '''turn lines into {'k' => {seq id => lineage}, 'p' => ...}'''
        mappings = {abbr: {} for abbr in rank_abbreviations}
        for line in lines:
                res = cls.parse_line(line.rstrip())

                if res is not None:
                    sid, lineage = res

                    if min_confidence is not None:
                        lineage.trim_at_confidence(min_confidence)

                    for abbr in rank_abbreviations:
                        rank = rank_abbr_map[abbr]
                        trimmed_lin = lineage.lineage_at_rank(rank)
                        mappings[abbr][sid] = str(trimmed_lin)

        return mappings

    @classmethod
    def parse_file(cls, fixrank, level, output, min_conf):
        '''
        Parse a fixrank file and output the mapping yaml

        fixrank : read filehandle
        level : string, one of 'k', 'p', 'c', etc.
        output : write filehandle
        min_conf : float
        '''

        rank = rank_abbr_map[level]
        mapping = cls.parse_lines(fixrank, min_conf, rank=rank)
        yaml.dump(mapping, output, default_flow_style=False)

    @staticmethod
    def substituted_filehandles(output_base, repl):
        '''
        open handles to many files by replacing repl in output_base with
        one of the rank abbreviations
        '''

        return {a: open(re.sub(repl, a, output_base), 'w') for a in rank_abbreviations}

    @classmethod
    def parse_file_all_ranks(cls, fixrank, output_base, repl, min_conf):
        handles = cls.substituted_filehandles(output_base, repl)
        mappings = cls.parse_lines_all_ranks(fixrank, min_conf)

        for a in rank_abbreviations:
            yaml.dump(mappings[a], handles[a], default_flow_style=False)
