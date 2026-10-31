"""Hackathon-readiness: dedupe, bounded retry, failure paths, timing, demo reset."""
import httpx
import pytest
from fastapi.testclient import TestClient

from backend import agent, db, runtime, tools
from backend.main import app
from tests.test_app import fake_ollama

client = TestClient(app)
CALL = {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "Pack charger"}}}]}


def test_duplicate_task_is_not_created_twice():
    first = tools.execute("create_task", {"title": "Pack charger"})
    again = tools.execute("create_task", {"title": "  pack   CHARGER "})
    assert first["ok"] and not first.get("duplicate")
    assert again["ok"] and again["duplicate"] is True and again["task"]["id"] == first["task"]["id"]
    assert len(db.list_tasks()) == 1
    tools.execute("create_task", {"title": "Pack charger", "due": "2026-11-01"})  # different due = different task
    assert len(db.list_tasks()) == 2


def test_agent_double_send_creates_one_task_and_says_so():
    for _ in range(2):
        c, _s = fake_ollama([CALL, {"role": "assistant", "content": "Done."}])
        out = runtime.run("add task pack charger", client=c)
    assert len(db.list_tasks()) == 1
    tool_step = [s for s in out["steps"] if s["type"] == "tool"][0]
    assert "already exists" in tool_step["summary"]


def test_llm_retries_once_on_transient_error_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    out = runtime.run("hello", client=httpx.Client(transport=httpx.MockTransport(handler)))
    llm = [s for s in out["steps"] if s["type"] == "llm"][0]
    assert calls["n"] == 2 and llm["attempts"] == 2 and out["reply"] == "ok"


def test_llm_retry_is_bounded_and_failure_is_persisted():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        raise httpx.ConnectError("down")

    with pytest.raises(httpx.HTTPError):
        runtime.run("hello", client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert calls["n"] == 2  # 1 try + 1 retry, never more
    assert client.get("/api/runs").json()[0]["status"] == "error"


def test_tool_failure_is_reported_not_retried_or_faked():
    bad = {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "complete_task", "arguments": {"title": "nonexistent"}}}]}
    c, _s = fake_ollama([bad, {"role": "assistant", "content": "I could not find that task."}])
    out = runtime.run("finish nonexistent", client=c)
    tool_steps = [s for s in out["steps"] if s["type"] == "tool"]
    assert len(tool_steps) == 1 and tool_steps[0]["ok"] is False and tool_steps[0]["error"] == "task not found"


def test_timing_is_measured_from_real_steps():
    c, _s = fake_ollama([CALL, {"role": "assistant", "content": "Done."}])
    out = runtime.run("add task pack charger", client=c)
    t = out["timing"]
    assert t["llm_calls"] == 2 and t["tool_calls"] == 1
    assert t["llm_ms"] == sum(s["ms"] for s in out["steps"] if s["type"] == "llm")
    assert t["tool_ms"] == sum(s["ms"] for s in out["steps"] if s["type"] == "tool")
    assert t["total_ms"] >= t["llm_ms"]


def test_persistence_survives_a_fresh_connection():
    client.post("/api/tasks", json={"title": "Persist me"})
    with db._conn() as c:  # brand-new SQLite connection reading the file
        assert c.execute("SELECT title FROM tasks").fetchone()["title"] == "Persist me"


def _up():
    try:
        return httpx.get(f"{agent.OLLAMA_URL}/api/tags", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def test_demo_reset_fails_safely_when_embeddings_down(monkeypatch):
    db.create_task("keep me")
    monkeypatch.setattr(agent, "OLLAMA_URL", "http://127.0.0.1:1")
    r = client.post("/api/demo/reset")
    assert r.status_code == 503
    assert [t["title"] for t in db.list_tasks()] == ["keep me"]  # nothing wiped


@pytest.mark.live
@pytest.mark.skipif(not _up(), reason="Ollama not running")
def test_demo_reset_seeds_labelled_sample_data_and_is_repeatable():
    db.create_task("old junk")
    for _ in range(2):
        r = client.post("/api/demo/reset")
        assert r.status_code == 200
    titles = [t["title"] for t in db.list_tasks()]
    assert titles and all(t.startswith("[Sample]") for t in titles) and "old junk" not in titles
    docs = client.get("/api/documents").json()
    assert [d["name"] for d in docs] == ["SAMPLE-event-agenda.pdf"]
    hit = client.get("/api/search", params={"q": "when do submissions close?"}).json()
    assert hit["chunks"] and hit["chunks"][0]["doc"] == "SAMPLE-event-agenda.pdf" and hit["chunks"][0]["page"] == 2


def test_near_duplicate_title_is_blocked():
    from backend import tools
    first = tools.execute("create_task", {"title": "Submit public repo link and demo video by 14:00", "due": "2026-10-31"})
    again = tools.execute("create_task", {"title": "Submit public repo link & demo video by 14:00.", "due": "2026-10-31"})
    other = tools.execute("create_task", {"title": "Charge laptop", "due": "2026-10-31"})
    assert first["ok"] and not first.get("duplicate")
    assert again.get("duplicate") is True
    assert other["ok"] and not other.get("duplicate")
