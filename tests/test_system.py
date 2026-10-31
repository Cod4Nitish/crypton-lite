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


def test_scrape_requests_go_to_web_research():
    from backend import skills
    for msg in ("scrape https://example.com", "scrape the website example.com", "read the content of this page https://example.com/a"):
        assert skills.route(msg)[0].name == "web-research", msg
    assert skills.route("open youtube")[0].name == "computer-control"


def test_shopping_and_research_questions_go_to_web_research():
    from backend import skills
    for msg in ("best product avalable on market best laptop under 50k", "compare iPhone vs Pixel prices",
                "what is the best phone under 30000", "recommend a good laptop"):
        assert skills.route(msg)[0].name == "web-research", msg
    assert skills.route("add a task to buy milk")[0].name == "task-management"


def test_url_in_message_goes_to_web_research_unless_opening():
    from backend import skills
    assert skills.route("scrape https://example.com and tell me what it says")[0].name == "web-research"
    assert skills.route("summarize https://example.com/page")[0].name == "web-research"
    assert skills.route("open https://www.youtube.com")[0].name == "computer-control"


def test_play_music_opens_the_first_youtube_video(launched, monkeypatch):
    from backend import anakin
    monkeypatch.setattr(anakin, "search", lambda q, limit=5: {"results": [
        {"title": "Some blog", "url": "https://blog.example.com/karan"},
        {"title": "Karan Aujla - Song (Official Video)", "url": "https://www.youtube.com/watch?v=abc123XYZ_-"}]})
    out = tools.execute("play_music", {"query": "Karan Aujla song"})
    assert out["ok"] and out["mode"] == "video" and launched == ["https://www.youtube.com/watch?v=abc123XYZ_-"]


def test_play_music_falls_back_to_youtube_results(launched, monkeypatch):
    from backend import anakin

    def boom(q, limit=5):
        raise anakin.AnakinError("no key")

    monkeypatch.setattr(anakin, "search", boom)
    out = tools.execute("play_music", {"query": "Karan Aujla song"})
    assert out["ok"] and out["mode"] == "search_results"
    assert launched == ["https://www.youtube.com/results?search_query=Karan+Aujla+song"]


def test_play_requests_route_to_computer_control():
    from backend import skills
    for msg in ("play Karan Aujla song", "play a song by Diljit", "play music"):
        assert skills.route(msg)[0].name == "computer-control", msg
