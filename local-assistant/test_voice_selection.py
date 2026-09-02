#!/usr/bin/env python3
"""Test del selettore Vosk/Whisper senza caricare modelli vocali."""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path


os.environ["PEPPE_PREFER_VOSK"] = "1"
sys.modules["vosk"] = types.SimpleNamespace(
    KaldiRecognizer=object, Model=object, SetLogLevel=lambda *_args: None,
)
MODULE_PATH = Path(__file__).with_name("peppe_listener.py")
SPEC = importlib.util.spec_from_file_location("peppe_listener_test", MODULE_PATH)
listener = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(listener)


class VoiceSelectionTests(unittest.TestCase):
    def test_whisper_repetition_does_not_reject_correct_vosk(self):
        command, score = listener.select_command(
            "Ehi Peppe come stai? Ehi Peppe come stai? Ehi Peppe come stai?",
            "ehi come stai",
        )
        self.assertEqual(command, "come stai")
        self.assertEqual(score, 1.0)

    def test_vosk_is_preferred_after_sufficient_agreement(self):
        command, score = listener.select_command(
            "Funziona la mania", "funziona meglio",
        )
        self.assertGreaterEqual(score, 0.42)
        self.assertEqual(command, "funziona meglio")

    def test_missing_or_unrelated_transcription_is_rejected(self):
        self.assertEqual(listener.select_command("come stai", ""), ("", 0.0))
        command, score = listener.select_command(
            "riproduci musica rilassante", "che tempo farà domani",
        )
        self.assertEqual(command, "")
        self.assertLess(score, 0.42)


if __name__ == "__main__":
    unittest.main(verbosity=2)
