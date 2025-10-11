from __future__ import annotations
from pathlib import Path
from typing import Iterable, Iterator, Sequence, Set, Union
import fnmatch
import sys


def normalize_library_path(path: Union[Path, str]) -> str:
    """Normalize a library file path to a canonical form for database storage.
    
    This ensures consistent path representation across different contexts:
    - Resolves to absolute path
    - Normalizes separators (platform-specific)
    - On Windows: uppercases drive letter, normalizes to backslashes
    - Handles symlinks (resolves to real path)
    
    Args:
        path: File path as Path object or string
        
    Returns:
        Canonical normalized path as string
        
    Example:
        >>> normalize_library_path("Z:\\music\\song.mp3")
        'Z:\\music\\song.mp3'
        >>> normalize_library_path("./relative/path.mp3")
        'C:\\absolute\\path.mp3'
    """
    if not isinstance(path, Path):
        path = Path(path)
    
    # Resolve to absolute path (follows symlinks)
    resolved = path.resolve()
    
    # Convert to string
    path_str = str(resolved)
    
    # Platform-specific normalization
    if sys.platform == 'win32':
        # On Windows: uppercase drive letter, ensure backslashes
        if len(path_str) >= 2 and path_str[1] == ':':
            # Normalize drive letter to uppercase
            path_str = path_str[0].upper() + path_str[1:]
        # Ensure backslashes (Path.resolve() should already handle this)
        path_str = path_str.replace('/', '\\')
    
    return path_str


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

__all__ = ["iter_music_files", "normalize_library_path"]
