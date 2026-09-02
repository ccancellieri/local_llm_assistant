#!/usr/bin/env python3
"""Verifica offline wake word, stop phrase e Whisper su PCM 16 kHz da stdin."""

import collections
import json
import sys

import peppe_listener as peppe
from vosk import KaldiRecognizer, Model, SetLogLevel


def result_text(recognizer, final=False):
    raw = recognizer.FinalResult() if final else recognizer.PartialResult()
    data = json.loads(raw)
    return str(data.get("text") or data.get("partial") or "")


def main():
    SetLogLevel(-1)
    audio = sys.stdin.buffer.read()
    if len(audio) < peppe.RATE * 2:
        raise SystemExit("FAIL audio assente o troppo corto")
    model = Model(str(peppe.VOSK_MODEL))
    wake = KaldiRecognizer(model, peppe.RATE, peppe.WAKE_GRAMMAR)
    full = KaldiRecognizer(model, peppe.RATE)
    recent = collections.deque(maxlen=80)
    detected = ""
    for pos in range(0, len(audio) - peppe.FRAME_BYTES + 1, peppe.FRAME_BYTES):
        frame = audio[pos:pos + peppe.FRAME_BYTES]
        recent.append(frame)
        full.AcceptWaveform(frame)
        complete = wake.AcceptWaveform(frame)
        heard = (json.loads(wake.Result()).get("text", "")
                 if complete else result_text(wake))
        if peppe.has_wake(heard) and not detected:
            detected = heard
    vosk_text = result_text(full, final=True)
    whisper_text = peppe.transcribe(audio)
    print(f"wake={detected!r}")
    print(f"vosk={vosk_text!r}")
    print(f"whisper={whisper_text!r}")
    print(f"stop={peppe.is_stop(vosk_text) or peppe.is_stop(whisper_text)}")
    if not detected:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
