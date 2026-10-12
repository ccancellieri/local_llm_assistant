# Parakeet INT8 on the MX250: CUDA qualification

CUDA execution worked, but this configuration was slower and used more host
RAM than the earlier CPU trial. No production service or model was changed.

Same pinned model, six FLEURS Italian clips and eight synthetic commands as
the [CPU comparison](../README.md). ONNX Runtime GPU 1.26.0, onnx-asr 0.12.0,
Python 3.14, CUDA 12 libraries and cuDNN 9; MX250 Pascal compute capability 6.1.
Default GPU preprocessing failed at a cuDNN convolution with `no kernel image
is available for execution on the device`. NumPy preprocessing on CPU allowed
the encoder and decoder to run with CUDA followed by CPU fallback providers.

| Measurement | Earlier CPU trial | Hybrid CUDA trial |
|---|---:|---:|
| Warm median | 0.766 s | 1.071 s |
| Warm p95 | 1.137 s | 1.611 s |
| Peak process RSS | 1.36 GiB | 1.64 GiB |
| Errors per 113-word warm pass | 4 / 4 / 4 | 4 / 4 / 4 |
| Eight synthetic commands | 8/8 | 8/8 |
| Command median | 225 ms | 402 ms |

One first pass and three warm passes; model load 2.775 s. Independent normalized
word-distance scoring verified all 24 long-speech and eight command rows.
Digital silence still returned “Thank you.”. Equal error totals do not imply
identical predictions. No microphone or relay actions were used.

A separate provider profile recorded 2,896 CUDA / 999 CPU encoder node
executions and 1,800 CUDA / 288 CPU decoder executions. This proves actual CUDA
work; provider availability alone would not. Node counts are not percentages
of computational work, and individual overhead contributions were not isolated.

With the original Whisper server resident, total device VRAM ranged from 929
to 1,367 MiB across 167 samples at 200 ms intervals. The 438 MiB difference is
whole-device occupancy, not an isolated model allocation; shorter peaks could
be missed. Peak GPU utilization was 38%. Original services were restored and
VRAM returned to 929 MiB.

CPU and GPU trials ran separately with different runtime builds. They compare
usable configurations, not a controlled GPU-only acceleration change. Keep
Whisper deployed while qualifying live speech and action rejection.

Evidence: [summary](summary.json), [predictions](results.json),
[commands](command-results.json), [provider and VRAM summary](provider-profile-summary.json),
[VRAM samples](vram-samples.csv).
Runtime reference: [ONNX Runtime CUDA compatibility](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
