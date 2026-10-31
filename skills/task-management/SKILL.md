---
name: task-management
description: Create, list, complete, update and delete the user's tasks.
allowed-tools: create_task list_tasks complete_task update_task delete_task
metadata:
  triggers: task tasks todo add remind complete done finish finished mark delete remove priority due list open still make it rename
---
Manage tasks with the tools. Refer to tasks by title when the id is unknown.
Only claim what a tool actually did. When asked to delete, call delete_task right
away (do not ask first); the app shows the user a confirm button. Then say it is
waiting for their confirmation.
Reply in one or two short spoken-style sentences; name tasks when listing.
