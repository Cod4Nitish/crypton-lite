---
name: planning-briefing
description: Turn documents and existing tasks into a briefing and concrete preparation tasks, or plan the day.
allowed-tools: search_documents list_tasks create_task
metadata:
  triggers: plan planning prepare preparation prep brief briefing checklist schedule day agenda based create tasks from organise organize
---
1. Call search_documents for the relevant facts (and list_tasks only if planning the day).
2. When the user asks to create, prepare or plan tasks, you MUST call create_task 3 to 5 times
   BEFORE writing any reply. One call per concrete preparation task, each with a short action
   title (no "[Sample]" prefix), a due date YYYY-MM-DD from the evidence if one exists, and a
   priority from the evidence. Never skip this step because similar tasks may exist: the
   create_task tool detects exact duplicates itself.
3. Only after the create_task calls, reply with a short briefing citing passages as [1], [2]
   (only numbers that were returned), then list the tasks you created. If the search found
   insufficient evidence, say so, create nothing and do not invent agenda items.
