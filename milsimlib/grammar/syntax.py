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

from collections.abc import Callable, Iterator
from abc import ABC, abstractmethod
from typing import Any, Protocol

from milsimlib.grammar.category import Number, Person, Case, VerbForm

class HasEmit(Protocol):
    def emit(rem : Iterator[str]) -> Iterator[str]:
        ...

Token = str | HasEmit

class Phrase(ABC):
    def __class_getitem__(klass, typeval):
        if typeval is Ellipsis:
            return Callable[..., klass]
        elif isinstance(typeval, tuple):
            return Callable[list(typeval), klass]
        else:
            return Callable[[typeval], klass]

    @abstractmethod
    def linearize(self, *w : Any, **kw : Any) -> Iterator[Token]:
        ...

class NP(Phrase):
    def __init__(self, l, r, /, *, number : Number, person : Person):
        self.left, self.right = l, r

        self.number, self.person = number, person

    def linearize(self, c : Case) -> Iterator[Token]:
        yield from self.left(c)
        yield from self.right(c)

class VP(Phrase):
    def __init__(self, l, r, /):
        self.left, self.right = l, r

    def linearize(self, vf : VerbForm) -> Iterator[Token]:
        yield from self.left(vf)
        yield from self.right(vf)

class Sentence(ABC):
    @abstractmethod
    def linearize(self) -> Iterator[Token]:
        ...
