# Team Guide: Crypton Lite me kya use hua hai aur kaise

Event: CRYPTON, Speed of Thought (WeMakeDevs, 31 Oct 2026). Submission deadline: **2:00 PM**.
Judging ke liye teen tools ka meaningful use dikhana hai: Wispr Flow, Anakin.io, GenieX.

## Project kya karta hai
Ek local AI agent. Aap bolke ya type karke command dete ho, wo tasks banata hai, uploaded PDF se
page-numbered citations ke saath jawab deta hai, aur ab live web par research bhi karta hai.
Model laptop par chalta hai (Ollama, qwen3.5:4b), data SQLite mein rehta hai.

## Teen sponsor tools ki sach me status
| Tool | Kaise use hua | Status |
|---|---|---|
| **Wispr Flow** | Voice se command dena. Wispr bolne ko text banata hai, text chat box me aata hai, Enter dabane par agent chalta hai. Wispr khud agent nahi chalata. | Setup/docs ready (`docs/WISPR_FLOW_WORKSHOP.md`). **Asli mic se abhi test nahi hua.** |
| **Anakin.io** | `web-research` skill: `web_search` (AI web search) aur `scrape_url` (page ka text). Code: `backend/anakin.py`, `skills/web-research/SKILL.md`. | Code + mocked tests pass (45/45). **Asli API key ke saath live test baaki hai** (bina key ke search 401, scrape 402 aaya tha). |
| **GenieX** | Abhi **use nahi hua.** GenieX sirf Qualcomm Snapdragon hardware par chalta hai. Hamare laptop me Intel + NVIDIA hai. | Snapdragon device mile to `geniex serve` ka OpenAI-compatible endpoint backend se jod sakte hain. Nahi mila to README me honestly likhna hai ki chala nahi. |

Judges ko jhooth mat bolna: jo tool chala nahi, use "used" mat likhna.

## Local chalane ka tareeka
```powershell
git clone https://github.com/Cod4Nitish/crypton-lite
cd crypton-lite
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
ollama pull qwen3.5:4b
ollama pull nomic-embed-text
copy .env.example .env      # phir .env me apni ANAKIN_API_KEY daalo
.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```
Browser me http://localhost:8000 kholo, **Prepare demo (sample data)** do baar dabao, phir ek baar
"list my tasks" bhejke model warm karo (pehla jawab ~7 s leta hai).

## Anakin key kaise lein
1. https://anakin.io/signup par sign up (card nahi chahiye, 300 credits).
2. Dashboard me code `SOT26` redeem karo.
3. Key `.env` me `ANAKIN_API_KEY=ak-...` likho. **Key chat, code ya git me kabhi mat daalo.** `.env` gitignored hai.

## Demo commands (Wispr Flow se bol ke try karo)
1. "Create preparation tasks based on the event agenda document." (8-11 s lagta hai)
2. "Search the web for the latest Wispr Flow news and save a note." (Anakin key chahiye)
3. "Delete the task rehearse the demo." (confirmation card aata hai, Confirm dabao)

Timeline tab me dikhega kaunsa skill/tool chala aur kitne ms lage. Judges ko ye dikhana: "ye measured hai."

## Kaam baant ne ke liye
- [ ] Wispr Flow install + mic se poora demo ek baar chalake dekhna
- [ ] Anakin key daalke `web_search` aur `scrape_url` live verify karna
- [ ] Organizers se poochna: Snapdragon device milega? Pre-built code allowed hai?
- [ ] README me "har tool ne build me kya contribute kiya" likhna (sirf naam kaafi nahi)
- [ ] 2:00 PM se pehle submit karna

## Git workflow
`main` se branch banao (`git checkout -b feature/naam`), tests chalao (`.venv\Scripts\python -m pytest -q`),
phir pull request kholo. Repo private hai; owner ko apna GitHub username do taaki collaborator add ho.

## Aur padhne ke liye
`PROJECT_STATUS.md` (pass/fail), `EVENT_RUNBOOK.md` (demo script), `docs/ARCHITECTURE.md`.
