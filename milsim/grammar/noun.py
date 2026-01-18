from dataclasses import dataclass
from typing import Optional

from milsim.grammar.category import GrammarError, Number, SG, PL, Case, NOM, OBL, POS

@dataclass
class Noun:
    nom_sg : Optional[str] = None
    pos_sg : Optional[str] = None
    nom_pl : Optional[str] = None
    pos_pl : Optional[str] = None

    def inflect(self, n : Number, c : Case):
        if n is SG:
            if self.nom_sg is not None and c is NOM or c is OBL:
                return self.nom_sg
            if self.pos_sg is not None and c is POS:
                return self.pos_sg

        if n is PL:
            if self.nom_pl is not None and c is NOM or c is OBL:
                return self.nom_pl
            if self.pos_pl is not None and c is POS:
                return self.pos_pl

        raise GrammarError

def possessify(w):
    if w is None:
        return

    if w[-1] == 's':
        return w + "'"
    else:
        return w + "'s"

class SemiregularNoun(Noun):
    def __init__(self, *, sg = None, pl = None):
        super().__init__(
            nom_sg = sg, pos_sg = possessify(sg),
            nom_pl = pl, pos_pl = possessify(pl)
        )

endswith = lambda val, *sfxs: any(val.endswith(sfx) for sfx in sfxs)

# https://github.com/GrammaticalFramework/gf-rgl/blob/master/src/english/ParadigmsEng.gf
def pluralize(w):
    if endswith(w, "io", "oo"):
        return w + "s"
    elif endswith(w, "s", "z", "x", "sh", "ch", "o"):
        return w + "es"
    elif endswith(w, "ay", "oy", "uy", "ey"):
        return w + "s"
    elif endswith(w, "y"):
        return w.removesuffix("y") + "ies"
    else:
        return w + "s"

class RegularNoun(SemiregularNoun):
    def __init__(self, sg):
        super().__init__(sg = sg, pl = pluralize(sg))
