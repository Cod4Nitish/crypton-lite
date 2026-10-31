import httpx
import pytest

from backend import anakin, tools


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_search_sends_key_and_trims(monkeypatch):
    seen = {}

    def fake_post(url, json, headers, timeout):
        seen.update(url=url, json=json, headers=headers)
        return FakeResp(200, {"id": "x", "results": [{"title": "T", "url": "https://a.io", "snippet": "s" * 900}]})

    monkeypatch.setenv("ANAKIN_API_KEY", "ak-test")
    monkeypatch.setattr(httpx, "post", fake_post)
    out = tools.execute("web_search", {"query": "wispr flow"})
    assert out["ok"] and out["results"][0]["url"] == "https://a.io"
    assert len(out["results"][0]["snippet"]) == 400
    assert seen["headers"]["X-API-Key"] == "ak-test" and seen["url"].endswith("/search")


def test_scrape_truncates_and_rejects_bad_url(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(200, {"markdown": "x" * 5000}))
    out = tools.execute("scrape_url", {"url": "https://example.com"})
    assert out["ok"] and out["total_parts"] > 1 and len(out["content"]) == anakin.MAX_CHARS
    assert not tools.execute("scrape_url", {"url": "ftp://example.com/file"})["ok"]


@pytest.mark.parametrize("status", [401, 402, 429, 500])
def test_errors_are_reported_not_raised(monkeypatch, status):
    monkeypatch.setenv("ANAKIN_API_KEY", "ak-test")
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(status, {}))
    out = tools.execute("web_search", {"query": "anything"})
    assert out["ok"] is False and "Anakin" in out["error"]


def test_router_picks_web_research():
    from backend import skills
    assert skills.route("search the web for the latest Wispr Flow news")[0].name == "web-research"
