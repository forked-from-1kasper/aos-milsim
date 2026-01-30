# Copyright © 2026 rzrn

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

from milsim.grammar.category import GrammarError
from milsim.grammar.syntax import HasEmit

ascii_vowels = {'a', 'e', 'i', 'o', 'u'}

# https://en.wikipedia.org/wiki/Template:A_or_an
class AnToken(HasEmit):
    @staticmethod
    def emit(rem):
        w = next(rem)

        if w.startswith(("eu", "ew", "uni", "one", "once", "U")):
            yield "a"
        elif w[0] in ascii_vowels:
            yield "an"
        elif w in {"heir", "hour", "honor"}:
            yield "an"
        elif w.isupper():
            if w.startswith(("F", "H", "L", "M", "N", "R", "S", "X")):
                yield "an"
            else:
                yield "a"
        elif w.isdigit():
            if w.startswith(("8", "11", "18")):
                yield "an"
            else:
                yield "a"
        else:
            yield "a"

        yield w

class CompoundToken(HasEmit):
    def __init__(self, *words):
        self.words = words

    def emit(self, rem):
        yield from self.words

def possessify(w):
    if w is None:
        return

    if w.endswith("s"):
        return w + "'"
    else:
        return w + "'s"

# https://en.wikipedia.org/wiki/English_plurals
def pluralize(w):
    if w.endswith(("s", "z", "sh", "ch")): # /s/, /z/, /ʃ/, /tʃ/
        return w + "es"
    elif w[-2] not in ascii_vowels and w.endswith("o"):
        return w + "es"
    elif w[-2] not in ascii_vowels and w.endswith("y"):
        return w.removesuffix("y") + "ies"
    elif w.endswith("quy"):
        return w.removesuffix("quy") + "quies"
    else:
        return w + "s"

# https://en.wikipedia.org/wiki/English_verbs
def esize(w):
    if w.endswith(("s", "z", "sh", "ch")): # /s/, /z/, /ʃ/, /tʃ/
        return w + "es"
    elif w[-2] not in ascii_vowels and w.endswith("o"):
        return w + "es"
    elif w[-2] not in ascii_vowels and w.endswith("y"):
        return w.removesuffix("y") + "ies"
    else:
        return w + "s"

ascii_doubling_consonants = {'b', 'd', 'f', 'g', 'j', 'k', 'l', 'm', 'n', 'p', 'q', 's', 'v', 'z'}

def ckize(w):
    if w.endswith("t"):
        raise GrammarError("Cannot decide whether the final syllable is stressed in ‘{}’".format(w))
    elif w.endswith("c"):
        return w.removesuffix("c") + "ck"
    elif w[-1] in ascii_doubling_consonants:
        return w + w[-1]
    else:
        return w

def edize(w):
    if w.endswith("e"):
        return w + "d"
    elif w[-2] not in ascii_vowels and w.endswith("y"):
        return w.removesuffix("y") + "ied"
    else:
        return ckize(w) + "ed"

def ingize(w):
    if w.endswith("e"):
        return w.removesuffix("e") + "ing"
    elif w.endswith("ie"):
        return w.removesuffix("ie") + "ying"
    else:
        return ckize(w) + "ing"

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
