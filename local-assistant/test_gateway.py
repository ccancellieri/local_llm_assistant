"""Verifica del trasporto autenticato senza chiamate a provider esterni."""

import json
import os
import tempfile
import types
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

from test_quick_wins import assistant, FakeResponse


class GatewayTests(unittest.TestCase):
    def test_fast_default_limits_ordinary_answers_but_keeps_explicit_analysis(self):
        with mock.patch.dict(os.environ, {"LOCAL_ASSISTANT_DEFAULT_PROFILE": "fast"}):
            ordinary = assistant.response_profile("Ciao, raccontami qualcosa")
            voice = assistant.response_profile("Ciao", voice=True)
            analysis = assistant.response_profile("Analizza le alternative")
        self.assertEqual(ordinary["id"], "fast")
        self.assertEqual(ordinary["max_tokens"], 160)
        self.assertFalse(ordinary["enable_thinking"])
        self.assertEqual(voice["max_tokens"], 96)
        self.assertEqual(analysis["id"], "reasoned")

    def test_authenticated_stream_preserves_model_and_deltas(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "gateway.key"
            key.write_text("synthetic-test-key\n")
            response = FakeResponse([
                b'data: {"choices":[{"delta":{"content":"Ciao"}}]}\n',
                b'data: [DONE]\n',
            ])
            with mock.patch.dict(os.environ, {"LOCAL_LLM_API_KEY_FILE": str(key)}), \
                    mock.patch.object(assistant, "LLAMA_MODEL", "home/peppe"), \
                    mock.patch.object(assistant.urllib.request, "urlopen", return_value=response) as send:
                self.assertEqual(assistant.llama([], 20), "Ciao")
            request = send.call_args.args[0]
            self.assertEqual(request.get_header("Authorization"), "Bearer synthetic-test-key")
            self.assertEqual(json.loads(request.data)["model"], "home/peppe")

    def test_invalid_key_file_fails_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            key = Path(directory) / "gateway.key"
            for content in (None, "", "bad\nheader"):
                if content is not None:
                    key.write_text(content)
                with self.subTest(content=content), \
                        mock.patch.dict(os.environ, {"LOCAL_LLM_API_KEY_FILE": str(key)}), \
                        mock.patch.object(assistant.urllib.request, "urlopen") as send:
                    with self.assertRaisesRegex(RuntimeError, "Credenziale LLM"):
                        assistant.llama([], 20)
                    send.assert_not_called()

    def test_default_transport_does_not_require_credentials(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(assistant.urllib.request, "urlopen", return_value=FakeResponse([])) as send:
            self.assertEqual(assistant.llama([], 20), "")
        self.assertIsNone(send.call_args.args[0].get_header("Authorization"))

    def test_upstream_failure_does_not_retry_or_fallback(self):
        failure = urllib.error.HTTPError("http://localhost/v1/chat/completions", 429,
                                         "Quota exhausted", {}, None)
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(assistant.urllib.request, "urlopen", side_effect=failure) as send:
            with self.assertRaises(urllib.error.HTTPError):
                assistant.llama([], 20)
        self.assertEqual(send.call_count, 1)

    def test_health_checks_configured_gateway(self):
        responses = []
        handler = types.SimpleNamespace(path="/health", json_response=responses.append)
        response = FakeResponse([])
        response.status = 200
        with mock.patch.object(assistant, "LLM_HEALTH_URL", "http://localhost:20128/healthz"), \
                mock.patch.object(assistant.urllib.request, "urlopen", return_value=response) as send:
            assistant.Handler.do_GET(handler)
        self.assertEqual(send.call_args.args[0], "http://localhost:20128/healthz")
        self.assertTrue(responses[0]["components"]["llm"])
