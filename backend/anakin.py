"""Anakin.io client: AI web search and URL scraping for the agent's web_research skill.

Auth is the X-API-Key header. The key comes from ANAKIN_API_KEY (env or a project-local
.env file, which is gitignored). Without a key, scraping still works on Anakin's keyless
"Zero Touch" tier (per-IP free allowance); search needs a key.
"""
import os
from urllib.parse import urlparse

import httpx

BASE_URL = os.environ.get("ANAKIN_BASE_URL", "https://api.anakin.io/v1")
TIMEOUT = float(os.environ.get("ANAKIN_TIMEOUT", "45"))
MAX_CHARS = 3000  # keep tool output small enough for a 4B model's context


class AnakinError(Exception):
    pass


def _api_key() -> str | None:
    key = os.environ.get("ANAKIN_API_KEY")
    if key:
        return key.strip()
    path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.isfile(path):
        for line in open(path, encoding="utf-8"):
            k, _, v = line.strip().partition("=")
            if k == "ANAKIN_API_KEY" and v:
                return v.strip().strip("\"'")
    return None


def configured() -> bool:
    return _api_key() is not None


def _post(path: str, body: dict) -> dict:
    headers = {"Content-Type": "application/json"}
    key = _api_key()
    if key:
        headers["X-API-Key"] = key
    try:
        r = httpx.post(f"{BASE_URL}{path}", json=body, headers=headers, timeout=TIMEOUT)
    except httpx.HTTPError as e:
        raise AnakinError(f"Anakin request failed: {type(e).__name__}") from e
    if r.status_code == 401:
        raise AnakinError("Anakin rejected the API key (401)" if key else "ANAKIN_API_KEY is not set (add it to .env)")
    if r.status_code == 402:
        raise AnakinError("Anakin credits or free allowance exhausted (402)")
    if r.status_code == 429:
        raise AnakinError("Anakin rate limit hit (429), try again shortly")
    if r.status_code >= 400:
        raise AnakinError(f"Anakin error {r.status_code}")
    return r.json()


def search(prompt: str, limit: int = 5) -> dict:
    data = _post("/search", {"prompt": prompt, "limit": limit})
    results = [
        {"title": x.get("title", ""), "url": x.get("url", ""), "snippet": (x.get("snippet") or "")[:400], "date": x.get("date")}
        for x in data.get("results", [])[:limit]
    ]
    return {"source": "anakin.io", "query": prompt, "results": results}


def scrape(url: str) -> dict:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("url must start with http:// or https://")
    data = _post("/url-scraper/scrape", {"url": url})
    text = data.get("markdown") or data.get("content") or ""
    return {"source": "anakin.io", "url": url, "content": text[:MAX_CHARS], "truncated": len(text) > MAX_CHARS}
