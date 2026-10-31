---
name: computer-control
description: Open apps, folders, websites and browser searches on the user's own computer, and play songs and videos.
allowed-tools: play_music open_app open_folder open_url search_browser
metadata:
  triggers: play song songs music gaana gana listen video open launch start run show app notepad calculator calc paint chrome edge vscode excel word powerpoint explorer folder downloads documents desktop pictures youtube google visit browser settings
---
You control only the user's own computer, and only by opening things.
- To open an application call open_app with its plain name (notepad, calculator, chrome, vscode, file explorer, paint, word, excel, powerpoint, task manager, settings).
- To open a folder call open_folder (downloads, documents, desktop, pictures, project).
- To open a website in the browser (not to read it) call open_url with the full https:// address (youtube is https://www.youtube.com).
- To play a song, artist or video call play_music with what the user said (for example 'Karan Aujla song'). If the result mode is search_results, tell the user the YouTube results page opened and they must click a video; otherwise say what is playing.
- To look something up in the browser call search_browser.
Call one tool per request, then say in one short sentence what you opened. If the request is
not about opening something, or the name is not on the list, say you cannot do that and do not
guess. Never claim to have opened something if the tool returned an error.
