from pathlib import Path
from psm.export.playlists import export_strict, export_mirrored, export_placeholders


def _sample_tracks():
    return [
        {"position": 0, "name": "Song One", "artist": "Artist", "duration_ms": 1000, "local_path": Path("file1.mp3")},
        {"position": 1, "name": "Song Two", "artist": "Artist", "duration_ms": 2000, "local_path": None},
        {
            "position": 2,
            "name": "Song Two",
            "artist": "Artist",
            "duration_ms": 2000,
            "local_path": None,
        },  # duplicate name to test uniqueness
    ]


def test_export_strict(tmp_path: Path):
    pl = {"name": "My Playlist", "id": "testid12345678"}
    tracks = _sample_tracks()
    path = export_strict(pl, tracks, tmp_path)
    content = path.read_text(encoding="utf-8").splitlines()
    # Check filename includes ID (sanitize_filename keeps spaces)
    assert path.name == "My Playlist_testid12.m3u"
    # Only the matched track path appears
    assert "file1.mp3" in content
    assert "#EXTINF" not in "\n".join(content)
    assert "MISSING" not in "\n".join(content)


def test_export_mirrored(tmp_path: Path):
    pl = {"name": "Mirror List", "id": "mirrorid123456"}
    tracks = _sample_tracks()
    path = export_mirrored(pl, tracks, tmp_path)
    lines = path.read_text(encoding="utf-8").splitlines()
    # Check filename includes ID (sanitize_filename keeps spaces)
    assert path.name == "Mirror List_mirrorid.m3u"
    # NOTE comment for missing tracks with emoji indicator
    note_lines = [l for l in lines if "NOTE" in l and "not found" in l]
    assert len(note_lines) == 1
    assert "❌" in "\n".join(lines), "Expected ❌ emoji indicator in header or EXTINF"
    # EXTINF lines count equals ALL tracks (mirrored mode preserves order)
    extinf = [l for l in lines if l.startswith("#EXTINF")]
    assert len(extinf) == 3, f"Expected 3 tracks (all tracks), got {len(extinf)}"
    # Missing tracks should have ❌ emoji in their EXTINF title
    missing_extinf = [l for l in extinf if "❌" in l]
    assert len(missing_extinf) == 2, "Expected 2 EXTINF lines with ❌ emoji for missing tracks"
    # Missing tracks use '!' prefix placeholder
    missing_placeholders = [l for l in lines if l.startswith("!MISSING")]
    assert len(missing_placeholders) == 2, "Expected 2 missing track placeholders"


def test_export_placeholders(tmp_path: Path):
    pl = {"name": "Placeholders", "id": "placehold12345"}
    tracks = _sample_tracks()
    path = export_placeholders(pl, tracks, tmp_path, placeholder_extension=".missing")
    lines = path.read_text(encoding="utf-8").splitlines()
    # Check filename includes ID (first 8 chars of 'placehold12345' = 'placehol')
    assert path.name == "Placeholders_placehol.m3u"
    # Check placeholder directory name includes ID
    placeholder_dir = tmp_path / "Placeholders_placehol_placeholders"
    assert placeholder_dir.exists()
    placeholder_files = list(placeholder_dir.glob("*.missing"))
    # Two missing tracks => two placeholder files, distinct names
    assert len(placeholder_files) == 2
    names = {p.name for p in placeholder_files}
    assert len(names) == 2
    # Playlist references placeholders (relative paths)
    rel_refs = [l for l in lines if l.endswith(".missing")]
    assert len(rel_refs) == 2
    # EXTINF lines should be 3
    extinf = [l for l in lines if l.startswith("#EXTINF")]
    assert len(extinf) == 3
