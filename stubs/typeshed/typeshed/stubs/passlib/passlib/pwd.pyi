from _typeshed import Incomplete
from abc import abstractmethod
from collections.abc import MutableMapping
from typing import Any

class SequenceGenerator:
    length: Any
    requested_entropy: str
    rng: Any
    @property
    @abstractmethod
    def symbol_count(self) -> int: ...
    def __init__(
        self, entropy: Incomplete | None = ..., length: Incomplete | None = ..., rng: Incomplete | None = ..., **kwds
    ) -> None: ...
    @property
    def entropy_per_symbol(self) -> float: ...
    @property
    def entropy(self) -> float: ...
    def __next__(self) -> None: ...
    def __call__(self, returns: Incomplete | None = ...): ...
    def __iter__(self): ...

default_charsets: Any

class WordGenerator(SequenceGenerator):
    charset: str
    chars: Any
    def __init__(self, chars: Incomplete | None = ..., charset: Incomplete | None = ..., **kwds) -> None: ...
    @property
    def symbol_count(self): ...
    def __next__(self): ...

def genword(entropy: Incomplete | None = ..., length: Incomplete | None = ..., returns: Incomplete | None = ..., **kwds): ...

class WordsetDict(MutableMapping[Any, Any]):
    paths: Any
    def __init__(self, *args, **kwds) -> None: ...
    def __getitem__(self, key): ...
    def set_path(self, key, path) -> None: ...
    def __setitem__(self, key, value) -> None: ...
    def __delitem__(self, key) -> None: ...
    def __iter__(self): ...
    def __len__(self) -> int: ...
    def __contains__(self, key): ...

default_wordsets: Any

class PhraseGenerator(SequenceGenerator):
    wordset: str
    words: Any
    sep: str
    def __init__(
        self, wordset: Incomplete | None = ..., words: Incomplete | None = ..., sep: Incomplete | None = ..., **kwds
    ) -> None: ...
    @property
    def symbol_count(self): ...
    def __next__(self): ...

def genphrase(entropy: Incomplete | None = ..., length: Incomplete | None = ..., returns: Incomplete | None = ..., **kwds): ...