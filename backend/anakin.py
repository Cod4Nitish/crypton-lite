"""Anakin.io client: AI web search and URL scraping for the agent's web-research skill.

Auth is the X-API-Key header. The key comes from ANAKIN_API_KEY (env or a project-local
.env file, which is gitignored). Without a key, scraping still works on Anakin's keyless
"Zero Touch" tier (per-IP free allowance); search needs a key.
"""
import os
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx

BASE_URL = os.environ.get("ANAKIN_BASE_URL", "https://api.anakin.io/v1")
TIMEOUT = float(os.environ.get("ANAKIN_TIMEOUT", "100"))  # inline scrapes can hold the connection ~90 s
MAX_CHARS = 3500  # per scrape_url part: small enough for a 4B model's context
RESEARCH_CHARS = 1400  # per page inside research_web
SAVE_CHARS = 60000  # cap for a saved page


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


def _clean(md: str) -> str:
    """Drop image lines and runs of blank lines so more real text fits the model's context."""
    lines = [ln.rstrip() for ln in md.splitlines() if not ln.lstrip().startswith("![")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _check_url(url: str) -> str:
    url = url.strip()
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("url must start with http:// or https://")
    return url


def _scrape_markdown(url: str) -> str:
    """Full cleaned markdown of one page. Retries once in a headless browser when the page looks JS-rendered."""
    text = ""
    for use_browser in (False, True):
        data = _post("/url-scraper/scrape", {"url": url, "useBrowser": use_browser})
        status = data.get("status")
        if status == "failed":
            raise AnakinError(f"Anakin could not scrape that page: {str(data.get('error') or 'unknown error')[:120]}")
        if status in ("pending", "processing", "queued"):
            raise AnakinError("Anakin scrape timed out, try again or use another page")
        text = _clean(data.get("markdown") or data.get("content") or "")
        if len(text) >= 300:
            break
    return text


def scrape(url: str, part: int = 1) -> dict:
    """One page, in parts of MAX_CHARS so the model can keep reading with part=2, 3, ..."""
    url = _check_url(url)
    text = _scrape_markdown(url)
    part = max(1, part)
    total = max(1, -(-len(text) // MAX_CHARS))
    chunk = text[(part - 1) * MAX_CHARS: part * MAX_CHARS]
    if not chunk:
        raise ValueError(f"page has only {total} part(s)")
    note = f"More available: call scrape_url again with part={part + 1}." if part < total else "End of page."
    return {"source": "anakin.io", "url": url, "part": part, "total_parts": total, "content": chunk, "note": note}


def research(query: str, pages: int = 3) -> dict:
    """Search, then read the top pages in parallel. Returns short evidence per page, with URLs."""
    hits = search(query, limit=max(pages + 1, 4))["results"]
    urls = [h["url"] for h in hits if h["url"].startswith("http")][:pages]

    def read(u):
        try:
            return {"url": u, "content": _scrape_markdown(u)[:RESEARCH_CHARS]}
        except (AnakinError, ValueError) as e:
            return {"url": u, "error": str(e)}

    with ThreadPoolExecutor(max_workers=max(1, len(urls))) as ex:
        out = list(ex.map(read, urls))
    titles = {h["url"]: h["title"] for h in hits}
    for p in out:
        p["title"] = titles.get(p["url"], "")
    return {"source": "anakin.io", "query": query, "pages": out, "read_ok": sum(1 for p in out if p.get("content"))}


def page_for_saving(url: str) -> tuple[str, str]:
    """(host, full cleaned markdown) for ingesting a page into the document store."""
    url = _check_url(url)
    text = _scrape_markdown(url)
    if len(text) < 50:
        raise ValueError("page had no readable text to save")
    host = urlparse(url).netloc.replace("www.", "")
    return host, f"Source: {url}\n\n{text[:SAVE_CHARS]}"
