#!/usr/bin/env python3
"""Test veloci senza rete per streaming, profili e compatibilità."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock


MODULE_PATH = Path(__file__).with_name("assistant.py")
SPEC = importlib.util.spec_from_file_location("peppe_assistant", MODULE_PATH)
assistant = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(assistant)


class FakeResponse:
    def __init__(self, lines):
        self.lines = lines

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __iter__(self):
        return iter(self.lines)


class QuickWinTests(unittest.TestCase):
    def test_profiles_are_bounded_and_automatic(self):
        normal = assistant.response_profile("Ciao, come stai?")
        fast = assistant.response_profile("Modalità rapida: dimmi soltanto ciao")
        deep = assistant.response_profile("Analizza e confronta le due alternative")
        forced = assistant.response_profile("Non analizzare, rispondi brevemente")
        self.assertEqual(normal["id"], "normal")
        self.assertEqual(fast["id"], "fast")
        self.assertEqual(deep["id"], "reasoned")
        self.assertEqual(forced["id"], "fast")
        self.assertEqual(normal["max_tokens"], 700)
        self.assertLessEqual(fast["max_tokens"], 160)
        self.assertLessEqual(deep["max_tokens"], 320)

    def test_voice_budget_is_smaller(self):
        self.assertLess(
            assistant.response_profile("Analizza il problema", True)["max_tokens"],
            assistant.response_profile("Analizza il problema", False)["max_tokens"],
        )

    def test_history_has_message_and_character_limits(self):
        history = [
            {"role": "user" if index % 2 == 0 else "assistant", "content": "x" * 1500}
            for index in range(20)
        ]
        compact = assistant.compact_history(history)
        self.assertLessEqual(len(compact), 10)
        self.assertLessEqual(sum(len(item["content"]) for item in compact), 16000)

    def test_llama_sse_hides_reasoning_and_usage_chunks(self):
        lines = [
            b'data: {"choices":[{"delta":{"reasoning_content":"segreto"}}]}\n',
            'data: {"choices":[{"delta":{"content":"Ci"}}]}\n'.encode(),
            'data: {"choices":[{"delta":{"content":"aò"}}]}\n'.encode("utf-8"),
            b'data: {"choices":[],"usage":{"completion_tokens":2}}\n',
            b'data: [DONE]\n',
        ]
        captured = {}

        def fake_open(request, timeout):
            captured.update(json.loads(request.data))
            return FakeResponse(lines)

        with mock.patch.object(assistant.urllib.request, "urlopen", fake_open):
            text = "".join(assistant.llama_deltas(
                [{"role": "user", "content": "ciao"}], 160,
                assistant.response_profile("ciao"),
            ))
        self.assertEqual(text, "Ciaò")
        self.assertTrue(captured["stream"])
        self.assertTrue(captured["cache_prompt"])
        self.assertNotIn("chat_template_kwargs", captured)
        self.assertNotIn("reasoning_budget_tokens", captured)

    def test_reasoned_profile_enables_thinking_only_for_that_request(self):
        captured = {}

        def fake_open(request, timeout):
            captured.update(json.loads(request.data))
            return FakeResponse([b'data: [DONE]\n'])

        with mock.patch.object(assistant.urllib.request, "urlopen", fake_open):
            list(assistant.llama_deltas(
                [{"role": "user", "content": "confronta"}], 320,
                assistant.response_profile("Analizza e confronta"),
            ))
        self.assertTrue(captured["chat_template_kwargs"]["enable_thinking"])
        self.assertEqual(captured["reasoning_budget_tokens"], 96)

    def test_direct_answer_is_emitted_progressively(self):
        def fake_deltas(*_args, **_kwargs):
            yield "Ciao"
            yield " Peppe"

        deltas = []
        with mock.patch.object(assistant, "llama_deltas", fake_deltas):
            result = assistant.chat("Saluta", [], emit=deltas.append)
        self.assertEqual(deltas, ["Ciao", " Peppe"])
        self.assertEqual(result["answer"], "Ciao Peppe")
        self.assertEqual(result["profile"], "normal")

    def test_tool_json_is_never_emitted(self):
        calls = []

        def fake_deltas(messages, *_args, **_kwargs):
            if any("RISULTATO_STRUMENTO" in item.get("content", "") for item in messages):
                yield "Sono le "
                yield "12:34."
            else:
                yield ' {"tool":"local_time",'
                yield '"args":{}}'

        def fake_tool(name, args):
            calls.append((name, args))
            return {"time": "12:34"}

        deltas = []
        with mock.patch.object(assistant, "llama_deltas", fake_deltas), \
             mock.patch.object(assistant, "execute_tool", fake_tool):
            result = assistant.chat("Che ore sono?", [], emit=deltas.append)
        self.assertEqual("".join(deltas), "Sono le 12:34.")
        self.assertNotIn("tool", "".join(deltas))
        self.assertEqual(calls, [("local_time", {})])
        self.assertEqual(len(result["tools"]), 1)

    def test_non_streaming_client_still_gets_complete_result(self):
        with mock.patch.object(assistant, "llama_deltas", return_value=iter(["Tutto", " bene."])):
            result = assistant.chat("Come va?", [])
        self.assertEqual(result["answer"], "Tutto bene.")

    def test_ui_uses_ndjson_stream(self):
        self.assertIn("stream:true", assistant.INDEX)
        self.assertIn("TextDecoder", assistant.INDEX)
        self.assertIn("{message:t,history:h,stream:true}", assistant.INDEX)
        self.assertNotIn("{message:t,history:h,voice,stream:true}", assistant.INDEX)
        control_text = Path(__file__).with_name("control.py").read_text()
        self.assertIn("application/x-ndjson", control_text)
        self.assertIn("chatRunning", control_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
