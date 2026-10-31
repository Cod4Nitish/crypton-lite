---
name: web-research
description: Research the live web with Anakin.io: search, read and scrape pages, save pages as documents, and turn findings into notes or tasks.
allowed-tools: research_web web_search scrape_url save_page add_note create_task
metadata:
  triggers: web online internet research lookup latest news scrape scraping extract fetch content page text read website webpage site url link best price prices cost buy cheap cheaper compare comparison review reviews recommend recommendation market product products laptop phone under top worth alternatives save
---
Choose ONE approach for the request:
- A question that needs facts from the web (best, compare, price, news, how to) -> call research_web once.
- A quick list of sources only -> call web_search.
- The user gave a URL and wants its content -> call scrape_url with that exact URL. If the result says
  more parts are available and the user needs them, call scrape_url again with the next part number.
- The user wants a page kept ("save", "add to my documents") -> call save_page, then tell them they can
  now ask questions about it.
Answer ONLY from the tool results and name the source URL for each fact. If a tool returned an error,
say so plainly and do not guess. If research_web read_ok is 0, say the pages could not be read and
offer the search snippets instead. If asked to save findings call add_note once; for follow-up actions
call create_task for each. Keep the reply under 120 words and say the data came from Anakin.io.
