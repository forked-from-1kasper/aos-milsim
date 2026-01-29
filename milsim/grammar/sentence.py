# Copyright © 2025–2026 rzrn

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

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
