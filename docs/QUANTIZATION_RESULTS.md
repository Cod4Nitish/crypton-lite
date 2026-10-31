# Quantization benchmark results

Generated 2026-10-31T01:54:23+00:00 by `benchmarks/quantization_bench.py`. All values are measured on this machine; nothing is estimated.

- Machine: Intel64 Family 6 Model 191 Stepping 2, GenuineIntel | GPU: NVIDIA GeForce RTX 4050 Laptop GPU, 6141 MiB, 610.74 | Ollama 0.40.2
- Settings: `{"temperature": 0, "seed": 42, "num_ctx": 4096, "num_predict": 128}`, `think=false`, 3 trials x 3 identical tests per model

## Comparison status

- **qwen2 7.6B**: only `qwen2.5-coder:7b` installed. **No same-model quantization comparison is possible.** Missing: another quantization of the same model (for example a Q8_0 build). Nothing was downloaded.
- **qwen35 4.2B**: only `qwen3.5:4b` installed. **No same-model quantization comparison is possible.** Missing: another quantization of the same model (for example a Q8_0 build). Nothing was downloaded.

## Per-model results (baseline, not a quantization comparison unless stated above)

| Model | Quant | File GiB | Cold load s | Prompt tok/s | Gen tok/s | Median latency s | Max latency s | Ollama VRAM MiB | Ollama resident MiB | GPU peak delta MiB | Quality |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen2.5-coder:7b | Q4_K_M | 4.36 | 16.254 | 555.3 | 25.0 | 0.38 | 16.793 | 3992 | 4886 | 0 | 9/9 |
| qwen3.5:4b | Q4_K_M | 3.1 | 7.319 | 670.5 | 62.0 | 0.3 | 7.691 | 2985 | 2985 | 3733 | 9/9 |

Quality by test: qwen2.5-coder:7b: {'arithmetic': '3/3', 'extraction': '3/3', 'tool-selection': '3/3'}; qwen3.5:4b: {'arithmetic': '3/3', 'extraction': '3/3', 'tool-selection': '3/3'}

## Caveats

- Different models (e.g. a 4B vs a 7B) differ in more than quantization; their rows must not be read as a quantization effect.
- `GPU peak delta` is whole-GPU memory growth sampled every 150 ms and can include other processes. `Ollama VRAM` comes from `/api/ps` after the run.
- Quality is 3 tiny deterministic checks; it detects breakage, not subtle quality loss. Small sample, no statistical claims.
- Re-run to reproduce; numbers vary with thermal state and background GPU load.
