'''
parse fixrank files output by classifier.jar
'''

import csv, re, itertools

class FixrankRank:
    def __init__(self, name, taxon, confidence):
        self.name = name
        self.taxon = re.sub('"', '', taxon)
        self.confidence = float(confidence)

    def __eq__(self, other):
        return all([self.name == other.name, self.taxon == other.taxon, self.confidence == other.confidence])

    def __repr__(self):
        return 'FixrankRank("{}", "{}", {})'.format(self.name, self.taxon, self.confidence)

    def __str__(self):
        return self.taxon


class FixrankLineage:
    standard_rank_names = ['domain', 'phylum', 'class', 'order', 'family', 'genus']

    def __init__(self, ranks, standardize=False, min_confidence=None):
        self.ranks = ranks

        # try to recast lists as ranks
        for i in range(len(self.ranks)):
            if type(self.ranks[i]) is list:
                self.ranks[i] = FixrankRank(*self.ranks[i])

        if standardize:
            self.standardize()

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

    def standardized_ranks(self):
        '''return ranks in standard level order, filling empties'''
        # make a dictionary like 'phylum' => FrRank['phylum', 'Chloroflexi', 0.8]
        mix_ranks = {rank.name: rank for rank in self.ranks}
        out = []

        for name in self.standard_rank_names:
            if name in mix_ranks:
                out.append(mix_ranks[name])
            else:
                out.append(FixrankRank(name, 'no_entry_{}'.format(name), 0.0))

        return out

    def standardize(self):
        '''make my ranks standard ranks'''
        self.ranks = self.standardized_ranks()

    def ranks_to_rank(self, name):
        '''return ranks down to a certain level'''
        out = []

        for rank in self.ranks:
            out.append(rank)

            if rank.name == name:
                break

        return out


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
        assert (len(entries) - 2) % 3 == 0
        entry_triplets = zip(*[iter(entries[2:])] * 3)
        ranks = [cls.parse_triplet(t) for t in entry_triplets]

        # the first entry should be root, whatever that is
        assert ranks[0] == FixrankRank('rootrank', 'Root', 1.0)

        return sid_entry, FixrankLineage(ranks[1:])

    @classmethod
    def parse_line(cls, line):
        '''parse a line into seq id and lineage'''
        entries = line.rstrip().split("\t")
        return cls.parse_entries(entries)

    @classmethod
    def parse_lines(cls, lines):
        for line in lines:
            pass