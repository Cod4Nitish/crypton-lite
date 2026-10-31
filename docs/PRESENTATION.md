# Presentation plan: Crypton Lite (2 minutes + Q&A)

Judging slot: 14:00-14:45. Submit repo link + demo video **before 14:00**.

## Pehle (setup, 5 min)
- [ ] Charger lagao. Ollama chal raha ho (`ollama list`).
- [ ] Server: `.venv\Scripts\python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000`
- [ ] http://localhost:8000 kholo, Ctrl+Shift+R.
- [ ] **Prepare demo (sample data)** do baar dabao. Phir "list my tasks" bhejo (model warm).
- [ ] Wispr Flow install, mic permission, ek baar bolke test.
- [ ] `.env` me `ANAKIN_API_KEY` ho, tabhi web search dikhao. Nahi ho to wo step skip karo.
- [ ] Backup: demo video pehle se record karke rakho. Wifi fail ho to wahi chalao.

## Kaun kya bolega (2 min)
| Time | Dikhao | Bolo |
|---|---|---|
| 0:00 | Problem | "Hath busy hote hain, aur cloud assistants hamare private documents bahar bhejte hain." |
| 0:15 | Perf tab | "4-bit model, 3.1 GiB, 6 GB GPU par local chalta hai. Ye measured numbers hain." |
| 0:30 | **Wispr Flow se bolo:** "Create preparation tasks based on the event agenda document." Enter. (8-16 s lagte hain, tab tak Timeline samjhao) | "Wispr Flow sirf bolne ko text banata hai. Agent tab shuru hota hai jab main Enter dabata hoon." |
| 1:00 | Reply ke `[1]` chip par click, Sources tab | "Har jawab ke saath citation aur page number hai. Agent kuch invent nahi karta." |
| 1:15 | **Wispr se bolo:** "Search the web for the latest Wispr Flow news." (key ho tab) Timeline me `web_search` | "Live web research Anakin.io se. Documents local, sirf research online." |
| 1:35 | "Delete the task rehearse the demo" → Confirm card | "Delete jaisa kaam bina meri manzoori ke nahi hota." |
| 1:50 | Page refresh | "Sab SQLite me hai, local." |

## Teeno sponsor tools par sach bolo
- **Wispr Flow:** voice input. Mic se jo asli me chala wahi bolo.
- **Anakin.io:** `web_search`/`scrape_url`. Sirf tab "live" bolo jab key ke saath asli jawab dekha ho.
- **GenieX:** "Hamare laptop par Intel+NVIDIA hai, GenieX ko Snapdragon chahiye. Agent OpenAI-compatible endpoint se jud sakta hai, par Snapdragon par abhi test nahi hua." Jhooth mat bolna.
- **"No duplicates" tab hi bolo jab same command dobara chalake dikha do.** Same command par model naye alag titles ke tasks bana sakta hai.

## Judges ke sawal (taiyar jawab)
| Sawal | Jawab |
|---|---|
| Local kyun? | Documents aur tasks laptop se bahar nahi jate. Sirf voice transcription aur web research network use karte hain. |
| 4B model se galti hogi? | Isliye tools Pydantic se validate hote hain, delete me confirmation hai, aur trace me har step ka time dikhta hai. Evidence na mile to agent mana kar deta hai. |
| Quantization? | Q4_K_M, ~62 tok/s. Q4 vs Q8 comparison nahi hai, kyunki doosra variant install nahi tha. |
| Pehle se bana code? | Seedha bolo: project event se pehle shuru hua tha; event me Anakin skill, duplicate guard, docs jode. Rules organizers se confirm karo (unverified). |
| Agent kya kar sakta hai? | Tasks, document Q&A, notes, web research. Har skill ke apne tools hain. |

## Agar kuch fail ho
| Problem | Karo |
|---|---|
| Voice nahi chala | Type karo, bolo "voice cloud hai, agent local". |
| Ollama down | `ollama serve`, header ka dot dekho. |
| Anakin error | Error dikhao: "key/credit na ho to agent saaf batata hai, invent nahi karta." |
| Pehla jawab slow | Model cold tha; pehle warm karo. |
| UI purana | Ctrl+Shift+R. Data ganda ho to **Prepare demo**. |

Repo: https://github.com/Cod4Nitish/crypton-lite
