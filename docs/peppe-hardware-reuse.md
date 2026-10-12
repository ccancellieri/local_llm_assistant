# Peppe: giving an old laptop a second life as a voice assistant

Peppe's goal is to reuse existing hardware well: an Intel i7-10510U laptop,
16 GB of system RAM and a discrete NVIDIA MX250 with 4 GB of VRAM. The useful
question is how to allocate speech, dialogue and tools so the laptop remains
available for other work, rather than maximizing a single benchmark score.

The tested resident Whisper Turbo configuration used approximately 367 MiB
host-process RSS and 929 MiB total device GPU memory. The tested Parakeet CPU
process peaked at approximately 1.36 GiB RSS. These are different process and
device measurements, not a controlled whole-system memory saving. Moving ASR to
VRAM still requires host RAM; the OS, browser and assistant also use memory.
The objective is to preserve more of the 16 GB capacity, not claim all of it is
free. Concurrent local LLM and GPU ASR residency within 4 GB is not yet qualified.

## Capabilities and evidence boundaries

| Capability | Implementation / evidence | Remaining qualification |
|---|---|---|
| Voice conversation and questions | Wake/session listener, streamed chat, local speech recognition and Piper synthesis; backend can be llama.cpp or an explicitly configured gateway | Real microphone accuracy and complete turn p50/p95 |
| Internet search and grounded answers | Search, public-page retrieval and links; explicit browser-search routing | Network/tool latency varies; this is an online capability |
| Spotify and Alexa/Echo devices | Spotify Web API control, search/play/transfer, authentication and controllable Echo discovery verified on the laptop prototype | Actual speaker playback is not established by the ASR tests; Alexa is a Spotify Connect destination, not a general TTS transport |
| Stop, pause and confirmation | Cancellable turn worker, wake validation, stop orders and yes/no flow in the laptop prototype | Physical echo/barge-in and background-video tests |
| Console and diagnostics | Voice/text UI, speech-device selection, model/resource status and service controls | Host-specific setup and documentation alignment |
| Raspberry Pi relay switches | Separate Zero W prototype recognizes logical kitchen/bedroom/table targets | GPIO/channel mapping, relay actuation, rejection reliability and integration with the laptop are pending |

The published main branch and the evolving laptop prototype are at different
stages. The original local model profile is Qwen3 4B GGUF through llama.cpp.
The later laptop dialogue configuration uses an explicitly selected gateway;
local speech processing does not imply an entirely offline assistant. No local
LLM was enabled by the ASR experiments.

## Measured speech tradeoffs

See the [full ASR comparison](benchmarks/2026-10-12/README.md), including raw
transcripts, fixed model revisions, scoring, repeated runs and limitations.

| Paired Parakeet/Turbo test | Parakeet v3 INT8 CPU | Whisper Turbo Q5 GPU |
|---|---:|---:|
| Six FLEURS Italian clips, warm median | 0.766 s | 1.462 s |
| Warm p95 | 1.137 s | 1.675 s |
| Strict word differences per 113-word pass | 4 | 1 |
| Eight synthetic commands, exact transcripts | 8/8 | 8/8 |
| Synthetic command median | 225 ms | 1.230 s |

Two Parakeet differences were equivalent number forms. Both tested negations
were retained. Parakeet's digital-silence result was “Thank you.”, so adoption
requires speech-activity and command validation. Whistle with keyword hints
previously achieved 7/8 synthetic commands at 80 ms, but was less accurate and
slower on the longer FLEURS clips. Synthetic and clean read speech cannot
establish live interaction quality.

## Soft real-time interaction

The target is responsive interaction with bounded cancellation and clear
feedback. ASR duration is only one stage: end-of-speech detection, chat/tool
execution, TTS and playback all affect perceived delay. Earlier stage logs
showed approximately 1.2–1.5 s ASR and about 2 s simple chat, with some tool
requests taking 5–8 s. Resident Piper shortened a tested synthesis path to
approximately 0.25–0.32 s. These are separate historical observations, not
one measured end-to-end latency or a hard real-time guarantee.

## GPU qualification and privacy goal

The [completed MX250 qualification](benchmarks/2026-10-12/parakeet-gpu/README.md)
proved real CUDA execution using CPU preprocessing and CPU fallback. Default
GPU preprocessing failed on Pascal. The hybrid configuration took a 1.071 s
warm median versus 0.766 s in the earlier CPU run, and peaked at 1.64 GiB host
RSS versus 1.36 GiB. Total VRAM rose from 929 to 1,367 MiB with Whisper still
resident. These separate runtime configurations do not isolate GPU overhead,
but provide no measured upgrade. Whisper remains deployed; real speech,
wake/stop, background audio and bilingual regressions remain pending.

The goal is to replace Alexa's listening and light-control path with local
speech processing, a local dialogue model and bounded relay commands. The
owner reports that Echo microphones are disabled in his setup. Keeping Echo
devices for output does not make Spotify, Echo services, web search or remote
AI offline. General Echo delivery of locally generated speech is unqualified.
The current dialogue profile uses OmniRoute while the local llama.cpp service
is stopped; it is a hybrid prototype. Optional remote providers require an
explicit privacy boundary and remain subject to availability and terms.

The [earlier Alexa-to-Raspberry Pi light-control video](https://www.youtube.com/shorts/a4J8do0zlt4)
shows the previous arrangement. Peppe's physical relay integration is a goal,
not an outcome of the speech benchmarks.

For Raspberry Pi Zero W, the physical limit is 512 MB and ARMv6. The measured
Parakeet CPU footprint rules out this configuration there. The relay prototype
remains a separate bounded experiment, with no actuation from these benchmarks.
