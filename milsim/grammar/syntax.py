from collections.abc import Callable, Iterator
from abc import ABC, abstractmethod
from typing import Any, Protocol

from milsim.grammar.category import Number, Person, Case, VerbForm

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
