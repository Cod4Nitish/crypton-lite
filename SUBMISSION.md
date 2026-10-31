# Submission: Crypton Lite (CRYPTON, Speed of Thought)

## One-line pitch
A private, local AI agent you can talk to: it turns an event agenda into preparation tasks, answers from your documents with page-numbered citations, and researches the live web, all driven by voice.

## Problem and user
People capture tasks while their hands are busy (setting up, travelling, on stage), and cloud assistants send private documents away. Crypton Lite is for an event attendee or organizer who wants to speak a command and get real, checkable results while documents and tasks stay on their own laptop.

## What it does
- Voice or typed command → local agent (LangGraph loop, Ollama `qwen3.5:4b`, Q4_K_M, about 3.1 GiB).
- Creates tasks from an uploaded agenda PDF, with duplicate prevention.
- Answers from documents with citations that open the exact source page.
- Destructive actions (delete) need an explicit Confirm click.
- Every request has a measured timeline (route, skill, llm, tool, final, in ms).
- Everything is stored in SQLite and survives refresh.

## How each sponsor tool contributed
| Tool | What it does in this build | Where | Status (honest) |
|---|---|---|---|
| **Wispr Flow** | Voice input: the user holds the Wispr key and speaks, Wispr turns speech into text in the chat box, and pressing Enter starts the agent. Wispr only transcribes; the agent is separate. | `docs/WISPR_FLOW_WORKSHOP.md`, `web/src/lib/voice.ts` | Integration ready (Wispr types into the chat box). Real-microphone run is shown in the presenter's Wispr dashboard recording. |
| **Anakin.io** | `web-research` skill with two agent tools: `web_search` (AI web search) and `scrape_url` (page text). Findings can be saved as notes or turned into tasks. | `backend/anakin.py`, `skills/web-research/SKILL.md`, `tests/test_anakin.py` | Verified live: web search ("best laptop under 50k") and page scrape (example.com) returned real results through the agent. Mocked tests cover error cases. |
| **GenieX** | Not run. GenieX needs Snapdragon hardware; this build ran on Intel + NVIDIA RTX 4050. The agent talks to any OpenAI-compatible local endpoint, which is what `geniex serve` exposes, so it can be pointed at GenieX. | n/a | **Not verified on Snapdragon.** |

## Why local matters
Model, retrieval, tools and database all run on the laptop (6 GB GPU). Only voice transcription (Wispr Flow) and web research (Anakin.io) use the network, by design.

## Evidence
- Backend tests: 62 passing offline (`pytest -q`); frontend typecheck and build pass.
- Real timing, no estimates: see the Timeline tab and `benchmarks/quantization_results.json`.
- Known limits: `PROJECT_STATUS.md`.

## Demo script (2 minutes)
1. Perf tab: model, quantization, tokens/s.
2. Speak: "Create preparation tasks based on the event agenda document." Show tasks and cited sources.
3. Speak: "Search the web for the latest Wispr Flow news and save a note." Show Timeline with `web_search`.
4. Repeat step 2: no duplicates. Delete a task: confirmation card.

## Run it
See `README.md`. Repo: https://github.com/Cod4Nitish/crypton-lite
