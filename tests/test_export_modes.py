from pathlib import Path
from spx.export.playlists import export_strict, export_mirrored, export_placeholders


def _sample_tracks():
    return [
        {'position': 0, 'name': 'Song One', 'artist': 'Artist', 'duration_ms': 1000, 'local_path': Path('file1.mp3')},
        {'position': 1, 'name': 'Song Two', 'artist': 'Artist', 'duration_ms': 2000, 'local_path': None},
        {'position': 2, 'name': 'Song Two', 'artist': 'Artist', 'duration_ms': 2000, 'local_path': None},  # duplicate name to test uniqueness
    ]


def test_export_strict(tmp_path: Path):
    pl = {'name': 'My Playlist', 'id': 'testid12345678'}
    tracks = _sample_tracks()
    path = export_strict(pl, tracks, tmp_path)
    content = path.read_text(encoding='utf-8').splitlines()
    # Check filename includes ID (sanitize_filename keeps spaces)
    assert path.name == 'My Playlist_testid12.m3u8'
    # Only the matched track path appears
    assert 'file1.mp3' in content
    assert '#EXTINF' not in '\n'.join(content)
    assert 'MISSING' not in '\n'.join(content)


def test_export_mirrored(tmp_path: Path):
    pl = {'name': 'Mirror List', 'id': 'mirrorid123456'}
    tracks = _sample_tracks()
    path = export_mirrored(pl, tracks, tmp_path)
    lines = path.read_text(encoding='utf-8').splitlines()
    # Check filename includes ID (sanitize_filename keeps spaces)
    assert path.name == 'Mirror List_mirrorid.m3u8'
    # EXTINF lines count equals 3 tracks
    extinf = [l for l in lines if l.startswith('#EXTINF')]
    assert len(extinf) == 3
    # Missing markers present for two missing tracks
    missing_markers = [l for l in lines if l.startswith('# MISSING:')]
    assert len(missing_markers) == 2


def test_export_placeholders(tmp_path: Path):
    pl = {'name': 'Placeholders', 'id': 'placehold12345'}
    tracks = _sample_tracks()
    path = export_placeholders(pl, tracks, tmp_path, placeholder_extension='.missing')
    lines = path.read_text(encoding='utf-8').splitlines()
    # Check filename includes ID (first 8 chars of 'placehold12345' = 'placehol')
    assert path.name == 'Placeholders_placehol.m3u8'
    # Check placeholder directory name includes ID
    placeholder_dir = tmp_path / 'Placeholders_placehol_placeholders'
    assert placeholder_dir.exists()
    placeholder_files = list(placeholder_dir.glob('*.missing'))
    # Two missing tracks => two placeholder files, distinct names
    assert len(placeholder_files) == 2
    names = {p.name for p in placeholder_files}
    assert len(names) == 2
    # Playlist references placeholders (relative paths)
    rel_refs = [l for l in lines if l.endswith('.missing')]
    assert len(rel_refs) == 2
    # EXTINF lines should be 3
    extinf = [l for l in lines if l.startswith('#EXTINF')]
    assert len(extinf) == 3
