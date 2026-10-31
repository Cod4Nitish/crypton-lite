"""Runtime graph, skills, confirmation gate, citations, RAG (offline parts)."""
from fastapi.testclient import TestClient

from backend import db, rag, runtime, skills, store, tools
from backend.main import app
from tests.test_app import fake_ollama

client = TestClient(app)


def test_skills_lazy_and_routing():
    skills.load.cache_clear()
    loaded = skills.load()
    assert set(loaded) == {"task-management", "document-qa", "planning-briefing", "knowledge-notes", "web-research"}
    assert all(s._body is None for s in loaded.values())  # bodies not read yet
    assert skills.route("Summarize the agenda")[0].name == "document-qa"
    assert skills.route("Create preparation tasks from the agenda document")[0].name == "planning-briefing"
    assert skills.route("remember the wifi password is on the badge")[0].name == "knowledge-notes"
    assert skills.route("hello")[0].name == "task-management"
    assert skills.route("anything", "document-qa")[0].name == "document-qa"
    assert client.get("/api/skills").status_code == 200


def test_trace_steps_are_recorded_and_persisted():
    c, seen = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "Pack charger"}}}]},
        {"role": "assistant", "content": "Added."},
    ])
    out = runtime.run("add a task to pack charger", client=c)
    kinds = [s["type"] for s in out["steps"]]
    assert kinds == ["route", "skill_loaded", "llm", "tool", "llm", "final"]
    # only the routed skill's tools were offered to the model
    offered = {t["function"]["name"] for t in seen[0]["tools"]}
    assert offered == set(skills.load()["task-management"].tools)
    saved = store.get_run(out["run_id"])
    assert saved["skill"] == "task-management" and [s["type"] for s in saved["steps"]] == kinds
    assert client.get("/api/runs").json()[0]["id"] == out["run_id"]


def test_allowlist_blocks_tools_outside_skill():
    c, _ = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "delete_task", "arguments": {"task_id": 1}}}]},
        {"role": "assistant", "content": "Not allowed here."},
    ])
    out = runtime.run("what does the agenda say", client=c)  # document-qa: search only
    assert out["actions"][0]["result"] == {"ok": False, "error": "tool 'delete_task' is not allowed here"}


def test_validation_error_goes_back_to_model():
    c, seen = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "x", "due": "someday"}}}]},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "create_task", "arguments": {"title": "x"}}}]},
        {"role": "assistant", "content": "Added."},
    ])
    out = runtime.run("add task x", client=c)
    assert out["actions"][0]["result"]["ok"] is False and "YYYY-MM-DD" in out["actions"][0]["result"]["error"]
    assert out["actions"][1]["result"]["ok"] is True
    assert "YYYY-MM-DD" in seen[1]["messages"][-1]["content"]


def test_step_cap_stops_runaway_loop():
    loop = [{"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "list_tasks", "arguments": {}}}]}] * 20
    c, _ = fake_ollama(loop)
    out = runtime.run("list tasks forever", client=c)
    assert sum(1 for s in out["steps"] if s["type"] == "llm") == runtime.MAX_LLM_CALLS


def test_cancel_pending_keeps_task():
    t = db.create_task("Keep")
    p = tools.execute("delete_task", {"task_id": t["id"]})["pending"]
    assert client.get("/api/pending").json()[0]["id"] == p["id"]
    assert client.post(f"/api/pending/{p['id']}/cancel").json()["pending"]["status"] == "cancelled"
    assert len(db.list_tasks()) == 1
    assert client.post(f"/api/pending/{p['id']}/confirm").status_code == 404  # already resolved


def test_invented_citations_are_removed(monkeypatch):
    monkeypatch.setattr(rag, "search", lambda q, k=4: {"chunks": [{"doc": "a.pdf", "page": 1, "text": "Talk at 9:30", "score": 0.9}], "insufficient": False})
    c, _ = fake_ollama([
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "search_documents", "arguments": {"query": "talk"}}}]},
        {"role": "assistant", "content": "The talk is at 9:30 [1]. Lunch is at noon [7]."},
    ])
    out = runtime.run("when is the talk in the agenda", client=c)
    assert out["sources"][0]["n"] == 1 and out["sources"][0]["doc"] == "a.pdf"
    assert "[1]" in out["reply"] and "[7]" not in out["reply"]
    assert out["steps"][-1]["removed_citations"] == [7]


def test_chunking_and_extract(tmp_path):
    text = ("Sentence number one is here. " * 80).strip()
    chunks = rag.chunk(text)
    assert len(chunks) > 1 and all(len(c) <= rag.CHUNK_CHARS for c in chunks)
    from scripts.make_agenda_pdf import build
    pdf = tmp_path / "agenda.pdf"
    build(str(pdf))
    pages = rag.extract("agenda.pdf", pdf.read_bytes())
    assert [p for p, _ in pages] == [1, 2]
    assert "Quantization" in pages[0][1] and "submissions close" in pages[1][1]
    try:
        rag.extract("x.exe", b"MZ")
        raise AssertionError("should reject")
    except ValueError:
        pass


def test_upload_rejects_bad_type():
    r = client.post("/api/documents", files={"file": ("evil.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400
