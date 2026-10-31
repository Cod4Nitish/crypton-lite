import os

import pytest

from backend import system, tools


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    docs, outside = tmp_path / "Documents", tmp_path / "Outside"
    docs.mkdir()
    outside.mkdir()
    (docs / "notes.txt").write_text("hello from notes", encoding="utf-8")
    (docs / "resume.pdf").write_bytes(b"%PDF-1.4")
    (docs / "run.bat").write_text("echo hi")
    (docs / ".env").write_text("SECRET=1")
    (docs / "sub").mkdir()
    (docs / "sub" / "deep notes.md").write_text("# deep", encoding="utf-8")
    (outside / "private.txt").write_text("do not read", encoding="utf-8")
    monkeypatch.setattr(system, "SAFE_ROOTS", {"documents": str(docs)})
    opened = []
    monkeypatch.setattr(system, "_open_path", opened.append)
    return {"docs": docs, "outside": outside, "opened": opened}


def test_list_and_find(sandbox):
    out = tools.execute("list_files", {"folder": "documents"})
    names = {i["name"] for i in out["items"]}
    assert out["ok"] and {"notes.txt", "resume.pdf", "sub"} <= names and ".env" not in names
    found = tools.execute("find_files", {"query": "notes"})
    assert {i["name"] for i in found["items"]} == {"notes.txt", "deep notes.md"}


def test_read_text_file(sandbox):
    out = tools.execute("read_file", {"path": "documents/notes.txt"})
    assert out["ok"] and out["content"] == "hello from notes"


@pytest.mark.parametrize("bad", ["documents/.env", "documents/../Outside/private.txt", "C:/Windows/win.ini",
                                 "../../etc/passwd", "documents/resume.pdf"])
def test_protected_or_outside_paths_are_refused(sandbox, bad):
    assert tools.execute("read_file", {"path": bad})["ok"] is False


def test_outside_path_by_absolute_name_is_refused(sandbox):
    assert tools.execute("read_file", {"path": str(sandbox["outside"] / "private.txt")})["ok"] is False


def test_open_file_allows_documents_but_never_programs(sandbox):
    assert tools.execute("open_file", {"path": "documents/resume.pdf"})["ok"]
    assert tools.execute("open_file", {"path": "documents/run.bat"})["ok"] is False
    assert len(sandbox["opened"]) == 1 and sandbox["opened"][0].endswith("resume.pdf")


def test_screenshot_uses_generated_path_and_env(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, env, timeout, check, creationflags):
        calls["env"] = env["CRYPTON_SHOT_PATH"]
        calls["cmd"] = cmd

    monkeypatch.setattr(system, "_home", lambda *p: os.path.join(str(tmp_path), *p))
    monkeypatch.setattr(system.sys, "platform", "win32")
    monkeypatch.setattr(system.subprocess, "run", fake_run)
    out = tools.execute("take_screenshot", {})
    assert out["ok"] and out["saved"] == calls["env"] and out["saved"].endswith(".png")
    assert calls["env"] not in " ".join(calls["cmd"])  # path travels in the environment, never in the command text


def test_router_sends_file_and_screenshot_requests_to_computer_control():
    from backend import skills
    for msg in ("take a screenshot", "find my resume file", "list files in downloads", "open the readme on github"):
        assert skills.route(msg)[0].name == "computer-control", msg


def test_agent_stops_after_a_refused_action(sandbox, monkeypatch):
    """After a blocked read the model must not go on to run other tools (seen live with a 4B model)."""
    from backend import runtime

    calls = iter([
        {"message": {"content": "", "tool_calls": [{"function": {"name": "read_file", "arguments": {"path": "documents/.env"}}}]}},
        {"message": {"content": "", "tool_calls": [{"function": {"name": "take_screenshot", "arguments": {}}}]}},
    ])

    def fake_post(client, payload):
        return next(calls), 1

    monkeypatch.setattr(runtime, "_post_llm", fake_post)
    out = runtime.run("read the file documents/.env")
    names = [a["tool"] for a in out["actions"]]
    assert names == ["read_file"]
    assert "could not do that" in out["reply"] and "protected" in out["reply"]
