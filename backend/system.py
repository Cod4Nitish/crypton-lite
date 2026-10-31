"""Computer control: open an allowlisted app, folder or web page on this machine.

Deliberately NOT a shell. The model can only pick a name from APPS / FOLDERS or give an
http(s) URL; nothing it writes is ever executed as a command. Apps and folders are Windows only.
"""
import os
import re
import subprocess
import sys
import webbrowser
from urllib.parse import quote_plus, urlparse

APPS = {  # friendly name -> launch target (fixed list; extend here, never from model output)
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "file explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "settings": "ms-settings:",
    "chrome": "chrome",
    "edge": "msedge",
    "vscode": "code",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
}

FOLDERS = {  # name -> folder under the user's home; None = this project's folder
    "downloads": "Downloads",
    "documents": "Documents",
    "desktop": "Desktop",
    "pictures": "Pictures",
    "project": None,
}

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _launch(target: str) -> None:
    """Single choke point for launching, so tests can replace it."""
    if sys.platform != "win32":
        raise ValueError("opening apps is only supported on Windows")
    if target.startswith("ms-settings:"):
        os.startfile(target)  # type: ignore[attr-defined]
        return
    # `start` resolves names like chrome/code/winword through App Paths; arguments are fixed, never model text.
    subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=0x08000000)


def open_app(name: str) -> dict:
    target = APPS.get(name)
    if not target:
        raise ValueError(f"unknown app '{name}'. Allowed: {', '.join(APPS)}")
    _launch(target)
    return {"opened": name}


def open_folder(name: str) -> dict:
    if name not in FOLDERS:
        raise ValueError(f"unknown folder '{name}'. Allowed: {', '.join(FOLDERS)}")
    sub = FOLDERS[name]
    path = ROOT if sub is None else os.path.join(os.path.expanduser("~"), sub)
    if not os.path.isdir(path):
        raise ValueError(f"folder not found: {name}")
    _launch(path)
    return {"opened": name, "path": path}


def open_url(url: str) -> dict:
    url = url.strip()
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("url must start with http:// or https://")
    webbrowser.open(url)
    return {"opened": url}


def search_in_browser(query: str) -> dict:
    return open_url("https://www.google.com/search?q=" + quote_plus(query))


_VIDEO = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]{6,}")


def play_media(query: str) -> dict:
    """Find the best matching YouTube video with Anakin search and open it (it autoplays).
    Without an Anakin key, or if no video is found, open the YouTube results page instead."""
    from . import anakin
    try:
        for hit in anakin.search(f"{query} official video youtube", limit=8)["results"]:
            m = _VIDEO.match(hit.get("url", ""))
            if m:
                webbrowser.open(hit["url"])
                return {"mode": "video", "playing": hit.get("title", "")[:100], "url": hit["url"]}
    except (anakin.AnakinError, ValueError):
        pass
    url = "https://www.youtube.com/results?search_query=" + quote_plus(query)
    webbrowser.open(url)
    return {"mode": "search_results", "url": url,
            "note": "Could not pick a single video, so the YouTube results page was opened. The user must click one."}
