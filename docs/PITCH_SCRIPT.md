# Pitch script: Crypton Lite (4 speakers, about 1 min 45 s)

Bolne ki speed: aaram se, ~130 words per minute. Har speaker apni lines ek baar zor se padh ke practice kare.
Demo (Speaker 2) ke time Speaker 1 laptop chalaye, Speaker 2 Wispr se bole.

## Setup (pehle)
- App khula ho: http://localhost:8000, browser full screen, terminal band.
- "Prepare demo" ho chuka ho (Advanced → Prepare demo), phir "list my tasks" bheja ho (model warm).
- Calculator band ho. Sound on ho (gaana demo ke liye).

---

## Speaker 1: Problem (0:00 – 0:20)
> Hi, we are team ____ and this is **Crypton Lite**.
> Most of us capture tasks while our hands are busy, and today's cloud assistants send our private documents away to someone else's server.
> Crypton Lite is a private AI assistant that runs on your own laptop and listens to your voice.

*(Speaker 1 laptop Speaker 2 ko de de ya screen ki taraf ishara kare.)*

## Speaker 2: Live voice demo (0:20 – 1:00)
> Let me show it. I hold **Wispr Flow** and say: *"Create preparation tasks based on the event agenda document."*

*(Wispr se bolo, text box mein dikhne do, Enter dabao. 10–15 second lagte hain, tab tak bolte raho.)*

> Wispr Flow only turns my voice into text. When I press Enter, a small AI model running on this laptop reads the agenda I uploaded, creates the tasks, and shows the exact page it got each fact from.
> Now I say: *"Open calculator."*

*(Calculator khulega.)*

> It can open apps, folders and websites, but only from a safe fixed list, never random commands.
> And: *"Play Karan Aujla song."*

*(YouTube video khulega. 5 second chalne do, phir roko.)*

## Speaker 3: How it works + sponsor tools (1:00 – 1:30)
> Under the hood, a 4-billion-parameter model, compressed to 4 bits, runs locally on a 6 GB GPU. Your documents, tasks and database never leave this machine.
> For live web research we use **Anakin**. When I ask "best laptop under 50k", the agent searches the web through Anakin, reads the top pages, and answers with sources and prices. It can also scrape any page and save it into my documents so I can ask questions with citations.
> **Wispr Flow** gives us hands-free voice input.
> We did not run GenieX, because it needs Snapdragon hardware and our laptop is Intel and NVIDIA.

*(Ye aakhri line zaroor bolo. Sach bolna judges ko pasand aata hai.)*

## Speaker 4: Close (1:30 – 1:45)
> Everything is open source and the code is public on GitHub at **Cod4Nitish slash crypton-lite**. The default screen is just a chat box and a to-do list, so anyone can use it.
> Crypton Lite: your private assistant, on your own machine. Thank you.

---

## Agar 3 log hain
Speaker 4 ki lines Speaker 1 bole (shuruaat Speaker 1, ant bhi Speaker 1).

## Agar sirf 1 minute mile
Sirf Speaker 1 (problem) + Speaker 2 (Wispr wala task + "Open calculator") + Speaker 4 (close). Anakin ek line mein: "For web research we use Anakin."

## Judges ke sawal (chhote jawab)
| Sawal | Jawab |
|---|---|
| Local kyun? | Documents laptop se bahar nahi jaate. Sirf voice text banane (Wispr) aur web research (Anakin) network use karte hain. |
| Chhota model galti karega? | Tools validate hote hain, delete par Confirm click lagta hai, aur har step ka time aur trace dikhta hai. Proof na mile to agent mana kar deta hai. |
| Anakin ne kya kiya? | Live search aur page scraping. Agent sirf wahi bolta hai jo Anakin se mila, source ke saath. |
| GenieX? | Chalaya nahi, Snapdragon chahiye. Hamara agent kisi bhi local model server se baat karta hai, to aage jod sakte hain. |
| Pehle se bana tha? | Project event se pehle shuru hua tha. Event mein Anakin web research, computer control, play music, simple UI aur docs jode gaye. (Organizers se rules confirm karo.) |

## Agar demo fail ho
- Voice nahi chali: type karo aur bolo "voice cloud service hai, agent local hai."
- Web search slow (30 s): pehle se ek research ka jawab screen par rakho.
- Internet nahi: documents aur tasks demo karo, web wala hissa skip karo.
