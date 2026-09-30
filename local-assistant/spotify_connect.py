#!/usr/bin/env python3
"""Spotify Web API controller for the graphical Spotify Connect player."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


REDIRECT_URI = "http://127.0.0.1:8181/callback"
SCOPES = "user-read-playback-state user-modify-playback-state"
TOKEN_FILE = Path.home() / ".config/local-ai/spotify-connect-token.json"
_token_lock = threading.Lock()


def _client_id() -> str:
    value = os.environ.get("SPOTIFY_CLIENT_ID", "").strip()
    if not value:
        path = Path.home() / ".config/local-ai/spotify-client-id"
        if path.is_file():
            value = path.read_text().strip()
    if not value or not all(c in "0123456789abcdefABCDEF" for c in value) or len(value) != 32:
        raise ValueError("Configura il Client ID della tua app Spotify in SPOTIFY_CLIENT_ID")
    return value


def _save_token(token: dict) -> None:
    TOKEN_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".spotify-token-", dir=TOKEN_FILE.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            os.fchmod(handle.fileno(), 0o600)
            json.dump(token, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, TOKEN_FILE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def _token_request(form: dict) -> dict:
    request = urllib.request.Request(
        "https://accounts.spotify.com/api/token",
        urllib.parse.urlencode(form).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Autorizzazione Spotify non riuscita (HTTP {exc.code})") from None


def _authorization_code(path: str, state: str) -> str | None:
    parsed = urllib.parse.urlparse(path)
    query = urllib.parse.parse_qs(parsed.query)
    if parsed.path != "/callback" or query.get("state") != [state]:
        return None
    return query.get("code", [None])[0]


def login() -> None:
    client_id = _client_id()
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    received = {}

    class Callback(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            code = _authorization_code(self.path, state)
            if code or (parsed.path == "/callback" and query.get("state") == [state]):
                received["code"] = code
                received["error"] = query.get("error", [None])[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Autorizzazione ricevuta. Puoi chiudere questa pagina.")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Richiesta non valida.")

        def log_message(self, *_args):
            pass

    params = urllib.parse.urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT_URI,
        "scope": SCOPES, "code_challenge_method": "S256",
        "code_challenge": challenge, "state": state,
    })
    with HTTPServer(("127.0.0.1", 8181), Callback) as server:
        print("Apro Spotify nel browser per autorizzare Peppe. Attendo fino a 3 minuti.")
        webbrowser.open("https://accounts.spotify.com/authorize?" + params)
        deadline = time.monotonic() + 180
        while "code" not in received and "error" not in received and time.monotonic() < deadline:
            server.timeout = min(2, max(0, deadline - time.monotonic()))
            server.handle_request()
    if not received.get("code"):
        raise RuntimeError("Autorizzazione Spotify non completata")
    token = _token_request({"grant_type": "authorization_code", "code": received["code"],
                            "redirect_uri": REDIRECT_URI, "client_id": client_id,
                            "code_verifier": verifier})
    token["expires_at"] = time.time() + int(token["expires_in"]) - 60
    _save_token(token)
    print("Spotify Connect autorizzato per Peppe.")


class SpotifyClient:
    def _access_token(self) -> str:
        with _token_lock:
            if not TOKEN_FILE.is_file():
                raise RuntimeError("Spotify non autenticato: esegui spotify_connect.py --login")
            token = json.loads(TOKEN_FILE.read_text())
            if time.time() >= token.get("expires_at", 0):
                if not token.get("refresh_token"):
                    raise RuntimeError("Spotify non autenticato: esegui spotify_connect.py --login")
                fresh = _token_request({"grant_type": "refresh_token",
                                        "refresh_token": token["refresh_token"],
                                        "client_id": _client_id()})
                token.update(fresh)
                token["expires_at"] = time.time() + int(fresh["expires_in"]) - 60
                _save_token(token)
            return token["access_token"]

    def api(self, method: str, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        request = urllib.request.Request(
            "https://api.spotify.com/v1" + path, data=data, method=method,
            headers={"Authorization": "Bearer " + self._access_token(),
                     "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                return json.load(response) if response.status != 204 else {}
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Spotify API HTTP {exc.code}") from None

    def devices(self) -> list[dict]:
        return self.api("GET", "/me/player/devices").get("devices", [])

    def _device(self, name: str) -> dict:
        requested = " ".join(name.casefold().split())
        if not requested:
            raise ValueError("Nome dispositivo Spotify vuoto")
        devices = [(device, " ".join(device.get("name", "").casefold().split()))
                   for device in self.devices()]
        matches = [device for device, normalized in devices if normalized == requested]
        if not matches:
            matches = [device for device, normalized in devices
                       if normalized.startswith(requested + " ")]
        if len(matches) != 1 or not matches[0].get("id") or matches[0].get("is_restricted"):
            raise ValueError("Dispositivo Spotify assente, ambiguo o non controllabile")
        return matches[0]

    def search(self, query: str, media_type: str = "track") -> dict:
        if media_type not in ("track", "playlist", "album", "artist"):
            raise ValueError("Tipo Spotify non consentito")
        if not query.strip():
            raise ValueError("Query Spotify vuota")
        path = "/search?" + urllib.parse.urlencode({"type": media_type, "limit": 5, "q": query.strip()})
        items = self.api("GET", path).get(media_type + "s", {}).get("items", [])
        return {"query": query, "results": [{"id": i.get("id"), "name": i.get("name"),
                "uri": i.get("uri")} for i in items if isinstance(i, dict) and i.get("uri")]}

    def play(self, query: str, media_type: str = "track", device: str = "") -> dict:
        try:
            target = self._device(device) if device else None
            found = self.search(query, media_type)
            if not found["results"]:
                return {"ok": False, "error": "Nessun risultato Spotify trovato"}
            item = found["results"][0]
            path = "/me/player/play"
            if target:
                path += "?" + urllib.parse.urlencode({"device_id": target["id"]})
            payload = ({"uris": [item["uri"]]} if media_type == "track"
                       else {"context_uri": item["uri"]})
            self.api("PUT", path, payload)
            for attempt in range(3):
                state = self.api("GET", "/me/player")
                active = state.get("device") or {}
                playing = state.get("item") or {}
                context = state.get("context") or {}
                uri = playing.get("uri") if media_type == "track" else context.get("uri")
                if state.get("is_playing") and uri == item["uri"] and (
                    not target or active.get("id") == target["id"]
                ):
                    return {"ok": True, "selected": item,
                            "device": active.get("name") or device}
                if attempt < 2:
                    time.sleep(0.4)
            return {"ok": False, "pending": True, "selected": item,
                    "error": "Spotify non ha ancora confermato la riproduzione sul dispositivo"}
        except (RuntimeError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    def transfer(self, name: str) -> dict:
        try:
            target = self._device(name)
            self.api("PUT", "/me/player", {"device_ids": [target["id"]], "play": False})
            state = self.api("GET", "/me/player")
            if (state.get("device") or {}).get("id") == target["id"]:
                return {"ok": True, "device": target["name"]}
            return {"ok": False, "pending": True,
                    "error": "Spotify non ha ancora confermato il dispositivo"}
        except (RuntimeError, ValueError, OSError) as exc:
            return {"ok": False, "error": str(exc)}

    def control(self, action: str) -> dict:
        endpoints = {"play": ("PUT", "/me/player/play"),
                     "pause": ("PUT", "/me/player/pause"),
                     "next": ("POST", "/me/player/next"),
                     "previous": ("POST", "/me/player/previous")}
        if action not in endpoints:
            return {"ok": False, "error": "azione non consentita"}
        method, path = endpoints[action]
        try:
            self.api(method, path)
            return {"ok": True, "backend": "spotify-api"}
        except (RuntimeError, OSError) as exc:
            return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    import sys
    if sys.argv[1:] != ["--login"]:
        raise SystemExit("Uso: python3 spotify_connect.py --login")
    try:
        login()
    except (RuntimeError, ValueError, OSError) as error:
        raise SystemExit(str(error)) from None
