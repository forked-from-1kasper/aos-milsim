from dataclasses import dataclass
from typing import Optional

from milsim.grammar.category import VerbForm, OBL
from milsim.grammar.syntax import NP, VP
from milsim.grammar.verb import Verb

@dataclass(repr = False)
class AdverbPrefix:
    value : str

    def __call__(self, vp : VP):
        def left(vf : VerbForm):
            yield self.value
            yield from vp.left(vf)

        def right(vf : VerbForm):
            yield from vp.right(vf)

        return VP(left, right)

@dataclass(repr = False)
class AdverbPostfix:
    value : str

    def __call__(self, vp : VP):
        def left(vf : VerbForm):
            yield from vp.left(vf)

        def right(vf : VerbForm):
            yield from vp.right(vf)
            yield self.value

        return VP(left, right)

def VerbNTR(verb : Verb, ptcl : Optional[str] = None):
    def left(vf : VerbForm):
        yield verb.decline(vf)

    def right(vf : VerbForm):
        if ptcl is not None:
            yield ptcl

    return VP(left, right)

@dataclass(repr = False)
class VerbNP:
    verb : Verb
    ptcl : Optional[str] = None

    def __call__(self, np : NP):
        def left(vf : VerbForm):
            yield self.verb.decline(vf)

        def right(vf : VerbForm):
            yield from np.linearize(OBL)

            if ptcl := self.ptcl:
                yield ptcl

        return VP(left, right)

@dataclass(repr = False)
class VerbNPPP:
    verb : Verb
    prep : str
    ptcl : Optional[str] = None

    def __call__(self, np1 : Optional[NP], np2 : NP):
        def left(vf : VerbForm):
            yield self.verb.decline(vf)

        def right(vf : VerbForm):
            if np1 is not None:
                yield from np1.linearize(OBL)

            yield self.prep
            yield from np2.linearize(OBL)

            if ptcl := self.ptcl:
                yield ptcl

        return VP(left, right)

@dataclass(repr = False)
class VerbVP:
    verb    : Verb
    complvf : VerbForm

    def __call__(self, vp : VP):
        def left(vf : VerbForm):
            yield self.verb.decline(vf)

        def right(vf : VerbForm):
            yield from vp.linearize(self.complvf)

        return VP(left, right)

@dataclass(repr = False)
class VerbVPPP:
    verb    : Verb
    complvf : VerbForm
    prep    : str

    def __call__(self, vp : VP, np : NP):
        def left(vf : VerbForm):
            yield self.verb.decline(vf)

        def right(vf : VerbForm):
            yield from vp.linearize(self.complvf)

            yield self.prep
            yield from np.linearize(OBL)

        return VP(left, right)
