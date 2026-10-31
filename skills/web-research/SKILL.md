---
name: web-research
description: Look things up on the live web with Anakin.io (search, read a page) and turn findings into notes or tasks.
allowed-tools: web_search scrape_url add_note create_task
metadata:
  triggers: web online internet research lookup latest news scrape scraping extract fetch content page text read website webpage site url link
---
1. Call web_search with a short query. If the user gave a URL, call scrape_url on it instead.
2. Answer ONLY from the returned results. Name the source URL for each fact. If a tool returned
   an error, say so plainly and do not guess.
3. If the user asked to save the findings, call add_note once with a short title and the key
   facts. If they asked for follow-up tasks, call create_task for each concrete action.
4. Keep the reply under 100 words and say that the data came from Anakin.io.
