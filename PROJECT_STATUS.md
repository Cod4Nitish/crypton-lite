# PROJECT STATUS (31 Oct 2026)

## PASS / FAIL
| Area | Result | Evidence |
|---|---|---|
| Backend tests (offline + live Ollama) | **PASS** 44/44 | `pytest -q` |
| Frontend typecheck + build | **PASS** | `tsc -b`, `npm run build` |
| SQLite persistence | **PASS** (fresh-connection test) | `test_readiness.py` |
| Duplicate task prevention | **PASS** | `test_readiness.py` |
| Bounded LLM retry (1 retry, transport errors only) | **PASS** | `test_readiness.py` |
| Tool failure reported honestly, not retried | **PASS** | `test_readiness.py` |
| Real timing (llm_ms / tool_ms) | **PASS** | response `timing` field |
| Demo reset with labelled sample data | **PASS** (API, live) / **UNVERIFIED** (button in browser) | tests; UI not clicked |
| RAG citations with page numbers | **PASS** | `test_live_rag.py` |
| Quantization benchmark | **PASS** (script and real results) | `benchmarks/quantization_results.json` |
| Q4_K_M vs Q8_0 comparison | **FAIL / not possible**: no second variant installed, nothing downloaded | `QUANTIZATION_RESULTS.md` |
| Model Performance panel | **PARTIAL**: existing Perf tab fed by real benchmark data via `/api/bench/results`. **Server must be restarted** to pick it up; not checked in browser | `backend/main.py` |
| Voice (Wispr Flow / browser mic) with real microphone | **UNTESTED**: needs a human and internet | manual |
| Browser end-to-end click-through | **UNTESTED** | manual |
| Onsite rules on pre-built code | **UNVERIFIED** | ask organizers |

## Late fix (verified live, isolated server on port 8001 with temp DB)
"Create preparation tasks based on the event agenda document" created **no tasks in 4 of 6 runs** (model answered after search). `skills/planning-briefing/SKILL.md` now makes create_task mandatory: **6/6 runs created 3-4 tasks** (backup of the old file was in the temp folder only). Remaining: that command takes about 8-11 s (4 sequential task creations by a 4B model), so say so in the demo and do not rely on it under a time limit. Sample tasks were renamed so they do not overlap with agenda tasks.
Also seen: "delete the charge laptop task" matched a different task by fuzzy title; the confirmation card names the exact task, so read it before clicking Confirm.

## Changes made in this session
Backend: duplicate guard (`db.find_duplicate_open`, `tools._create`), LLM retry and timing (`runtime.py`), demo reset (`backend/demo.py`, `POST /api/demo/reset`), benchmark-backed `/api/bench/results`.
Frontend: voice error toasts (`web/src/lib/voice.ts`), chat error handling and "Listening" state, latency breakdown, **Prepare demo** button.
Sample agenda date corrected to Saturday 31 October 2026 (it said 1 November, a Sunday).
Docs: `docs/MODEL_QUANTIZATION.md`, `QUANTIZATION_RESULTS.md`, `WISPR_FLOW_WORKSHOP.md`, `SKILL_WORKFLOW.md`, `ARCHITECTURE.md`, `EVENT_RUNBOOK.md`.
Not changed: git (the folder is not a git repo; no history was touched), existing features, files deleted: none.

## Starter vs competition-specific
Reusable starter: `backend/{runtime,tools,skills,rag,store,db}.py`, `web/src/components/ui/`, skills loader. Competition-specific: `backend/demo.py`, `docs/sample/`, `skills/planning-briefing`, `docs/*`, `benchmarks/`.

## Unresolved demo risks
1. Rules on pre-built code unconfirmed (project was started before the event).
2. Voice needs internet; unverified end to end with a real mic.
3. Cold model load about 7 s: warm up first.
4. 6 GB GPU is shared (4.3 GB was already in use); a 7B model would partly run on CPU.
5. Retrieval threshold was calibrated only on the sample agenda.
6. Server was started before the latest backend edits: restart it.
