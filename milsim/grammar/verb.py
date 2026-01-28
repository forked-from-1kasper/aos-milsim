from dataclasses import dataclass
from typing import Optional

from milsim.grammar.category import (
    GrammarError, VerbForm,
    INF,     PTCP1,   PTCP2,
    PRES1SG, PRES2SG, PRES3SG,
    PRES1PL, PRES2PL, PRES3PL,
    PAST1SG, PAST2SG, PAST3SG,
    PAST1PL, PAST2PL, PAST3PL
)

from milsim.grammar.paradigms import esize, ingize, edize

@dataclass
class Verb:
    inf   : Optional[str] = None
    ving  : Optional[str] = None
    ved   : Optional[str] = None
    v1sg  : Optional[str] = None
    v2sg  : Optional[str] = None
    v3sg  : Optional[str] = None
    v1pl  : Optional[str] = None
    v2pl  : Optional[str] = None
    v3pl  : Optional[str] = None
    vp1sg : Optional[str] = None
    vp2sg : Optional[str] = None
    vp3sg : Optional[str] = None
    vp1pl : Optional[str] = None
    vp2pl : Optional[str] = None
    vp3pl : Optional[str] = None

    def decline(self, vf : VerbForm):
        if self.inf   is not None and vf is INF:     return self.inf
        if self.ving  is not None and vf is PTCP1:   return self.ving
        if self.ved   is not None and vf is PTCP2:   return self.ved
        if self.v1sg  is not None and vf is PRES1SG: return self.v1sg
        if self.v2sg  is not None and vf is PRES2SG: return self.v2sg
        if self.v3sg  is not None and vf is PRES3SG: return self.v3sg
        if self.v1pl  is not None and vf is PRES1PL: return self.v1pl
        if self.v2pl  is not None and vf is PRES2PL: return self.v2pl
        if self.v3pl  is not None and vf is PRES3PL: return self.v3pl
        if self.vp1sg is not None and vf is PAST1SG: return self.vp1sg
        if self.vp2sg is not None and vf is PAST2SG: return self.vp2sg
        if self.vp3sg is not None and vf is PAST3SG: return self.vp3sg
        if self.vp1pl is not None and vf is PAST1PL: return self.vp1pl
        if self.vp2pl is not None and vf is PAST2PL: return self.vp2pl
        if self.vp3pl is not None and vf is PAST3PL: return self.vp3pl

        raise GrammarError

    def finite(self):
        return Verb(
            v1sg  = self.v1sg,  v2sg  = self.v2sg,  v3sg  = self.v3sg,
            v1pl  = self.v1pl,  v2pl  = self.v2pl,  v3pl  = self.v3pl,
            vp1sg = self.vp1sg, vp2sg = self.vp2sg, vp3sg = self.vp3sg,
            vp1pl = self.vp1pl, vp2pl = self.vp2pl, vp3pl = self.vp3pl
        )

class ModalVerb(Verb):
    def __init__(self, *, vpres = None, vpast = None):
        super().__init__(
            v1sg  = vpres, v2sg  = vpres, v3sg  = vpres,
            v1pl  = vpres, v2pl  = vpres, v3pl  = vpres,
            vp1sg = vpast, vp2sg = vpast, vp3sg = vpast,
            vp1pl = vpast, vp2pl = vpast, vp3pl = vpast
        )

class SemiregularVerb(Verb):
    def __init__(self, *, bare, ving, ved, v3sg, vpast):
        super().__init__(
            inf   = bare,  ving  = ving,  ved   = ved,
            v1sg  = bare,  v2sg  = bare,  v3sg  = v3sg,
            v1pl  = bare,  v2pl  = bare,  v3pl  = bare,
            vp1sg = vpast, vp2sg = vpast, vp3sg = vpast,
            vp1pl = vpast, vp2pl = vpast, vp3pl = vpast
        )

class RegularVerb(SemiregularVerb):
    def __init__(self, cry):
        cries, crying, cried = esize(cry), ingize(cry), edize(cry)

        super().__init__(bare = cry, ving = crying, ved = cried, v3sg = cries, vpast = cried)
