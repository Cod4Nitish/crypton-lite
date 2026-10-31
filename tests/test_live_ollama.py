"""Live tests against the real local model. Skipped if Ollama is not running."""
import httpx
import pytest

from backend import agent, db

try:
    httpx.get(f"{agent.OLLAMA_URL}/api/tags", timeout=2)
    UP = True
except httpx.HTTPError:
    UP = False

pytestmark = [pytest.mark.live, pytest.mark.skipif(not UP, reason="Ollama not running")]


def tools_used(out):
    return [a["tool"] for a in out["actions"]]


def test_live_create_task():
    out = agent.chat("Add a high priority task to submit the hackathon demo")
    assert "create_task" in tools_used(out)
    tasks = db.list_tasks()
    assert len(tasks) == 1 and "demo" in tasks[0]["title"].lower()
    assert tasks[0]["priority"] == "high"


def test_live_list_tasks():
    db.create_task("Buy groceries")
    out = agent.chat("What tasks do I have?")
    assert "list_tasks" in tools_used(out)
    assert "grocer" in out["reply"].lower()


def test_live_complete_task():
    db.create_task("Buy groceries")
    db.create_task("Practice the pitch")
    out = agent.chat("I finished practicing the pitch, mark it done")
    assert "complete_task" in tools_used(out)
    done = [t["title"] for t in db.list_tasks("done")]
    assert done == ["Practice the pitch"]


def test_live_update_priority():
    db.create_task("Buy HDMI cable", "low")
    out = agent.chat("Make the HDMI cable task high priority")
    assert "update_task" in tools_used(out)
    assert db.list_tasks()[0]["priority"] == "high"


def test_live_delete_task():
    db.create_task("Old idea")
    db.create_task("Keep me")
    out = agent.chat("Delete the old idea task")
    assert "delete_task" in tools_used(out)
    assert out["status"] == "needs_confirmation" and len(db.list_tasks()) == 2  # nothing deleted yet
    from backend import runtime
    runtime.confirm(out["pending"][0]["id"], True)
    assert [t["title"] for t in db.list_tasks()] == ["Keep me"]


def test_live_follow_up_uses_history():
    first = agent.chat("Add a task to book a cab")
    hist = [{"role": "user", "content": "Add a task to book a cab"}, {"role": "assistant", "content": first["memory"]}]
    agent.chat("make it high priority", history=hist)
    tasks = db.list_tasks()
    assert len(tasks) == 1 and tasks[0]["priority"] == "high"
