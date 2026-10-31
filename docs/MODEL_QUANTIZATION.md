# Model quantization, for CRYPTON's local voice agent

Talk: *Why Model Quantization Matters for Efficient Inference* (Shivay). Numbers marked **[measured]** come from this laptop, see `QUANTIZATION_RESULTS.md`. Everything else is general background.

## Our actual models [measured via `ollama show`]

| Model | Role | Params | Format | Quantization | File | Max context |
|---|---|---|---|---|---|---|
| `qwen3.5:4b` | agent / tool calling | 4.2B | GGUF (llama.cpp runner) | **Q4_K_M** | 3.1 GiB | 262144 |
| `qwen2.5-coder:7b` | installed, not used by CRYPTON | 7.6B | GGUF | **Q4_K_M** | 4.36 GiB | 32768 |
| `nomic-embed-text` | RAG embeddings | 137M | GGUF | **F16** | 0.26 GiB | 2048 |

Hardware: Intel i7-13700HX (16 cores / 24 threads), 15.7 GB RAM, NVIDIA RTX 4050 Laptop **6 GB VRAM** (about 4.3 GB was already used by other programs when we measured), Ollama 0.40.2.

## Number formats

| Format | Bits/weight | Notes |
|---|---|---|
| FP32 | 32 | Training default. 4 bytes per parameter. A 4B model would be about 16 GB. |
| FP16 / BF16 | 16 | Standard inference baseline. About 8 GB for 4B. Nearly lossless vs FP32. |
| INT8 (Q8_0) | about 8.5 | About half of FP16. Quality loss is usually very small. |
| INT4 (Q4_x) | about 4.5-5 | About a quarter of FP16. Visible but often acceptable quality loss. |

Size estimate: `parameters x bits / 8`. Our measured 4.2B model at 3.1 GiB works out to about 6.3 bits/weight on average, because Q4_K_M keeps some tensors at higher precision and the file includes extra tensors (for example embeddings, and a vision tower since it lists `vision`). Do not assume "4-bit = params/2".

## GGUF and llama.cpp quantization

- **GGUF** is llama.cpp's single-file model format: weights, tokenizer and metadata (`general.file_type`) together. Ollama runs GGUF models.
- Quantization works on small blocks of weights, each stored as low-bit integers plus a scale.
- **Legacy types** (`Q4_0`, `Q8_0`): simple block quantization.
- **K-quants** (`Q4_K_M`, `Q5_K_M`...): bigger super-blocks with quantized scales. The `_M` (medium) mix keeps the more sensitive tensors (parts of attention and feed-forward layers) at higher precision. Better quality per byte than `Q4_0`.
- **Q4_K_M vs Q8_0**: Q8_0 is about 1.7-1.9x larger and slower to read from memory, but closer to the original quality. Q4_K_M is the common local sweet spot. **We have no Q8_0 build installed, so we did not measure this difference.**

## Why it matters: memory bandwidth

Token generation reads (almost) all weights once per token. Speed is therefore limited by **memory bandwidth / model bytes**, not raw compute. Fewer bytes per weight means more tokens per second and a model that fits in VRAM at all.

Our measurement shows the "fits in VRAM" effect clearly **[measured]**:
- `qwen3.5:4b` (Q4_K_M): 2985 MiB loaded, entirely on GPU, about **62 tokens/s**.
- `qwen2.5-coder:7b` (Q4_K_M): 4886 MiB needed, only 3992 MiB on GPU (the rest on CPU), about **25 tokens/s**.

Caution: those two are different models, so this is not a pure quantization comparison. It shows what happens when a model does not fully fit in 6 GB.

## Metrics, defined

- **Load duration**: time to read the model into memory. Our cold load of the 4B model was about 7.3 s **[measured]**, so warm it up before a demo (`keep_alive` is 30 min in CRYPTON).
- **Prompt evaluation speed** (prefill): tokens/s while reading the prompt. Compute-bound. About 670 tok/s for `qwen3.5:4b` **[measured]**.
- **Generation speed** (decode): tokens/s while producing the answer. Bandwidth-bound. About 62 tok/s **[measured]**.
- **Total latency**: load + prefill + decode, plus tool time in an agent loop.

## Quality trade-offs

Lower bits add rounding error. Effects tend to show first in long reasoning chains, rare facts, exact formatting, and non-English text, and last in simple tasks. Bigger models tolerate quantization better than small ones. Always test on your own task: our tiny check (arithmetic, time extraction, correct tool plus argument) passed **9/9 for both models [measured]**. That only shows nothing is badly broken; it is far too small to rank quantizations.

## CPU vs GPU inference

- **GPU**: much higher memory bandwidth, so higher tokens/s, but limited by VRAM (6 GB here, shared with the display and other apps).
- **CPU**: uses system RAM (15.7 GB here) so larger models load, but with far lower bandwidth, so slower.
- **Hybrid** (what Ollama did for the 7B): some layers on GPU, rest on CPU. Works, but speed drops toward the CPU speed.

## KV cache and context length

The KV cache stores attention keys/values for every token already processed, so it grows **linearly with context length** and is in addition to the weights. A longer `num_ctx` costs VRAM even if you never fill it. The benchmark uses `num_ctx=4096`. The model's advertised maximum (262144 for `qwen3.5:4b`) is not what you can afford on 6 GB. Smaller contexts also make prefill faster. CRYPTON sends short prompts (one skill plus the last 6 turns), so a small context is enough.

## Why this matters for a voice agent

A spoken command should feel instant. The pipeline is: speech to text, then model, then tool, then answer. Only the model step is under our control. A quantized 4B model that fits in VRAM answers a tool call in about **1.2-1.4 s** and a simple reply in about 0.3 s **[measured]**, fully on this laptop with no per-call cloud cost and no document leaving the machine. A model that spills to CPU is roughly 2.5x slower at generation in our data. Efficient local inference is what makes voice control usable in real time.

Honest limit: Wispr Flow dictation and browser speech recognition are cloud services, so the *whole* voice workflow is **not** offline. Only the model, RAG and tools are local.

## How to reproduce

```
.venv/Scripts/python benchmarks/quantization_bench.py --trials 3
```
To get a real Q4_K_M vs Q8_0 comparison you would need a second build of the same model (for example a `q8_0` tag of `qwen3.5:4b`, a few GB). **Ask before downloading**; it has not been done.
