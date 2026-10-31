"""Computer control: open an allowlisted app, folder or web page on this machine.

Deliberately NOT a shell. The model can only pick a name from APPS / FOLDERS or give an
http(s) URL; nothing it writes is ever executed as a command. Apps and folders are Windows only.
"""
import os
import re
import subprocess
from datetime import datetime
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


# ---- files and screenshots (read-only, inside a few user folders) ------------------------------

def _home(*parts: str) -> str:
    return os.path.join(os.path.expanduser("~"), *parts)


SAFE_ROOTS = {  # the only places the agent may look; tests replace this
    "desktop": _home("Desktop"),
    "documents": _home("Documents"),
    "downloads": _home("Downloads"),
    "pictures": _home("Pictures"),
    "videos": _home("Videos"),
    "project": ROOT,
}
SECRET_NAMES = {".env", ".npmrc", ".pypirc", ".netrc", "id_rsa", "id_ed25519", "credentials", "known_hosts"}
SECRET_DIRS = {".ssh", ".aws", ".gnupg", "appdata"}
SKIP_DIRS = {"node_modules", ".venv", ".git", "__pycache__", "$recycle.bin"}
NEVER_OPEN = {".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf",
              ".lnk", ".reg", ".dll", ".jar", ".hta", ".cpl", ".msc", ".appx"}
READABLE = {".txt", ".md", ".py", ".json", ".csv", ".log", ".html", ".css", ".ts", ".tsx", ".js", ".yml", ".yaml",
            ".toml", ".ini", ".xml", ".rst"}
READ_MAX = 12000
LIST_MAX = 40
FIND_MAX = 20


def _relative_to_root(path: str) -> str:
    """The part of a path inside its safe root, so only names under the user's folders are judged."""
    real = os.path.realpath(path)
    for root_dir in SAFE_ROOTS.values():
        r = os.path.realpath(root_dir)
        if real == r or real.startswith(r + os.sep):
            return os.path.relpath(real, r)
    return real


def _is_secret(path: str) -> bool:
    rel = os.path.normpath(_relative_to_root(path))
    parts = [x.lower() for x in rel.split(os.sep)]
    return parts[-1] in SECRET_NAMES or any(x in SECRET_DIRS for x in parts)


def _safe_path(raw: str) -> str:
    """Resolve 'downloads/cv.pdf' or an absolute path to a real path inside SAFE_ROOTS, else refuse."""
    raw = (raw or "").strip().strip('"')
    if not raw:
        raise ValueError("path is empty")
    first, _, rest = raw.replace("\\", "/").partition("/")
    base = SAFE_ROOTS.get(first.lower())
    path = os.path.join(base, rest) if base else raw
    real = os.path.realpath(path)
    for root_dir in SAFE_ROOTS.values():
        r = os.path.realpath(root_dir)
        if real == r or real.startswith(r + os.sep):
            if _is_secret(real):
                raise ValueError("that file is protected and cannot be accessed")
            return real
    raise ValueError(f"not allowed. I can only use these folders: {', '.join(SAFE_ROOTS)}")


def _entry(path: str) -> dict:
    st = os.stat(path)
    return {"name": os.path.basename(path), "type": "folder" if os.path.isdir(path) else "file",
            "kb": round(st.st_size / 1024), "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "path": path}


def list_files(folder: str, sub: str = "") -> dict:
    path = _safe_path(f"{folder.strip().lower()}/{sub}" if sub else folder.strip().lower())
    if not os.path.isdir(path):
        raise ValueError("that is not a folder")
    items = [os.path.join(path, n) for n in os.listdir(path) if not _is_secret(os.path.join(path, n))]
    items.sort(key=lambda x: os.stat(x).st_mtime, reverse=True)
    return {"folder": path, "total": len(items), "showing": min(len(items), LIST_MAX),
            "items": [_entry(x) for x in items[:LIST_MAX]]}


def find_files(query: str, folder: str = "all") -> dict:
    q = query.strip().lower()
    if len(q) < 2:
        raise ValueError("search text is too short")
    roots = list(SAFE_ROOTS.values()) if folder.strip().lower() in ("", "all") else [_safe_path(folder.strip().lower())]
    hits, seen = [], 0
    for top in roots:
        for dirpath, dirs, files in os.walk(top):
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and d.lower() not in SECRET_DIRS]
            if dirpath[len(top):].count(os.sep) >= 4:
                dirs[:] = []
            for n in files + dirs:
                seen += 1
                full = os.path.join(dirpath, n)
                if q in n.lower() and not _is_secret(full):
                    hits.append(full)
                if len(hits) >= FIND_MAX or seen > 40000:
                    break
            if len(hits) >= FIND_MAX or seen > 40000:
                break
    hits.sort(key=lambda x: os.stat(x).st_mtime, reverse=True)
    return {"query": query, "found": len(hits), "items": [_entry(x) for x in hits]}


def read_file(path: str) -> dict:
    real = _safe_path(path)
    if os.path.splitext(real)[1].lower() not in READABLE:
        raise ValueError("I can only read text files (txt, md, py, json, csv, log, html...)")
    if os.path.getsize(real) > 2_000_000:
        raise ValueError("file is too large to read")
    with open(real, encoding="utf-8", errors="replace") as f:
        text = f.read()
    return {"path": real, "content": text[:READ_MAX], "truncated": len(text) > READ_MAX}


def _open_path(path: str) -> None:
    """Open a file with its default app. Choke point for tests."""
    if sys.platform != "win32":
        raise ValueError("opening files is only supported on Windows")
    os.startfile(path)  # type: ignore[attr-defined]


def open_file(path: str) -> dict:
    real = _safe_path(path)
    if not os.path.isfile(real):
        raise ValueError("that is not a file")
    if os.path.splitext(real)[1].lower() in NEVER_OPEN:
        raise ValueError("programs and scripts are never opened by the agent")
    _open_path(real)
    return {"opened": real}


SCREENSHOT_PS = (
    "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
    "$b=[System.Windows.Forms.SystemInformation]::VirtualScreen;"
    "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
    "$g=[System.Drawing.Graphics]::FromImage($bmp);"
    "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
    "$bmp.Save($env:CRYPTON_SHOT_PATH);$g.Dispose();$bmp.Dispose()"
)


def screenshot() -> dict:
    """Save the whole screen to Pictures/Screenshots. The file name is generated here; the path goes in via env."""
    if sys.platform != "win32":
        raise ValueError("screenshots are only supported on Windows")
    out_dir = _home("Pictures", "Screenshots")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"crypton-{datetime.now():%Y%m%d-%H%M%S}.png")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SCREENSHOT_PS],
                       env={**os.environ, "CRYPTON_SHOT_PATH": path}, timeout=30, check=True, creationflags=0x08000000)
    except (subprocess.SubprocessError, OSError) as e:
        raise ValueError(f"could not take a screenshot: {type(e).__name__}")
    return {"saved": path}
