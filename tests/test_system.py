import pytest

from backend import system, tools


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(system, "_launch", calls.append)
    monkeypatch.setattr(system.webbrowser, "open", calls.append)
    return calls


def test_open_known_app(launched):
    out = tools.execute("open_app", {"name": "Notepad"})
    assert out["ok"] and launched == ["notepad.exe"]


@pytest.mark.parametrize("bad", ["cmd", "powershell", "notepad & calc", "rm -rf /", "C:\\Windows\\System32\\cmd.exe"])
def test_unknown_app_is_refused(launched, bad):
    out = tools.execute("open_app", {"name": bad})
    assert out["ok"] is False and launched == []


@pytest.mark.parametrize("bad", ["file:///C:/Windows/win.ini", "javascript:alert(1)", "ftp://x.com/a", "notaurl"])
def test_only_http_urls(launched, bad):
    assert tools.execute("open_url", {"url": bad})["ok"] is False and launched == []


def test_url_and_search(launched):
    assert tools.execute("open_url", {"url": "https://www.youtube.com"})["ok"]
    assert tools.execute("search_browser", {"query": "wispr flow & anakin"})["ok"]
    assert launched[0] == "https://www.youtube.com"
    assert launched[1] == "https://www.google.com/search?q=wispr+flow+%26+anakin"


def test_folder_allowlist(launched):
    assert tools.execute("open_folder", {"name": "project"})["ok"]
    assert tools.execute("open_folder", {"name": "C:\\Windows"})["ok"] is False


def test_router():
    from backend import skills
    for msg in ("open notepad", "open YouTube", "open my downloads folder", "launch chrome"):
        assert skills.route(msg)[0].name == "computer-control", msg
    assert skills.route("search the web for latest Wispr Flow news")[0].name == "web-research"
