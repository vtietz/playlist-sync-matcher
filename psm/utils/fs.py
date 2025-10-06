from __future__ import annotations
from pathlib import Path
from typing import Iterable, Iterator, Sequence, Set
import fnmatch


def iter_music_files(paths: Sequence[str], extensions: Sequence[str], ignore_patterns: Sequence[str], follow_symlinks: bool = False) -> Iterator[Path]:
    exts: Set[str] = {e.lower() for e in extensions}
    compiled_ignores = list(ignore_patterns)
    for base in paths:
        root = Path(base)
        if not root.exists():
            continue
        for p in root.rglob('*'):
            try:
                if not follow_symlinks and p.is_symlink():
                    continue
                if p.is_file():
                    name = p.name
                    if any(fnmatch.fnmatch(name, pat) for pat in compiled_ignores):
                        continue
                    if p.suffix.lower() in exts:
                        yield p
            except PermissionError:
                continue

__all__ = ["iter_music_files"]
