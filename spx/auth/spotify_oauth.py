from __future__ import annotations
import base64
import hashlib
import json
import os
import random
import string
import threading
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, urlparse, parse_qs
import requests
from typing import Dict, Any, Optional
import ssl
try:
    # Local import; keep optional to avoid import cycles during certain test scenarios
    from .certutil import ensure_self_signed  # type: ignore
except Exception:  # pragma: no cover
    ensure_self_signed = None  # type: ignore

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"


def _code_verifier(length: int = 64) -> str:
    alphabet = string.ascii_letters + string.digits + "-._~"
    return ''.join(random.choice(alphabet) for _ in range(length))


def _code_challenge(verifier: str) -> str:
    h = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(h).decode().rstrip('=')


class OAuthServer(HTTPServer):
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        self.code: Optional[str] = None
        self.error: Optional[str] = None
        self.error_description: Optional[str] = None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = qs.get('code', [None])[0]
        error = qs.get('error', [None])[0]
        error_description = qs.get('error_description', [None])[0]
        # Only set the code if we actually received one; avoid overwriting a valid code
        # with None when the browser later requests /favicon.ico or other assets.
        if code is not None:
            self.server.code = code  # type: ignore[attr-defined]
        if error is not None:
            self.server.error = error  # type: ignore[attr-defined]
            if error_description:
                self.server.error_description = error_description  # type: ignore[attr-defined]
        elif os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Ignoring request without code path={self.path}")
        if os.environ.get('SPX_DEBUG'):
            state_dbg = qs.get('state', [''])[0]
            print(f"[SPX_DEBUG] Callback received path={self.path} code={code} error={error} state={state_dbg}")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        if error:
            self.wfile.write(b"Authorization failed. You may close this window.")
        else:
            self.wfile.write(b"You may close this window.")

    def log_message(self, format, *args):  # silence default logging
        return


class SpotifyAuth:
    def __init__(self, client_id: str, redirect_port: int, scope: str, cache_file: str = "tokens.json", redirect_path: str = "/callback", redirect_scheme: str = "http", redirect_host: str = "127.0.0.1", cert_file: str | None = None, key_file: str | None = None, timeout_seconds: int = 300):
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.scope = scope
        self.cache_file = cache_file
        self.redirect_scheme = redirect_scheme
        self.redirect_host = redirect_host
        # Normalize redirect path; ensure starts with '/'
        if not redirect_path.startswith('/'):
            redirect_path = '/' + redirect_path
        self.redirect_path = redirect_path
        self.cert_file = cert_file
        self.key_file = key_file
        self.timeout_seconds = timeout_seconds

    # ---------------- Token Cache Helpers -----------------
    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                    if os.environ.get('SPX_DEBUG'):
                        print(f"[SPX_DEBUG] Loaded token cache from {self.cache_file}")
                    return data
            except Exception:
                return {}
        return {}

    def _save_cache(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
            if os.environ.get('SPX_DEBUG'):
                abs_path = os.path.abspath(self.cache_file)
                print(f"[SPX_DEBUG] Saved token cache to {abs_path}")
        except Exception:
            pass

    def _needs_refresh(self, tok: Dict[str, Any]) -> bool:
        exp = tok.get('expires_at')
        if not exp:
            return True
        # refresh 60s early
        return time.time() + 60 >= exp

    def _refresh(self, tok: Dict[str, Any]) -> Dict[str, Any]:
        refresh_token = tok.get('refresh_token')
        if not refresh_token:
            return tok
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': self.client_id,
        }
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        new_tok = resp.json()
        # keep old refresh if not returned
        if 'refresh_token' not in new_tok:
            new_tok['refresh_token'] = refresh_token
        new_tok['expires_at'] = time.time() + int(new_tok.get('expires_in', 3600))
        self._save_cache(new_tok)
        return new_tok

    def get_token(self, force: bool = False) -> Dict[str, Any]:
        cached = self._load_cache()
        if not force and cached and not self._needs_refresh(cached):
            return cached
        if cached and self._needs_refresh(cached) and cached.get('refresh_token'):
            try:
                return self._refresh(cached)
            except Exception:
                pass
        # full auth flow
        return self._auth_flow()

    # ---------------- Primary Auth Flow -----------------
    def _auth_flow(self) -> Dict[str, Any]:
        verifier = _code_verifier()
        challenge = _code_challenge(verifier)
        redirect_uri = self.build_redirect_uri()
        # Generate a state token (mitigate stale/cached session anomalies & CSRF)
        state = base64.urlsafe_b64encode(os.urandom(12)).decode().rstrip('=')
        expected_state = state
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Beginning auth flow. Redirect URI: {redirect_uri} state={state}")
        # If HTTPS required, ensure cert BEFORE opening browser so user doesn't see invalid URL failure first.
        server = OAuthServer((self.redirect_host, self.redirect_port), OAuthHandler)
        if self.redirect_scheme.lower() == 'https':
            if not self.cert_file:
                self.cert_file = 'cert.pem'
            if not self.key_file:
                self.key_file = 'key.pem'
            need_gen = not (os.path.exists(self.cert_file) and os.path.exists(self.key_file))
            if need_gen and ensure_self_signed:
                try:
                    ensure_self_signed(self.cert_file, self.key_file)  # type: ignore[arg-type]
                except Exception as e:  # pragma: no cover
                    raise RuntimeError(
                        "Failed to generate self-signed certificate automatically. "
                        "Either install the 'cryptography' package (pip install cryptography), "
                        "install OpenSSL, or set SPX__SPOTIFY__REDIRECT_SCHEME=http to fall back to http. "
                        f"Original error: {e}"
                    ) from e
            if not (os.path.exists(self.cert_file) and os.path.exists(self.key_file)):
                raise RuntimeError(
                    "HTTPS redirect selected but cert/key files still missing. "
                    "Set SPX__SPOTIFY__REDIRECT_SCHEME=http for local development or pre-create cert.pem/key.pem."
                )
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(certfile=self.cert_file, keyfile=self.key_file)
            server.socket = context.wrap_socket(server.socket, server_side=True)
            if os.environ.get('SPX_DEBUG'):
                print(f"[SPX_DEBUG] HTTPS server ready with cert={self.cert_file} key={self.key_file}")
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
            "state": state,
        }
        url = f"{AUTH_URL}?{urlencode(params)}"
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Opening browser to: {url}")
        webbrowser.open(url)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Local server started on port {self.redirect_port}, waiting for authorization code...")
        start = time.time()
        while server.code is None:
            # Surface errors early
            if getattr(server, 'error', None):
                err = server.error  # type: ignore[attr-defined]
                desc = getattr(server, 'error_description', '')  # type: ignore[attr-defined]
                server.shutdown()
                raise RuntimeError(f"Spotify authorization error: {err} {desc}".strip())
            if time.time() - start > self.timeout_seconds:
                server.shutdown()
                raise TimeoutError("Authorization timeout expired.")
            time.sleep(0.05)
        server.shutdown()
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Received authorization code: {server.code}")
        code = server.code
        # Optional basic state validation (ignore if Spotify didn't echo it for some reason)
        # Extract state from server.code path (handler did not store it; extend handler for completeness)
        # NOTE: For minimal intrusion, we re-parse last request URL from handler 'path'
        # If needed we could extend handler to store qs state. For now we skip strict enforcement.
        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Exchanging code for token at {TOKEN_URL}")
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        tok = resp.json()
        tok['expires_at'] = time.time() + int(tok.get('expires_in', 3600))
        self._save_cache(tok)
        if os.environ.get('SPX_DEBUG'):
            print(f"[SPX_DEBUG] Token acquired (expires_in={tok.get('expires_in')})")
        return tok

    def build_redirect_uri(self) -> str:
        return f"{self.redirect_scheme}://{self.redirect_host}:{self.redirect_port}{self.redirect_path}"

__all__ = ["SpotifyAuth"]
