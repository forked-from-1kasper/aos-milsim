from dataclasses import dataclass

from milsim.grammar.category import (
    GrammarError, Number, Person, Case,
    SG, PL, NOM, OBL, POS, INF, P3RD, PTCP1
)
from milsim.grammar.syntax import NP, VP
from milsim.grammar.noun import Noun

def ProperNoun(value, number = SG):
    def left(c : Case):
        yield from ()

    def right(c : Case):
        if c is NOM or c is OBL:
            yield value
        elif c is POS:
            yield value + "'s" if number is SG else "'"
        else:
            raise GrammarError

    return NP(left, right, number = number, person = P3RD)

@dataclass(repr = False)
class ZeroArticle:
    number : Number

    def __call__(self, noun : Noun):
        def left(c : Case):
            yield from ()

        def right(c : Case):
            yield noun.inflect(self.number, c)

        return NP(left, right, number = self.number, person = P3RD)

@dataclass(repr = False)
class Determiner:
    value  : str
    number : Number

    def __call__(self, noun : Noun):
        def left(c : Case):
            yield self.value

        def right(c : Case):
            yield noun.inflect(self.number, c)

        return NP(left, right, number = self.number, person = P3RD)

@dataclass(repr = False)
class Possessive:
    value  : NP
    number : Number

    def __call__(self, noun : Noun):
        def left(c : Case):
            yield from self.value.linearize(POS)

        def right(c : Case):
            yield noun.inflect(self.number, c)

        return NP(left, right, number = self.number, person = P3RD)

def cardinal(k : int) -> str:
    return str(k)

def indicator(k : int) -> str:
    if k < 0: raise GrammarError

    if 11 <= k % 100 <= 13:
        return "th"

    match k % 10:
        case 1: return "st"
        case 2: return "nd"
        case 3: return "rd"

    return "th"

def ordinal(k : int) -> str:
    return str(k) + indicator(k)

def Cardinal(k : int, noun : Noun):
    number = SG if k == 1 else PL

    def left(c : Case):
        yield cardinal(k)

    def right(c : Case):
        yield noun.inflect(number, c)

    return NP(left, right, number = number, person = P3RD)

def Ordinal(k : int, np : NP):
    def left(c : Case):
        yield from np.left(c)
        yield ordinal(k)

    def right(c : Case):
        yield from np.right(c)

    return NP(left, right, number = np.number, person = np.person)

def Pronoun(number : Number, person : Person, nom, obl, pos):
    def left(c : Case):
        yield from ()

    def right(c : Case):
        if c is NOM:
            yield nom
        elif c is OBL:
            yield obl
        elif c is POS:
            yield pos
        else:
            raise GrammarError

    return NP(left, right, number = number, person = person)

@dataclass(repr = False)
class Adjective:
    value : str

    def __call__(self, np : NP):
        def left(c : Case):
            yield from np.left(c)
            yield self.value

        def right(c : Case):
            yield from np.right(c)

        return NP(left, right, number = np.number, person = np.person)

def NotNP(np : NP):
    def left(c : Case):
        yield "not"
        yield from np.left(c)

    def right(c : Case):
        yield from np.right(c)

    return NP(left, right, number = np.number, person = np.person)

def InfinitivePhrase(vp : VP):
    def left(c : Case):
        yield "to"

    def right(c : Case):
        if c is NOM or c is OBL:
            yield from vp.linearize(INF)
        else:
            raise GrammarError

    return NP(left, right, number = SG, person = P3RD)

def Gerund(vp : VP):
    def left(c : Case):
        yield from ()

    def right(c : Case):
        if c is NOM or c is OBL:
            yield from vp.linearize(PTCP1)
        else:
            raise GrammarError

    return NP(left, right, number = SG, person = P3RD)
