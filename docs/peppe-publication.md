# Peppe publication — 12 October 2026

The English article presents Peppe's hardware-reuse and local-first goals,
measured Italian speech results, the MX250 GPU qualification, and the current
prototype's capability and privacy boundaries.

- [WordPress: Meet Peppe — Local Voice, Old Hardware, and a Plan to Replace Alexa](https://ccancellieri.wordpress.com/2026/10/12/meet-peppe-local-voice-old-hardware-and-a-plan-to-replace-alexa/)
- [LinkedIn announcement](https://www.linkedin.com/feed/update/urn:li:activity:7515471941391233026/)
- [Concept illustration](https://ccancellieri.wordpress.com/wp-content/uploads/2026/10/peppe-local-assistant-hero.png)
- [Earlier Alexa-to-Raspberry Pi light-control video](https://www.youtube.com/shorts/a4J8do0zlt4)

The illustration is AI-generated and depicts the intended experience, not a
photograph or evidence of completed integration. Both publications link the
hardware goals to measured results and distinguish implemented tools from
physical relay and Echo speech-delivery work still requiring qualification.

## Evidence and decisions

- [Speech comparison](benchmarks/2026-10-12/README.md): Whistle, Parakeet CPU
  and resident Whisper Turbo, with raw predictions and limitations.
- [GPU qualification](benchmarks/2026-10-12/parakeet-gpu/README.md): real hybrid
  CUDA execution, but slower and more host RAM than the earlier CPU setup.
- [Hardware reuse overview](peppe-hardware-reuse.md): capacity goals,
  capabilities and remaining tests.
- [MiniCPM comparison](../evaluation-minicpm.md): historical LLM trial;
  faster inference did not establish acceptable Italian or command quality.

Whisper remains deployed. The speech experiments did not execute relay actions
or change the production model. A fully offline assistant remains the target;
the checked dialogue profile uses OmniRoute, while Spotify, web searches and
optional remote providers require external services. Disabled Echo microphones
do not make the Echo platform or Spotify cloud-free.

Next qualification work: real microphone and bilingual regression tests,
silence/VAD and wake/stop rejection, background audio, physical relay mapping,
and combined local LLM/ASR residency within the 4 GB VRAM budget.
