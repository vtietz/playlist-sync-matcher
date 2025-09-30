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
from typing import Dict, Any

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
        self.code = None


class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # type: ignore[override]
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        code = qs.get('code', [None])[0]
        self.server.code = code  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"You may close this window.")


class SpotifyAuth:
    def __init__(self, client_id: str, redirect_port: int, scope: str, cache_file: str = "tokens.json", redirect_path: str = "/callback"):
        self.client_id = client_id
        self.redirect_port = redirect_port
        self.scope = scope
        self.cache_file = cache_file
        # Normalize redirect path; ensure starts with '/'
        if not redirect_path.startswith('/'):
            redirect_path = '/' + redirect_path
        self.redirect_path = redirect_path

    # ---------------- Token Cache Helpers -----------------
    def _load_cache(self) -> Dict[str, Any]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as fh:
                    return json.load(fh)
            except Exception:
                return {}
        return {}

    def _save_cache(self, data: Dict[str, Any]) -> None:
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as fh:
                json.dump(data, fh)
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
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": self.scope,
            "code_challenge_method": "S256",
            "code_challenge": challenge,
        }
        url = f"{AUTH_URL}?{urlencode(params)}"
        webbrowser.open(url)
        server = OAuthServer(('localhost', self.redirect_port), OAuthHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        while server.code is None:
            pass
        server.shutdown()
        code = server.code
        data = {
            "client_id": self.client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
        resp = requests.post(TOKEN_URL, data=data, timeout=30)
        resp.raise_for_status()
        tok = resp.json()
        tok['expires_at'] = time.time() + int(tok.get('expires_in', 3600))
        self._save_cache(tok)
        return tok

    def build_redirect_uri(self) -> str:
        return f"http://localhost:{self.redirect_port}{self.redirect_path}"

__all__ = ["SpotifyAuth"]
