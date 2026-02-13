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
from typing import Optional

from milsimlib.grammar.category import GrammarError, Number, SG, PL, Case, NOM, OBL, POS
from milsimlib.grammar.paradigms import CompoundToken, possessify, pluralize
from milsimlib.grammar.syntax import Token

@dataclass
class Noun:
    nom_sg : Optional[Token] = None
    pos_sg : Optional[Token] = None
    nom_pl : Optional[Token] = None
    pos_pl : Optional[Token] = None

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

class Noun2(Noun):
    def __init__(self, *, sg = None, pl = None):
        super().__init__(
            nom_sg = sg, pos_sg = possessify(sg),
            nom_pl = pl, pos_pl = possessify(pl)
        )

class RegularNoun(Noun2):
    def __init__(self, sg):
        super().__init__(sg = sg, pl = pluralize(sg))

class CompoundNoun(Noun):
    def __init__(self, adjunct : Token, noun : Noun):
        super().__init__(
            nom_sg = CompoundToken(adjunct, noun.nom_sg),
            pos_sg = CompoundToken(adjunct, noun.pos_sg),
            nom_pl = CompoundToken(adjunct, noun.nom_pl),
            pos_pl = CompoundToken(adjunct, noun.pos_pl)
        )
