"""Spotify Connect contract tests without network or credentials."""

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SPEC = importlib.util.spec_from_file_location(
    "spotify_connect", Path(__file__).with_name("spotify_connect.py"))
spotify = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(spotify)


class FakeClient(spotify.SpotifyClient):
    def __init__(self, devices, playback=None):
        self.available_devices = devices
        self.playback = playback or {}
        self.calls = []

    def api(self, method, path, payload=None):
        self.calls.append((method, path, payload))
        if path == "/me/player/devices":
            return {"devices": self.available_devices}
        if path == "/search?type=track&limit=5&q=Ryden":
            return {"tracks": {"items": [{"id": "song1", "name": "Ryden", "uri": "spotify:track:song1"}]}}
        if path == "/me/player":
            return self.playback
        return None


class SpotifyConnectTests(unittest.TestCase):
    def test_exact_device_starts_selected_track_only_there(self):
        client = FakeClient([{"id": "echo1", "name": "Echo Plus", "is_restricted": False}],
                            {"is_playing": True, "device": {"id": "echo1"},
                             "item": {"uri": "spotify:track:song1"}})
        result = client.play("Ryden", "track", "echo plus")
        self.assertTrue(result["ok"])
        self.assertIn(("PUT", "/me/player/play?device_id=echo1",
                       {"uris": ["spotify:track:song1"]}), client.calls)

    def test_missing_ambiguous_or_restricted_device_never_starts(self):
        for devices in ([],
                        [{"id": "a", "name": "Echo Plus"}, {"id": "b", "name": "ECHO PLUS"}],
                        [{"id": "a", "name": "Echo Plus", "is_restricted": True}]):
            with self.subTest(devices=devices):
                client = FakeClient(devices)
                result = client.play("Ryden", "track", "Echo Plus")
                self.assertFalse(result["ok"])
                self.assertFalse(any(path.startswith("/me/player/play") for _, path, _ in client.calls))

    def test_device_name_normalizes_whitespace_and_accepts_unique_prefix(self):
        client = FakeClient([{"id": "echo1", "name": "Echo Plus  della cucina"}])
        for name in ("  ECHO   PLUS della cucina ", "echo plus"):
            with self.subTest(name=name):
                self.assertEqual(client._device(name)["id"], "echo1")

    def test_device_abbreviation_must_be_unique_and_end_at_word_boundary(self):
        for devices, name in (
            ([{"id": "a", "name": "Echo Plus cucina"},
              {"id": "b", "name": "Echo Plus sala"}], "echo plus"),
            ([{"id": "a", "name": "Echo Plus cucina"}], "echo plu"),
            ([{"id": "a", "name": "Echo Plus cucina"}], "   "),
            ([{"id": "a", "name": "Echo Plus cucina", "is_restricted": True}], "echo plus"),
        ):
            with self.subTest(devices=devices, name=name):
                client = FakeClient(devices)
                self.assertFalse(client.play("Ryden", "track", name)["ok"])
                self.assertFalse(any(method == "PUT" for method, _, _ in client.calls))

    def test_unverified_playback_is_pending_not_success(self):
        client = FakeClient([{"id": "echo1", "name": "Echo Plus"}])
        result = client.play("Ryden", "track", "Echo Plus")
        self.assertFalse(result["ok"])
        self.assertTrue(result["pending"])

    def test_voice_command_passes_query_and_device_together(self):
        assistant_spec = importlib.util.spec_from_file_location(
            "assistant_spotify_test", Path(__file__).with_name("assistant.py"))
        assistant = importlib.util.module_from_spec(assistant_spec)
        assistant_spec.loader.exec_module(assistant)
        with mock.patch.object(assistant, "execute_tool", return_value={"ok": True, "selected": {"name": "Ryden"}}) as tool:
            response = assistant.fast_voice_intent("Hey Peppe, suona 'ryden' su echo plus")
        tool.assert_called_once_with("spotify_play", {"query": "ryden", "type": "track", "device": "echo plus"})
        self.assertEqual(response["tools"][0]["tool"], "spotify_play")

    def test_text_command_needs_no_model_and_propagates_missing_auth(self):
        import assistant
        with mock.patch.object(assistant, "execute_tool", return_value={"ok": False, "error": "login richiesto"}) as tool, \
             mock.patch.object(assistant, "llama") as model:
            result = assistant.chat("hei peppe, suona ryden su echo plus", [])
        model.assert_not_called()
        self.assertIn("login richiesto", result["answer"])
        self.assertEqual(tool.call_args.args[1]["device"], "echo plus")

    def test_api_control_failure_never_uses_global_media_keys(self):
        import assistant
        with mock.patch.object(assistant.SpotifyClient, "control", return_value={"ok": False}) as api, \
             mock.patch.object(assistant, "run") as shell:
            self.assertFalse(assistant.spotify_bus("next")["ok"])
        api.assert_called_once_with("next")
        shell.assert_not_called()

    def test_spotify_is_not_mistaken_for_device_name(self):
        import assistant
        with mock.patch.object(assistant, "execute_tool") as tool:
            self.assertIsNone(assistant.spotify_combined_intent("riproduci Ryden su Spotify"))
        tool.assert_not_called()

    def test_wrong_oauth_state_is_rejected(self):
        self.assertIsNone(spotify._authorization_code("/callback?code=abc&state=wrong", "expected"))
        self.assertIsNone(spotify._authorization_code("/other?code=abc&state=expected", "expected"))
        self.assertEqual(spotify._authorization_code("/callback?code=abc&state=expected", "expected"), "abc")

    def test_expired_token_refreshes_and_preserves_refresh_token(self):
        with tempfile.TemporaryDirectory() as folder:
            token_file = Path(folder) / "spotify-token.json"
            token_file.write_text(json.dumps({"access_token": "old", "refresh_token": "keep",
                                              "expires_at": time.time() - 10}))
            with mock.patch.object(spotify, "TOKEN_FILE", token_file), \
                 mock.patch.object(spotify, "_client_id", return_value="a" * 32), \
                 mock.patch.object(spotify, "_token_request", return_value={"access_token": "new", "expires_in": 3600}):
                self.assertEqual(spotify.SpotifyClient()._access_token(), "new")
            saved = json.loads(token_file.read_text())
            self.assertEqual(saved["refresh_token"], "keep")
            self.assertEqual(token_file.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
