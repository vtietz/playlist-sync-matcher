from __future__ import annotations
from pathlib import Path
from typing import BinaryIO
import hashlib

CHUNK = 64 * 1024


def _read_head_tail(fh: BinaryIO, size: int, head_bytes: int, tail_bytes: int) -> bytes:
    if size <= head_bytes + tail_bytes:
        return fh.read()
    head = fh.read(head_bytes)
    # seek tail
    fh.seek(max(size - tail_bytes, 0))
    tail = fh.read(tail_bytes)
    return head + tail


def partial_hash(path: Path, head_bytes: int = 64 * 1024, tail_bytes: int = 64 * 1024) -> str:
    """Hash beginning and end of file plus size to detect renames/moves.
    Returns hex digest sha1(size||head||tail).
    """
    st = path.stat()
    size = st.st_size
    with path.open("rb") as fh:
        data = _read_head_tail(fh, size, head_bytes, tail_bytes)
    h = hashlib.sha1()
    h.update(str(size).encode())
    h.update(data)
    return h.hexdigest()


__all__ = ["partial_hash"]
