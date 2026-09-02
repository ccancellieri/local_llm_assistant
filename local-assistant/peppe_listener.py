#!/usr/bin/env python3
"""Listener vocale locale always-on per l'assistente Peppe."""

from __future__ import annotations

import array
import collections
import difflib
import json
import math
import os
import re
import signal
import subprocess
import tempfile
import time
import unicodedata
import urllib.request
import wave
from pathlib import Path

from vosk import KaldiRecognizer, Model, SetLogLevel


RATE = 16_000
FRAME_MS = 20
FRAME_SAMPLES = RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2
DATA = Path.home() / ".local/share/local-ai"
VOSK_MODEL = DATA / "vosk-model/vosk-model-small-it-0.22"
WHISPER = DATA / "whisper/whisper-cli"
WHISPER_MODEL = Path(os.environ.get(
    "PEPPE_WHISPER_MODEL", str(DATA / "whisper/ggml-whisper-base.bin")))
ASSISTANT = "http://127.0.0.1:8090"
SPEAKER_SINK = os.environ.get("PEPPE_SPEAKER_SINK", "").strip()
WAKE_VARIANTS = {"peppe", "pepe", "beppe"}
WAKE_PREFIXES = {"e", "ehi", "hei", "hey", "ciao"}
WAKE_GRAMMAR = json.dumps([
    "ehi peppe", "ehi pepe", "ehi beppe",
    "ciao peppe", "ciao pepe", "ciao beppe",
    "peppe basta", "pepe basta", "beppe basta", "[unk]",
])
ACTIVE_SECONDS = 12
PREFER_VOSK = os.environ.get("PEPPE_PREFER_VOSK", "0") == "1"
running = True


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def stop(_signum=None, _frame=None) -> None:
    global running
    running = False


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9à-ÿ]+", " ", text).strip()


def has_wake(text: str) -> bool:
    words = normalize(text).split()
    return any(words[i] in WAKE_PREFIXES and words[i + 1] in WAKE_VARIANTS
               for i in range(len(words) - 1))


def is_stop(text: str) -> bool:
    words = normalize(text).split()
    return any(words[i] in WAKE_VARIANTS and words[i + 1] in {"basta", "stop", "fine"}
               for i in range(len(words) - 1))


def strip_wake(text: str) -> str:
    words = text.strip().split()
    # Whisper può inserire un articolo: “E' il pepe, che ore sono?”. Cerca il
    # nome nelle prime quattro parole e rimuovi tutto fino a quel punto.
    wake_index = next((i for i, word in enumerate(words[:4])
                       if normalize(word) in WAKE_VARIANTS), None)
    if wake_index is not None:
        words = words[wake_index + 1:]
    elif words and normalize(words[0]) in WAKE_PREFIXES:
        words.pop(0)
    return " ".join(words).lstrip(" ,:;-.!?")


def select_command(whisper_text: str, vosk_text: str) -> tuple[str, float]:
    """Accetta soltanto comandi confermati in modo indipendente dai due STT."""
    whisper_command = strip_wake(whisper_text)
    vosk_command = strip_wake(vosk_text)
    a, b = normalize(whisper_command), normalize(vosk_command)
    if len(a.split()) < 2 or len(b.split()) < 2:
        return "", 0.0
    score = difflib.SequenceMatcher(None, a, b).ratio()
    if score < 0.42:
        return "", score
    # Il filtro WebRTC del portatile conserva molto bene le parole per Vosk;
    # Whisper resta il controllo indipendente contro falsi riconoscimenti.
    selected = (vosk_command if PREFER_VOSK or
                len(b.split()) > len(a.split()) * 1.25 else whisper_command)
    return selected, score


def rms(frame: bytes) -> float:
    values = array.array("h")
    values.frombytes(frame)
    if not values:
        return 0.0
    return math.sqrt(sum(v * v for v in values) / len(values))


def terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def recognizer_text(recognizer: KaldiRecognizer, final: bool = False) -> str:
    raw = recognizer.FinalResult() if final else recognizer.PartialResult()
    result = json.loads(raw)
    return str(result.get("text") or result.get("partial") or "")


def capture_utterance(model: Model, active: bool) -> tuple[bytes, str] | None:
    """Attende la wake word, oppure una frase qualunque se la sessione è attiva."""
    # La frase lunga riduce l'ambiguita rispetto alla singola parola Peppe.
    # Il comando successivo resta verificato da Vosk e Whisper indipendenti.
    recognizer = KaldiRecognizer(model, RATE, WAKE_GRAMMAR)
    capture_device = os.environ.get("PEPPE_CAPTURE_DEVICE", "").strip()
    pulse_source = os.environ.get("PEPPE_PULSE_SOURCE", "").strip()
    if capture_device:
        # Percorso ALSA mantenuto come ripristino diagnostico.
        command = ["arecord", "-q", "-D", capture_device, "-t", "raw",
                   "-f", "S16_LE", "-c", "1", "-r", str(RATE), "-"]
    else:
        command = [
            "parec", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1",
            "--latency-msec=40", "--property=media.name=Peppe wake-word listener",
        ]
        if pulse_source:
            command.insert(1, f"--device={pulse_source}")
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    pre_roll: collections.deque[bytes] = collections.deque(maxlen=80)
    audio: list[bytes] = []
    noise = 180.0
    loud_run = 0
    silent_run = 0
    recording = False
    endpoint_recognizer = None
    voiced_frames = 0
    started = time.monotonic()
    try:
        while running:
            frame = proc.stdout.read(FRAME_BYTES) if proc.stdout else b""
            if len(frame) != FRAME_BYTES:
                return None
            level = rms(frame)
            threshold = max(320.0, noise * 2.8)
            loud = level > threshold
            if not loud and not recording:
                noise = noise * 0.985 + level * 0.015
            pre_roll.append(frame)

            if active and not recording:
                loud_run = loud_run + 1 if loud else 0
                if loud_run >= 3:
                    recording = True
                    audio = list(pre_roll)
                    endpoint_recognizer = KaldiRecognizer(model, RATE)
                    for old_frame in pre_roll:
                        endpoint_recognizer.AcceptWaveform(old_frame)
                    voiced_frames = loud_run
                    log(f"voce rilevata (soglia {threshold:.0f}, livello {level:.0f})")
            elif not active and not recording:
                complete = recognizer.AcceptWaveform(frame)
                heard = (json.loads(recognizer.Result()).get("text", "")
                         if complete else recognizer_text(recognizer))
                if has_wake(heard):
                    recording = True
                    audio = list(pre_roll)
                    endpoint_recognizer = KaldiRecognizer(model, RATE)
                    for old_frame in pre_roll:
                        endpoint_recognizer.AcceptWaveform(old_frame)
                    voiced_frames = 3
                    log(f"wake phrase rilevata: {heard!r}")

            if recording:
                audio.append(frame)
                endpoint = endpoint_recognizer.AcceptWaveform(frame) if endpoint_recognizer else False
                if loud:
                    silent_run = 0
                    voiced_frames += 1
                else:
                    silent_run += 1
                duration_frames = len(audio)
                fast_text = (json.loads(endpoint_recognizer.Result()).get("text", "")
                             if endpoint and endpoint_recognizer else
                             recognizer_text(endpoint_recognizer) if endpoint_recognizer else "")
                # La frase di chiusura deve essere immediata e non dipendere
                # dal più lento Whisper.
                if active and is_stop(fast_text):
                    return b"".join(audio), fast_text
                end_level = max(340.0, noise * 3.2)
                if ((endpoint and voiced_frames >= 12) or
                        (silent_run >= 20 and level < end_level and voiced_frames >= 10) or
                        duration_frames >= 250):
                    if endpoint_recognizer and not fast_text:
                        fast_text = recognizer_text(endpoint_recognizer, final=True)
                    return b"".join(audio), fast_text

            # In sessione attiva non restare aperti oltre la finestra prevista.
            if active and time.monotonic() - started > ACTIVE_SECONDS:
                return b"", ""
    finally:
        terminate(proc)
    return None


def transcribe(raw_audio: bytes) -> str:
    with tempfile.TemporaryDirectory(prefix="peppe-stt-") as td:
        original = Path(td) / "original.wav"
        cleaned = Path(td) / "cleaned.wav"
        with wave.open(str(original), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(RATE)
            wav.writeframes(raw_audio)
        # Il denoise FFT alterava le consonanti del DMIC; il solo band-pass
        # conserva la voce e rimuove le frequenze esterne al parlato.
        ffmpeg = subprocess.run([
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(original),
            "-af", "highpass=f=80,lowpass=f=7600",
            "-ar", str(RATE), "-ac", "1", str(cleaned),
        ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=30)
        source = cleaned if ffmpeg.returncode == 0 else original
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(WHISPER.parent)
        result = subprocess.run([
            str(WHISPER), "-m", str(WHISPER_MODEL), "-l", "it", "-nt", "-sns",
            "-t", "4", "-ac", "256", "-bs", "5", "-bo", "5", "--prompt",
            "Ehi Peppe. Ciao Peppe. Che ore sono? Riproduci musica. Peppe basta.",
            "-f", str(source),
        ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=90, env=env, check=False)
        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        text = " ".join(lines)
        text = re.sub(r"\[[^]]*]|\([^)]*\)", "", text).strip()
        return text


def api_json(path: str, payload: dict, timeout: int = 240) -> dict:
    request = urllib.request.Request(
        ASSISTANT + path, json.dumps(payload, ensure_ascii=False).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def speak(text: str) -> None:
    if not text:
        return
    with tempfile.TemporaryDirectory(prefix="peppe-tts-") as td:
        wav = Path(td) / "reply.wav"
        request = urllib.request.Request(
            ASSISTANT + "/api/speak",
            json.dumps({"text": text[:1500]}, ensure_ascii=False).encode(),
            {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=120) as response:
            wav.write_bytes(response.read())
        play = ["pw-play", "--volume=1.0"]
        if SPEAKER_SINK:
            play.append(f"--target={SPEAKER_SINK}")
        subprocess.run([*play, str(wav)], timeout=180, check=False)
    # Scarta eco residuo e riapre il microfono pulito al ciclo successivo.
    time.sleep(0.45)


def open_browser(url: str) -> bool:
    """Apre soltanto URL HTTPS generati dall'assistente locale."""
    if not url.startswith("https://") or len(url) > 2000:
        log("apertura browser rifiutata: URL non consentito")
        return False
    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        log("ricerca aperta nel browser")
        return True
    except OSError as exc:
        log(f"apertura browser non riuscita: {exc}")
        return False


def main() -> None:
    SetLogLevel(-1)
    log("caricamento rilevatore italiano")
    model = Model(str(VOSK_MODEL))
    history: list[dict] = []
    active_until = 0.0
    log("Peppe pronto: di' 'Ehi Peppe' per iniziare e 'Peppe basta' per terminare")
    while running:
        active = time.monotonic() < active_until
        try:
            captured = capture_utterance(model, active)
            if captured is None:
                log("microfono non disponibile, nuovo tentativo tra 3 secondi")
                time.sleep(3)
                continue
            audio, fast_text = captured
            if not audio:
                if active:
                    active_until = 0
                    history.clear()
                    log("sessione scaduta")
                continue
            audio_seconds = len(audio) / (RATE * 2)
            if active and is_stop(fast_text):
                speak("Va bene, a presto.")
                active_until = 0
                history.clear()
                log(f"sessione chiusa da Vosk: {fast_text!r}")
                continue
            started = time.monotonic()
            text = transcribe(audio)
            log(f"audio {audio_seconds:.2f}s; trascrizione "
                f"({time.monotonic() - started:.2f}s): {text!r}; Vosk: {fast_text!r}")
            if not text:
                continue
            if is_stop(text):
                speak("Va bene, a presto.")
                active_until = 0
                history.clear()
                log("sessione chiusa da 'Peppe basta'")
                continue
            if not active:
                # Anche la prima richiesta viene accettata soltanto quando i
                # due riconoscitori concordano; con il filtro WebRTC Vosk è
                # la trascrizione primaria e Whisper la verifica indipendente.
                command, agreement = select_command(text, fast_text)
            else:
                command, agreement = select_command(text, fast_text)
            if len(normalize(command).split()) < 2:
                log(f"comando scartato per bassa confidenza: accordo={agreement:.2f}")
                # Una sola breve opportunità di ripetere, senza contaminare
                # cronologia o prolungare indefinitamente la conversazione.
                active_until = max(active_until, time.monotonic() + 7)
                speak("Non ho capito. Ripeti più vicino al portatile.")
                continue
            response = api_json("/api/chat", {
                "message": command, "history": history, "voice": True})
            answer = str(response.get("answer") or response.get("error") or
                         "Non sono riuscito a rispondere.")
            open_url = response.get("open_url")
            if isinstance(open_url, str) and not open_browser(open_url):
                answer = "Non sono riuscito ad aprire il browser."
            history.extend([{"role": "user", "content": command},
                            {"role": "assistant", "content": answer}])
            history = history[-4:]
            log(f"risposta: {answer[:240]!r}")
            speak(answer)
            active_until = time.monotonic() + ACTIVE_SECONDS
        except (OSError, subprocess.SubprocessError, urllib.error.URLError, ValueError) as exc:
            log(f"errore recuperabile: {exc}")
            time.sleep(2)


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    main()
