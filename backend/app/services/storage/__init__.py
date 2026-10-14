from pathlib import Path
from uuid import uuid4
from typing import Protocol


class Storage(Protocol):
    def save(self, content: bytes, suffix: str = ".png") -> str: ...
    def read(self, key: str) -> bytes: ...
    def path(self, key: str) -> Path: ...


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if path.parent != self.root:
            raise ValueError("Invalid storage key")
        return path

    def save(self, content: bytes, suffix: str = ".png") -> str:
        if suffix != ".png":
            raise ValueError("Only normalized PNG storage is supported")
        key = f"{uuid4()}{suffix}"
        self.path(key).write_bytes(content)
        return key

    def read(self, key: str) -> bytes:
        return self.path(key).read_bytes()
