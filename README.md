# Peppe — Local AI Assistant

Peppe is a lightweight, local-first voice and text assistant for Linux laptops.
It combines a locally hosted GGUF language model with speech recognition,
speech synthesis, system tools, and a low-overhead web console.

## Features

- local LLM inference through `llama.cpp`;
- progressive NDJSON response streaming with adaptive fast/reasoned profiles;
- bounded conversation history and prompt-prefix caching for low latency;
- Italian wake-word and voice-command support;
- optional local text-to-speech feedback;
- an integrated console for chat, recognized speech, logs, model details, and
  resource usage;
- user-level `systemd` services;
- self-tests, model evaluation, performance tuning, and rollback scripts;
- privacy-oriented defaults: the web services bind to localhost and model
  binaries are not stored in the repository.

## Repository layout

- `local-assistant/` — assistant, voice listener, web console, tests, and user
  services;
- `models/` — model metadata only; large model binaries are ignored;
- `local-ai-llama.service` — example `llama.cpp` server unit;
- `admin-*.sh` — optional system-tuning and rollback helpers.

## Getting started

Peppe is designed to run cleanly on modest Linux laptops (tested on an Intel i7 with discrete NVIDIA MX250 4 GB VRAM) under `~/.local/share/local-ai`.

### Architecture Overview

```
+---------------------------------------------------------------------------------+
|                                 PEPPE RUNTIME                                   |
|                                                                                 |
|  [ Microphone ] ---> ( Silero VAD / Vosk ) ---> [ Wake Word: "Ehi Peppe" ]      |
|                                                          |                      |
|                                                          v                      |
|  [ NVIDIA MX250 GPU (4 GB VRAM) ]                                               |
|  +-------------------------------------+  +----------------------------------+  |
|  | Whisper Turbo Server (Port 18183)   |  | llama-server: Liquid LFM2.5 1.2B |  |
|  | ~926 MiB resident VRAM              |  | ~746 MiB resident VRAM           |  |
|  | Transcribes Italian speech in ~1.2s |  | Generates at 52.2 tokens/sec     |  |
|  +-------------------------------------+  +----------------------------------+  |
|                                                          |                      |
|                                                          v                      |
|  [ Python Assistant Engine ] <---------------------------+                      |
|  | - Deterministic tool execution (Web research, Spotify, local time, status)   |
|  | - Resilient voice-stop listener ("Peppe basta", "Hey Peppe basta")           |
|                                                          |                      |
|                                                          v                      |
|  [ Piper TTS Engine ] ---> [ Speaker / PulseAudio / PipeWire ]                  |
+---------------------------------------------------------------------------------+
```

### Quick Setup: Running with Liquid LFM2.5 (100% Offline)

#### 1. Download the Liquid LFM2.5 Model
Download the compact GGUF quantization (~664 MB) into your models directory:
```bash
mkdir -p ~/.local/share/local-ai/models
curl -L -o ~/.local/share/local-ai/models/LFM2.5-1.2B-Instruct-QAD-Q4_0.gguf \
  https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF/resolve/main/LFM2.5-1.2B-Instruct-QAD-Q4_0.gguf
```

#### 2. Install and Start the Systemd Services
Copy the provided unit file to your user systemd configuration:
```bash
mkdir -p ~/.config/systemd/user
cp local-ai-llama.service ~/.config/systemd/user/local-ai-llama.service

systemctl --user daemon-reload
systemctl --user enable --now local-ai-llama.service
systemctl --user restart local-ai-assistant.service local-ai-peppe.service
```

#### 3. Test the Assistant
Verify that the services are active and test text or voice responses:
```bash
# Text API verification
curl -s -X POST http://127.0.0.1:8090/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Ciao Peppe, chi sei?"}'

# Test web research grounding
curl -s -X POST http://127.0.0.1:8090/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Cerca le ultime notizie sulla Luna", "voice": true}'
```

Speak into your microphone:
- **Wake:** *"Ehi Peppe, che ore sono?"*
- **Research:** *"Ehi Peppe, cerca notizie sul meteo a Milano"*
- **Stop:** *"Peppe basta"* or *"Hey Peppe basta"*

See [`local-assistant/README.md`](local-assistant/README.md) for full component, audio device routing, and security details.

## Models and third-party software

The [hardware reuse overview](docs/peppe-hardware-reuse.md) describes Peppe's
capabilities, measured RAM/VRAM tradeoffs, prototype boundaries and soft
real-time interaction goals.

See the [Italian ASR comparison](docs/benchmarks/2026-10-12/README.md) for
measured Whistle and Parakeet CPU/CUDA results against resident Whisper Turbo GPU,
including raw predictions, short-command latency and silence-rejection limits.

The [MiniCPM laptop report](evaluation-minicpm.md) and
[summary](final-evaluation-summary.md) document the earlier language-model
comparison. MiniCPM5-2B was faster and used less VRAM in that trial, but failed
Italian quality and command-format checks; it was not adopted.

See the [publication record](docs/peppe-publication.md) for the English article,
LinkedIn post, illustration and evidence links.

No model weights or third-party binaries are distributed by this repository.
Download them from their respective publishers and review their licenses and
acceptable-use terms independently. The Apache-2.0 license of this project does
not change the license of a model, dataset, system package, or external tool.

## Security and privacy

Review every administrative script before running it. The included services
are configured for local use, but remote-access settings and host-specific
paths remain the operator's responsibility. Never commit credentials or local
environment files.

## License

Licensed under the [Apache License 2.0](LICENSE).

Unless required by applicable law or agreed to in writing, software distributed
under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
CONDITIONS OF ANY KIND, either express or implied.
