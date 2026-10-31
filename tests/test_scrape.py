import httpx
import pytest

from backend import anakin, tools


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def page(md, status="completed", error=None):
    return FakeResp(200, {"status": status, "markdown": md, "error": error})


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("ANAKIN_API_KEY", "test-key")


def test_failed_scrape_is_reported_not_returned_as_empty(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: page("", status="failed", error="blocked by site"))
    out = tools.execute("scrape_url", {"url": "https://example.com"})
    assert out["ok"] is False and "blocked by site" in out["error"]


def test_timeout_status_is_reported(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: page("", status="processing"))
    out = tools.execute("scrape_url", {"url": "https://example.com"})
    assert out["ok"] is False and "timed out" in out["error"]


def test_thin_page_is_retried_with_browser(monkeypatch):
    sent = []

    def fake(url, json, headers, timeout):
        sent.append(json["useBrowser"])
        return page("x" if not json["useBrowser"] else "real content " * 60)

    monkeypatch.setattr(httpx, "post", fake)
    out = tools.execute("scrape_url", {"url": "https://spa.example.com"})
    assert sent == [False, True] and out["ok"] and "real content" in out["content"]


def test_long_page_is_read_in_parts(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: page("word " * 2000))  # about 10,000 chars
    first = tools.execute("scrape_url", {"url": "https://example.com"})
    third = tools.execute("scrape_url", {"url": "https://example.com", "part": 3})
    assert first["ok"] and first["total_parts"] == 3 and "part=2" in first["note"]
    assert third["ok"] and third["note"] == "End of page."
    assert tools.execute("scrape_url", {"url": "https://example.com", "part": 9})["ok"] is False


def test_markdown_images_are_dropped(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: page("# Title\n\n![logo](x.png)\n\n\n\nBody text " * 30))
    out = tools.execute("scrape_url", {"url": "https://example.com"})
    assert "![" not in out["content"] and "\n\n\n" not in out["content"]


def test_research_reads_top_pages_and_survives_one_failure(monkeypatch):
    def fake(url, json, headers, timeout):
        if url.endswith("/search"):
            return FakeResp(200, {"results": [{"title": f"T{i}", "url": f"https://s{i}.com", "snippet": "s"} for i in range(5)]})
        if json["url"] == "https://s1.com":
            return page("", status="failed", error="blocked")
        return page("content of " + json["url"] + " " + "z" * 2000)

    monkeypatch.setattr(httpx, "post", fake)
    out = tools.execute("research_web", {"query": "best laptop"})
    assert out["ok"] and len(out["pages"]) == 3 and out["read_ok"] == 2
    assert all(len(p.get("content", "")) <= anakin.RESEARCH_CHARS for p in out["pages"])
    assert [p["url"] for p in out["pages"] if "error" in p] == ["https://s1.com"]


def test_save_page_makes_it_searchable(monkeypatch):
    from backend import rag
    monkeypatch.setattr(httpx, "post", lambda *a, **k: page("Quantum widgets are made in Pune. " * 20))
    monkeypatch.setattr(rag, "ingest", lambda name, data, source_id=None: {"document": {"name": name, "chunks": 2}, "cached": False})
    out = tools.execute("save_page", {"url": "https://www.widgets.example/about"})
    assert out["ok"] and out["saved_as"] == "web-widgets.example.md" and out["chunks"] == 2


def test_router_picks_the_right_skill_for_scraping():
    from backend import skills
    assert skills.route("save this page https://example.com to my documents")[0].name == "web-research"
    assert skills.route("research the best budget laptops")[0].name == "web-research"
