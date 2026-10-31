# Wispr Flow workshop notes (10:00-10:40, "Build Faster with Wispr Flow")

**What Wispr Flow is:** a voice-to-text input tool. It types the transcribed words into whatever text field has focus. It does **not** run CRYPTON's agent or tools. The agent step happens only after the text is sent to FastAPI. Wispr Flow is a cloud service, so voice dictation needs internet. Do not call the full voice workflow offline.

## Setup (do before the workshop, as the agenda asks)
1. Install Wispr Flow from the official site and sign in.
2. Allow **microphone** permission when asked (Windows: Settings, Privacy and security, Microphone; also allow desktop apps).
3. Pick the right input device in Wispr Flow settings and do its mic test.
4. Learn the hotkey (hold to talk). Click into CRYPTON's text box first so the text lands there.

I could not verify Wispr Flow's current menus or hotkey from this machine, so follow its in-app onboarding for exact steps.

## Dictating into CRYPTON
1. Open `http://localhost:8000`, click the message box.
2. Hold the Wispr Flow hotkey, speak, release. Text appears in the box.
3. **Read it, fix mistakes, then press Enter.** Do not send blind.
4. Backup input: the **Mic** button in CRYPTON (browser dictation, Chrome/Edge, needs internet). Last resort: type.

## What happens after Enter (verified path)
1. Browser sends the text to `POST /api/chat` (FastAPI).
2. Router picks a skill; the local Ollama model (`qwen3.5:4b`) picks an approved tool.
3. Pydantic validates the arguments; the tool runs against SQLite or the vector store.
4. The UI shows the reply, the tool card and the real trace (timings from the server).

Automated proof of steps 1-4 with a scripted model is in `tests/` and live runs with the real model are in `tests/test_live_ollama.py`. The microphone and Wispr Flow step itself cannot be automated here: **test it manually**.

## Prompting techniques that work with this agent
- One intent per sentence: "Add a high priority task to charge the laptop."
- Say the verb first: add, complete, delete, list, summarize, plan, remember.
- Say dates as words or ISO: "tomorrow", "2026-11-01".
- Refer to documents explicitly: "based on the event agenda document".
- Deletes always ask for confirmation, so say "delete the charger task" and click Confirm.

## Voice-assisted coding workflow
Dictate intent and structure, not syntax: "Add a test that creating the same task twice returns the existing one." Then review the generated code yourself; dictated code and AI output both need reading and a test run.

## Common transcription failures and fixes
| Problem | Fix |
|---|---|
| Names or terms misheard ("Crypton", "Ollama", "Chroma") | Spell once, correct in the box, or use the Wispr Flow dictionary if available. |
| Text appears in the wrong window | Click the CRYPTON box first. |
| Nothing appears / mic error | Check mic permission and input device; check internet. |
| Filler words or run-ons | Speak shorter sentences; edit before sending. |
| Numbers/dates wrong | Read the box; say "2026-11-01" or retype. |
| No internet at the venue | **Type the command.** CRYPTON's text box and the local model work without internet. |

## Manual fallback (always available)
Type into the same box. CRYPTON also shows toasts when browser voice fails ("Voice transcription failed... Type your command instead"). Typed and spoken commands take the exact same path after Enter.
