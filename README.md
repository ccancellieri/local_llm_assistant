# Peppe — Local AI Assistant

Peppe is a lightweight, local-first voice and text assistant for Linux laptops.
It combines a locally hosted GGUF language model with speech recognition,
speech synthesis, system tools, and a low-overhead web console.

## Features

- local LLM inference through `llama.cpp`;
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

The current configuration was developed for Linux with an NVIDIA GPU and uses
paths under `~/.local/share/local-ai`. Hardware devices, account paths, model
names, and service settings may need to be adapted before installation.

See [`local-assistant/README.md`](local-assistant/README.md) for component,
usage, security, and service details.

## Models and third-party software

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
