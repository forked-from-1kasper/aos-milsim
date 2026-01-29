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

class GrammarError(Exception):
    pass

class Category:
    ...

class Number(Category):
    pass

SG = Number() # Singular
PL = Number() # Plural

class Person(Category):
    pass

P1ST = Person() # First person
P2ND = Person() # Second person
P3RD = Person() # Third person

class Case(Category):
    pass

# Nominative and oblique cases differ only for personal pronouns,
# but for simplicity we consider all three even for nouns.
NOM = Case() # Nominative
OBL = Case() # Oblique (objective)
POS = Case() # Possessive

class Tense(Category):
    pass

# Here we consider inflected tenses only, not compound ones like “Present Perfect”.
# Like Russian (я пишу / я писал) or German (ich schreibe / ich schrieb) and unlike Ukrainian (я пишу / я писав / я писатиму)
# or French (j’écris / j’écrivis / j’écrirai), English has only two such tenses (I write / I wrote).
PRES = Tense() # Present
PAST = Tense() # Past

class VerbForm(Category):
    pass

# In principle we can use something like `... | type[Number, Person, Tense]`,
# but since we’ll have to write these abbreviations for convenience anyway,
# it seems that it would be easier to define it like this.
INF     = VerbForm() # Bare infinitive
PTCP1   = VerbForm() # Participle I (present participle)
PTCP2   = VerbForm() # Participle II (past participle)
PRES1SG = VerbForm() # First-person singular, present
PRES2SG = VerbForm() # And so on…
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
