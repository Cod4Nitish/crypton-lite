import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import agent, db
from backend.main import app

client = TestClient(app)


# --- database ---------------------------------------------------------------

def test_create_list_complete_db():
    t = db.create_task("Buy milk", "high", "2026-11-01")
    assert t["id"] and t["priority"] == "high" and t["done"] is False
    db.create_task("Low thing", "low")
    assert [x["title"] for x in db.list_tasks("open")] == ["Buy milk", "Low thing"]
    done = db.complete_task(task_id=t["id"])
    assert done["done"] is True and done["completed_at"]
    assert [x["title"] for x in db.list_tasks("done")] == ["Buy milk"]


def test_complete_by_title_and_errors():
    db.create_task("Submit hackathon demo")
    assert db.complete_task(title="hackathon")["done"] is True
    with pytest.raises(LookupError):
        db.complete_task(title="does not exist")
    with pytest.raises(ValueError):
        db.create_task("   ")
    assert db.create_task("x", "urgent")["priority"] == "medium"


# --- REST API ---------------------------------------------------------------

def test_rest_endpoints():
    r = client.post("/api/tasks", json={"title": "Write README", "priority": "low"})
    assert r.status_code == 201
    tid = r.json()["id"]
    assert client.get("/api/tasks").json()[0]["title"] == "Write README"
    assert client.post(f"/api/tasks/{tid}/complete").json()["done"] is True
    assert client.post("/api/tasks/9999/complete").status_code == 404
    assert client.post("/api/tasks", json={"title": ""}).status_code == 422


def test_frontend_served():
    r = client.get("/")
    assert "CRYPTON" in r.text and r.headers["cache-control"] == "no-cache"
    assert client.get("/lite").headers["cache-control"] == "no-cache"
    assert client.get("/static/app.js").status_code == 200


# --- agent loop with a fake Ollama -------------------------------------------

def fake_ollama(script):
    """Returns an httpx client whose /api/chat replies with successive scripted messages."""
    replies = iter(script)
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json={"message": next(replies)})

    return httpx.Client(transport=httpx.MockTransport(handler)), seen


def test_agent_native_tool_call():
    c, seen = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "Call mom", "priority": "high"}}}]},
        {"role": "assistant", "content": "Added 'Call mom' as high priority."},
    ])
    out = agent.chat("remind me to call mom, it's urgent", client=c)
    assert out["actions"][0]["tool"] == "create_task" and out["actions"][0]["result"]["ok"]
    assert db.list_tasks()[0]["title"] == "Call mom"
    assert seen[1]["messages"][-1]["role"] == "tool"
    assert "Call mom" in out["reply"]


def test_agent_json_in_content_fallback_and_complete():
    db.create_task("Pitch practice")
    c, _ = fake_ollama([
        {"role": "assistant", "content": '{"name": "complete_task", "arguments": {"title": "pitch"}}'},
        {"role": "assistant", "content": "Marked it done."},
    ])
    out = agent.chat("I finished pitch practice", client=c)
    assert out["actions"][0]["result"]["task"]["done"] is True


def test_agent_tool_error_is_reported_not_raised():
    c, _ = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "complete_task", "arguments": {"task_id": 42}}}]},
        {"role": "assistant", "content": "I couldn't find that task."},
    ])
    out = agent.chat("complete task 42", client=c)
    assert out["actions"][0]["result"] == {"ok": False, "error": "task not found"}


def test_chat_endpoint_ollama_down(monkeypatch):
    monkeypatch.setattr(agent, "OLLAMA_URL", "http://127.0.0.1:1")
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 503


# --- v2 features --------------------------------------------------------------

def test_update_delete_restore_db():
    t = db.create_task("Draft pitch", "low")
    u = db.update_task(t["id"], title="Final pitch", priority="high", due="2026-11-01")
    assert (u["title"], u["priority"], u["due"]) == ("Final pitch", "high", "2026-11-01")
    assert db.update_task(t["id"], due="")["due"] is None
    assert db.update_task(t["id"], done=True)["completed_at"]
    assert db.update_task(t["id"], done=False)["completed_at"] is None
    gone = db.delete_task(t["id"])
    assert db.list_tasks() == []
    assert db.restore_task(gone)["id"] == t["id"]
    with pytest.raises(LookupError):
        db.update_task(999, title="x")


def test_rest_patch_delete_restore():
    tid = client.post("/api/tasks", json={"title": "Cables"}).json()["id"]
    assert client.patch(f"/api/tasks/{tid}", json={"priority": "high"}).json()["priority"] == "high"
    assert client.patch(f"/api/tasks/{tid}", json={"done": True}).json()["done"] is True
    gone = client.delete(f"/api/tasks/{tid}").json()
    assert client.get("/api/tasks").json() == []
    assert client.post("/api/tasks/restore", json=gone).json()["title"] == "Cables"
    assert client.delete("/api/tasks/999").status_code == 404
    assert client.patch("/api/tasks/999", json={"done": True}).status_code == 404


def test_pwa_assets_served():
    m = client.get("/manifest.webmanifest")
    assert m.status_code == 200 and m.json()["display"] == "standalone"
    assert "serviceWorker" not in client.get("/sw.js").text  # it's the worker itself
    assert client.get("/sw.js").status_code == 200
    for icon in ("icon-192.png", "icon-512.png", "icon.svg"):
        assert client.get(f"/static/{icon}").status_code == 200


def test_registry_has_all_tools():
    from backend import tools
    assert set(tools.REGISTRY) == {"create_task", "list_tasks", "complete_task", "update_task", "delete_task",
                                   "search_documents", "add_note", "list_notes", "web_search", "scrape_url", "research_web", "save_page", "play_music", "list_files", "find_files", "read_file", "open_file", "take_screenshot",
                                   "open_app", "open_folder", "open_url", "search_browser"}


def test_agent_update_and_delete_by_title():
    db.create_task("Buy HDMI cable")
    c, _ = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "update_task", "arguments": {"title": "hdmi", "priority": "high"}}}]},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "delete_task", "arguments": {"title": "hdmi"}}}]},
        {"role": "assistant", "content": "Updated, then deleted."},
    ])
    out = agent.chat("bump the hdmi task then delete it", client=c)
    assert [a["result"]["ok"] for a in out["actions"]] == [True, True]
    assert out["actions"][0]["result"]["task"]["priority"] == "high"
    # delete is destructive: it must wait for the user, not run
    assert out["status"] == "needs_confirmation" and len(db.list_tasks()) == 1
    pid = out["pending"][0]["id"]
    r = client.post(f"/api/pending/{pid}/confirm").json()
    assert r["pending"]["status"] == "confirmed" and r["tasks"] == []


def test_agent_ignores_unknown_args_and_sends_history():
    c, seen = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "X", "colour": "red"}}}]},
        {"role": "assistant", "content": "ok"},
    ])
    out = agent.chat("add X", client=c, history=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}])
    assert out["actions"][0]["result"]["ok"]
    assert [m["role"] for m in seen[0]["messages"]] == ["system", "user", "assistant", "user"]


def test_fuzzy_title_match():
    db.create_task("Practice the pitch")
    db.create_task("Buy groceries")
    assert db.find_open_by_title("practicing the pitch")["title"] == "Practice the pitch"
    assert db.find_open_by_title("grocery shopping")["title"] == "Buy groceries"
    assert db.find_open_by_title("unicorns") is None


def test_memory_includes_touched_task():
    c, _ = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "Book a cab"}}}]},
        {"role": "assistant", "content": "Added."},
    ])
    out = agent.chat("add book a cab", client=c)
    assert out["memory"].startswith("Added.") and '"Book a cab"' in out["memory"]
