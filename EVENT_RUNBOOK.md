# EVENT RUNBOOK: CRYPTON, Speed of Thought (WeMakeDevs, 31 Oct 2026)

## Before leaving home
- [ ] Laptop charger in the bag. Ollama running; models present: `ollama list` (qwen3.5:4b, nomic-embed-text).
- [ ] Start server: `.venv\Scripts\python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`
- [ ] Open http://localhost:8000, hard refresh (Ctrl+Shift+R).
- [ ] Click **Prepare demo (sample data)** twice (second click confirms). Check: 2 `[Sample]` tasks, `SAMPLE-event-agenda.pdf` indexed.
- [ ] Warm the model: send "list my tasks" once (cold load is about 7 s).
- [ ] Install Wispr Flow, allow microphone (needed for the 10:00 workshop).
- [ ] **Confirm the onsite rules** about pre-built code with the organizers. Not verified. Agenda says building starts 10:40.

## Schedule (from the sample agenda, verify against the real one)
09:00 check-in | 09:30 Quantization talk | 10:00 Wispr Flow workshop | 10:40 build phase

## Two-minute judge demo
Problem: people capture tasks while their hands are busy, and cloud assistants send private documents away. User: an event attendee/organizer managing prep tasks from an agenda.

| Time | Do | Say |
|---|---|---|
| 0:00 | Show the Performance tab (Perf): qwen3.5:4b Q4_K_M, about 62 tok/s, 3.1 GiB | "A 4-bit model fits in my 6 GB GPU, so the agent is fast and local." |
| 0:20 | Hold Wispr Flow key: "Create preparation tasks based on the event agenda document." Read text, Enter (takes about 8-11 s, keep talking about the trace) | "Wispr Flow only turns speech into text. The agent starts when I press Enter." |
| 0:50 | Show reply with [1] [2] chips, click one: Sources tab shows doc and page | "Citations are real chunks with page numbers." |
| 1:10 | Open Timeline: route, skill_loaded, llm, tool, final with ms | "This trace is measured, not narrated." |
| 1:30 | Say the same command again | "No duplicate tasks: it says 'already exists'." |
| 1:40 | "Delete the task rehearse the demo" then click Confirm | "Destructive actions need my approval." |
| 1:55 | Refresh the page | "Everything is in SQLite." |

## If something fails
| Symptom | Action |
|---|---|
| Voice fails / no internet | Type the command (toast says so). Say honestly: voice is cloud, the agent is local. |
| Ollama down | Header dot red; run `ollama serve`; chat shows "did not run, nothing changed". |
| Slow first answer | Model was cold. Warm it before the demo. |
| Wrong/stale UI | Ctrl+Shift+R; if still stale, clear site data (service worker). |
| Messy data | **Prepare demo** button. |
| Wrong citation / "insufficient evidence" | Say so; the agent refuses to invent. Re-upload the real agenda. |

## Honest claims
Local: model, RAG, tools, SQLite. Not local: Wispr Flow and browser dictation. No Q4 vs Q8 comparison exists on this machine (only Q4_K_M models are installed).
