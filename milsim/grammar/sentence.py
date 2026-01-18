from dataclasses import dataclass

from milsim.grammar.category import Tense, fvf, NOM, INF
from milsim.grammar.syntax import NP, VP, Sentence

@dataclass(repr = False)
class Declarative(Sentence):
    np : NP
    vp : VP

    tense : Tense

    def linearize(self):
        yield from self.np.linearize(NOM)

        vf = fvf(self.np.number, self.np.person, self.tense)
        yield from self.vp.linearize(vf)

@dataclass(repr = False)
class YesNoInterrogative(Sentence):
    np : NP
    vp : VP

    tense : Tense

    def linearize(self):
        vf = fvf(self.np.number, self.np.person, self.tense)

        yield from self.vp.left(vf)
        yield from self.np.linearize(NOM)
        yield from self.vp.right(vf)

        yield "?"

@dataclass(repr = False)
class Imperative(Sentence):
    vp : VP

    def linearize(self):
        yield from self.vp.linearize(INF)

@dataclass(repr = False)
class Compound(Sentence):
    s1 : Sentence
    s2 : Sentence

    conjunct : str

    def linearize(self):
        yield from self.s1.linearize()

        yield ","
        yield self.conjunct

        yield from self.s2.linearize()
