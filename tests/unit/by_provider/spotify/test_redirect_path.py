from psm.providers.spotify import SpotifyAuthProvider


def test_build_redirect_uri_custom_path(tmp_path):
    # Default host now 127.0.0.1 (loopback IP per updated policy)
    auth = SpotifyAuthProvider(client_id='dummy', redirect_port=5555, scope='user-library-read', cache_file=str(tmp_path / 'tok.json'), redirect_path='/', redirect_scheme='http')
    assert auth.build_redirect_uri() == 'http://127.0.0.1:5555/'
    # leading slash normalization for custom path
    auth2 = SpotifyAuthProvider(client_id='dummy', redirect_port=5555, scope='user-library-read', cache_file=str(tmp_path / 'tok2.json'), redirect_path='cb', redirect_scheme='http')
    assert auth2.build_redirect_uri() == 'http://127.0.0.1:5555/cb'
    # Explicit override of host (simulate legacy localhost usage)
    auth3 = SpotifyAuthProvider(client_id='dummy', redirect_port=5555, scope='user-library-read', cache_file=str(tmp_path / 'tok3.json'), redirect_path='cb', redirect_scheme='http', redirect_host='localhost')
    assert auth3.build_redirect_uri() == 'http://localhost:5555/cb'
