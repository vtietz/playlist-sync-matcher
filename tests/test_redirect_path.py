from spx.auth.spotify_oauth import SpotifyAuth


def test_build_redirect_uri_custom_path(monkeypatch, tmp_path):
    # Basic instantiation just to verify redirect path composition
    auth = SpotifyAuth(client_id='dummy', redirect_port=5555, scope='user-library-read', cache_file=str(tmp_path / 'tok.json'), redirect_path='/')
    assert auth.build_redirect_uri() == 'http://localhost:5555/'
    auth2 = SpotifyAuth(client_id='dummy', redirect_port=5555, scope='user-library-read', cache_file=str(tmp_path / 'tok2.json'), redirect_path='cb')
    # leading slash should be normalized
    assert auth2.build_redirect_uri() == 'http://localhost:5555/cb'