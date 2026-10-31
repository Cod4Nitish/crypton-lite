# Crypton Lite

A fully local, voice-friendly task and document agent built for **CRYPTON: Speed of Thought** (WeMakeDevs, 31 Oct 2026).
A small quantized model (qwen3.5:4b, Q4_K_M) runs on Ollama, answers questions over your documents with page-numbered citations, and manages tasks through tool calls. Everything is stored in SQLite and runs on a 6 GB GPU.

## Features
- Local LLM agent with tool calling (create / list / delete tasks, with confirmation for destructive actions)
- RAG over uploaded PDFs, with citations that point to the source chunk and page
- Duplicate-task prevention and bounded LLM retry
- Measured timing trace (route, skill, llm, tool, final) for every request
- Skills loaded from `skills/*/SKILL.md`
- Quantization benchmark and Performance tab
- Voice input through Wispr Flow or browser dictation (cloud speech-to-text; the agent itself stays local)

## Requirements
- Python 3.11+
- [Ollama](https://ollama.com) with `qwen3.5:4b` and `nomic-embed-text` pulled
- Node.js (only if you want to rebuild the `web/` frontend)

## Quick start
```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
Open http://localhost:8000, then click **Prepare demo (sample data)** to load sample tasks and the sample agenda.

Frontend rebuild: `cd web && npm install && npm run build`.

## Tests
```powershell
.venv\Scripts\python -m pytest -q
```
The live tests need Ollama running.

## Project layout
| Path | Purpose |
|---|---|
| `backend/` | FastAPI app, agent runtime, tools, RAG, SQLite store |
| `web/` | React + TypeScript frontend (Vite) |
| `frontend/` | Static PWA frontend |
| `skills/` | Agent skills (`SKILL.md` per skill) |
| `benchmarks/` | Quantization benchmark script and results |
| `docs/` | Architecture, quantization, skill workflow, Wispr Flow notes |
| `tests/` | Offline and live tests |

See also [PROJECT_STATUS.md](PROJECT_STATUS.md) and [EVENT_RUNBOOK.md](EVENT_RUNBOOK.md).

## Collaborating
1. Clone the repo and create a branch: `git checkout -b feature/your-change`
2. Run the tests before pushing.
3. Open a pull request into `main`.
