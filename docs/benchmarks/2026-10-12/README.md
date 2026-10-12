# Italian speech recognition on a laptop: Whistle, Parakeet and Whisper Turbo

Parakeet v3 INT8 on CPU is a promising alternative for short Italian voice
commands. It matched all eight synthetic command transcripts and returned them
in a median 225 ms, compared with 1.230 s for resident Whisper Turbo on GPU.
Keep the current deployment until microphone quality and silence rejection are
qualified: Parakeet returned “Thank you.” for two seconds of digital silence.

These are ASR measurements, not end-to-end assistant response times. No model
was adopted or deployed by this experiment.

## Hardware and runtime

- Intel Core i7-10510U, four cores/eight threads, 16 GB RAM.
- NVIDIA GeForce MX250, 4 GB VRAM, Pascal compute capability 6.1.
- Ubuntu 26.04.1, Python 3.14.
- Baseline: resident whisper.cpp Large V3 Turbo Q5, context 768, four CPU
  threads, beam size and best-of 5, Italian forced explicitly.
- Parakeet: onnx-asr 0.12.0, ONNX Runtime 1.31.0, NumPy 2.5.4,
  CPUExecutionProvider, four intra-op threads and one inter-op thread, INT8
  encoder and decoder. Language detection is automatic.
- Whistle: official Linux x86-64 library, full speech depth, Italian forced.
  Default native worker policy; effective thread count was not measured.

Both candidate models stayed resident during their timed runs. The listener
was suspended while measuring and restored afterward. No microphone capture,
playback, chat or tool execution occurred. Other desktop services remained
running. GPU memory stayed occupied by the baseline during the CPU tests.

## Public Italian read speech

Six frozen [Google FLEURS](https://huggingface.co/datasets/google/fleurs)
Italian validation recordings, 7.5–13.44 seconds, 113 reference words. Selection:
first six rows in official validation order whose duration was 5–15 seconds.
Dataset revision `8e74c3a7c16ffd851ceb9d50012daa64122d6734`; CC BY 4.0.
SHA-256 checks against the original frozen manifest passed before inference.
References and predictions are retained in the result files.

Each comparison ran one first pass and three warm passes of six files per
engine. Whistle and Parakeet were evaluated in separate comparisons, each
against the resident baseline.

| Comparison | Model / device | Warm median | Warm p95 | Errors per 113-word pass |
|---|---|---:|---:|---|
| Whistle trial | Whistle CPU | 2.662 s | 3.444 s | 13 / 13 / 13 |
| Whistle trial | Whisper Turbo GPU | 1.482 s | 1.908 s | 2 / 1 / 2 |
| Parakeet trial | Parakeet INT8 CPU | 0.766 s | 1.137 s | 4 / 4 / 4 |
| Parakeet trial | Whisper Turbo GPU | 1.462 s | 1.675 s | 1 / 1 / 1 |

Scoring lowercases, removes accents, replaces punctuation with spaces and
computes word-level Levenshtein distance. Numeric forms are not canonicalized.
Two of Parakeet's four differences were “2” versus “due” and “venti” versus
“20”; the other two were “Sri” versus “Shri” and “baiyan” versus “bhajan”.
The strict WER is therefore 3.54% versus the paired Turbo result of 0.88%.
Ignoring those two numeric spelling differences alone gives 2/113 for Parakeet;
that secondary interpretation does not replace the predefined score.

Parakeet's paired median was 47.6% lower. This is a small clean read-speech
sample, not a representative estimate of Italian conversational accuracy.

## Short synthetic commands

Eight macOS Alice recordings: on/off requests for kitchen, bedroom and table
lights, plus “non accendere la luce cucina” and “non spegnere la luce tavolo”.
One pass per condition, exact normalized transcript scoring; no action was
executed. Synthetic recording provenance: Apple Alice voice, 140 words/minute,
16 kHz mono PCM. Human voice performance is still unmeasured.

| Model / condition | Exact transcripts | Median |
|---|---:|---:|
| Whistle, no hints | 4/8 | 117 ms |
| Whistle, keyword biasing | 7/8 | 80 ms |
| Whisper Turbo, paired Whistle trial | 8/8 | 1.209 s |
| Parakeet INT8 CPU, no hints | 8/8 | 225 ms |
| Whisper Turbo, paired Parakeet trial | 8/8 | 1.230 s |

Whistle keywords: “luce cucina”, “luce camera da letto”, “luce tavolo”,
“non accendere”, “non spegnere”. Its remaining biased error was “Spagni” for
“Spegni”. Both negative requests retained “non” in every tested condition.
Two successful negations do not establish safe action rejection generally.

## Memory, silence and boundaries

Parakeet process peak RSS: 1,425,552 KiB, approximately 1.36 GiB; load time
2.568 s. Whistle diagnostic process sampled approximately 93 MiB and loaded in
22.8 ms. These process figures include Python, native allocations and prepared
audio; Whistle also retained its original model byte buffer.
Whisper process RSS checked after the Whistle run was approximately 367 MiB;
total device GPU memory was 929 MiB. RAM RSS and whole-device VRAM are different
measurements and must not be summed or compared as model-file sizes.

Digital silence returned empty text in Whistle and “Thank you.” in Parakeet.
A constant DC-offset probe returned “Grazie.” in Whistle; this is not a
realistic ambient-noise recording. VAD, wake validation and command validation
must be qualified before either candidate can trigger actions.

One separate Whistle CLI run observed no network syscalls under strace with
telemetry-disable flags. This is one checked execution, not a universal
network-free guarantee. Parakeet loaded local pinned files with hub offline
mode enabled; no cloud recognizer was used.

The subsequent [MX250 GPU qualification](parakeet-gpu/README.md) verified real
CUDA work with CPU preprocessing and fallback. Its 1.071 s warm median and
1.64 GiB peak host RSS were worse than this CPU configuration. Neither a small
model file nor a 4 GB card guarantees faster inference or less host RAM.
Parakeet's measured RAM rules out this configuration on a 512 MB Pi Zero W.

## Reproduction and artifacts

The `whistle/` and `parakeet/` folders contain:

- `artifacts.json`: exact model/runtime download URLs, revisions and hashes.
- `results.json`: all 48 long-speech predictions per comparison, reference
  texts, per-call latency and word-error counts.
- `command-results.json`: the short-command predictions and timings.
- `summary.json`: aggregate latency, versions where captured and silence probes.

Use the pinned versions above, preload the model, prepare 16 kHz mono float PCM
before timing, and replay each frozen clip serially for one first pass and three
warm passes. Call Parakeet through `onnx_asr.load_model` with a local model
directory, `quantization="int8"`, CPUExecutionProvider and the session thread
limits above, then `recognize(pcm, sample_rate=16000)`. Call Whistle's published
`needle_transcribe` C API with language `it`. Compare with the existing resident
Whisper service; include loopback upload/response in its wall timer. Numeric
normalization must match the strict score above.

No weights or source audio are distributed here. FLEURS dataset terms, model
licenses and synthetic voice redistribution terms remain separate.

Sources: [Whistle](https://huggingface.co/Cactus-Compute/whistle),
[Parakeet NVIDIA](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3),
[ONNX conversion](https://huggingface.co/istupakov/parakeet-tdt-0.6b-v3-onnx),
[onnx-asr](https://github.com/istupakov/onnx-asr).
