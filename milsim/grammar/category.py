class GrammarError(Exception):
    pass

class Category:
    ...

class Number(Category):
    pass

SG = Number()
PL = Number()

class Person(Category):
    pass

P1ST = Person()
P2ND = Person()
P3RD = Person()

class Case(Category):
    pass

NOM = Case()
OBL = Case()
POS = Case()

class Tense(Category):
    pass

PRES = Tense()
PAST = Tense()

class VerbForm(Category):
    pass

INF     = VerbForm()
PTCP1   = VerbForm()
PTCP2   = VerbForm()
PRES1SG = VerbForm()
PRES2SG = VerbForm()
PRES3SG = VerbForm()
PRES1PL = VerbForm()
PRES2PL = VerbForm()
PRES3PL = VerbForm()
PAST1SG = VerbForm()
PAST2SG = VerbForm()
PAST3SG = VerbForm()
PAST1PL = VerbForm()
PAST2PL = VerbForm()
PAST3PL = VerbForm()

def isfinite(vf : VerbForm) -> bool:
    return vf is not INF and vf is not PTCP1 and vf is not PTCP2

def fvf(n : Number, p : Person, t : Tense) -> VerbForm:
    if t is PRES:
        if n is SG:
            if p is P1ST: return PRES1SG
            if p is P2ND: return PRES2SG
            if p is P3RD: return PRES3SG
        if n is PL:
            if p is P1ST: return PRES1PL
            if p is P2ND: return PRES2PL
            if p is P3RD: return PRES3PL

    if t is PAST:
        if n is SG:
            if p is P1ST: return PAST1SG
            if p is P2ND: return PAST2SG
            if p is P3RD: return PAST3SG
        if n is PL:
            if p is P1ST: return PAST1PL
            if p is P2ND: return PAST2PL
            if p is P3RD: return PAST3PL

    raise GrammarError
