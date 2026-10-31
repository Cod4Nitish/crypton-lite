# Form answers (draft). Copy into the Google Form. Not committed on purpose.

## Fields only YOU can fill
- Team name: ________
- Name of the person submitting: ________
- Video demo link (YouTube/Drive, max 1 min): ________
- Wispr Flow dashboard recording (Drive link): ________
- Social media post links (Logitech MX Master 4 giveaway): ________
- Your own experience feedback for Wispr Flow / Anakin / GenieX and meetup rating: write what you really felt.

## GitHub link to project
https://github.com/Cod4Nitish/crypton-lite

## Deployed link (optional)
https://cod4nitish.github.io/crypton-lite/  (static preview page only; the agent itself runs locally)

## What does your project do?
Crypton Lite is a private AI assistant that runs on the user's own laptop and is controlled by voice or text. It is for event attendees and organizers (and anyone who works with busy hands) who want to turn documents into actions without sending private files to a cloud assistant.

You can say or type: "Create preparation tasks based on the event agenda document" and the agent reads the uploaded agenda PDF, creates the tasks with due dates, and answers with citations that point to the exact page. It also keeps notes, lists and completes tasks, asks for a Confirm click before anything is deleted, opens apps, folders and websites on the computer from a fixed safe list ("Open calculator"), and researches the web. The model (Ollama, qwen3.5:4b, 4-bit Q4_K_M, about 3.1 GiB) runs locally on a 6 GB GPU, with LangGraph for the agent loop, ChromaDB for retrieval and SQLite for storage. Every request has a measured timeline (route, skill, model, tool, with milliseconds). The default screen is deliberately simple: a chat box and a to-do list, with the technical panels under an Advanced button. 59 automated tests pass.

## How did you use Anakin in your project?
Anakin powers the agent's `web-research` skill (backend/anakin.py, skills/web-research/SKILL.md). It adds two tools the local model can call: `web_search`, which calls Anakin's /v1/search endpoint for AI web search with titles, URLs and snippets, and `scrape_url`, which calls /v1/url-scraper/scrape to read the text of a page. The agent answers only from what Anakin returns, names the source URL for each fact, and can save findings as a note or turn them into tasks (for example, "search the web for the speaker's background and add prep tasks"). Errors such as a missing key, 401, 402 or 429 are reported plainly to the user instead of being invented around. Documents and tasks stay local; only the research query goes to Anakin.
Status to state honestly: the integration is covered by automated tests with mocked responses. [EDIT THIS LINE: if you added your key and ran a real search, say what you searched and what came back; if not, say live calls were not verified.]

## How did you use GenieX in your project?
(Optional.) We did not run GenieX. It needs Snapdragon hardware and our build machine is Intel with an NVIDIA RTX 4050. The agent talks to a local model server over HTTP, and GenieX serves an OpenAI-compatible endpoint, so it is a natural next step, but we did not build or test that adapter and cannot claim it works.

## Feedback / experience questions
Write these yourself from what you actually experienced. Do not copy a draft for these.
