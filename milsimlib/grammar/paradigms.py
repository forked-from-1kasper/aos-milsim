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

from collections.abc import Iterator

from milsimlib.grammar.category import GrammarError
from milsimlib.grammar.syntax import HasEmit, Token

def flatten(tokens : Iterator[Token]) -> Iterator[str]:
    for token in tokens:
        if isinstance(token, str):
            yield token
        else:
            rem = flatten(tokens)
            yield from token.emit(rem)
            yield from rem

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
    def __init__(self, *tokens):
        self.tokens = tokens

    def emit(self, rem):
        yield from flatten(self.tokens)

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

def edize(w):
    if w.endswith("e"):
        return w + "d"
    elif w[-2] not in ascii_vowels and w.endswith("y"):
        return w.removesuffix("y") + "ied"
    elif w[-1] in {'h', 'w', 'x', 'y'}:
        return w + "ed"
    elif w[-1] not in ascii_vowels:
        raise GrammarError("Unable to generate past form for ‘{}’ automatically".format(w))
    else:
        return w + "ed"

def ingize(w):
    if w.endswith("e"):
        return w.removesuffix("e") + "ing"
    elif w.endswith("ie"):
        return w.removesuffix("ie") + "ying"
    elif w[-1] in {'h', 'w', 'x', 'y'}:
        return w + "ing"
    elif w[-1] not in ascii_vowels:
        raise GrammarError("Unable to generate present participle for ‘{}’ automatically".format(w))
    else:
        return w + "ing"

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
