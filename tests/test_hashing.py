from pathlib import Path
from psm.utils.hashing import partial_hash

def test_partial_hash_tmp(tmp_path: Path):
    p = tmp_path / "file.bin"
    p.write_bytes(b"a" * 10_000)
    h1 = partial_hash(p)
    h2 = partial_hash(p)
    assert h1 == h2
    # modify tail
    with p.open('r+b') as fh:
        fh.seek(-10, 2)
        fh.write(b"b" * 10)
    h3 = partial_hash(p)
    assert h3 != h1
