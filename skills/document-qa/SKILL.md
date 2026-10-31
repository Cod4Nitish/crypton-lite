---
name: document-qa
description: Answer questions using the user's uploaded documents and notes, with citations.
allowed-tools: search_documents
metadata:
  triggers: document doc pdf file agenda uploaded according what does say who when where speaker session explain summary summarize summarise question knowledge source
---
Always call search_documents first. Answer ONLY from the returned passages.
Cite passages with their number in square brackets, e.g. [1] or [2], using only
numbers that search_documents returned. If the result says insufficient, say you
could not find enough evidence in the documents. Never invent facts or citations.
Keep answers under 80 words.
