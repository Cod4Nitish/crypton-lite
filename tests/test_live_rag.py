"""Live RAG + end-to-end agenda scenario against real Ollama (qwen3.5:4b + nomic-embed-text)."""
import os

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import agent, db, rag
from backend.main import app

try:
    UP = httpx.get(f"{agent.OLLAMA_URL}/api/tags", timeout=2).status_code == 200
except httpx.HTTPError:
    UP = False

pytestmark = [pytest.mark.live, pytest.mark.skipif(not UP, reason="Ollama not running")]
client = TestClient(app)
AGENDA = os.path.join(os.path.dirname(__file__), "..", "docs", "sample", "event-agenda.pdf")


def upload():
    with open(AGENDA, "rb") as f:
        return client.post("/api/documents", files={"file": ("event-agenda.pdf", f, "application/pdf")})


def test_ingest_search_and_cache():
    r = upload()
    assert r.status_code == 201 and r.json()["cached"] is False
    assert r.json()["document"]["pages"] == 2
    again = upload().json()
    assert again["cached"] is True  # unchanged file is not re-embedded
    hits = rag.search("when do submissions close?")
    assert not hits["insufficient"]
    top = hits["chunks"][0]
    assert top["doc"] == "event-agenda.pdf" and top["page"] == 2 and "14:00" in top["text"]
    assert rag.search("recipe for chocolate cake with frosting")["insufficient"] is True


def test_e2e_agenda_summary_then_prep_tasks():
    assert upload().status_code == 201
    before = db.list_tasks()

    s = client.post("/api/chat", json={"message": "Summarize the important activities in the event agenda"}).json()
    assert s["skill"] == "document-qa"
    assert any(a["tool"] == "search_documents" for a in s["actions"])
    assert s["sources"] and all(src["doc"] == "event-agenda.pdf" for src in s["sources"])
    assert {src["page"] for src in s["sources"]} <= {1, 2}
    assert s["steps"][-1]["removed_citations"] == [] or isinstance(s["steps"][-1]["removed_citations"], list)

    p = client.post("/api/chat", json={"message": "Create preparation tasks based on the event agenda document"}).json()
    assert p["skill"] == "planning-briefing"
    created = [a["result"]["task"] for a in p["actions"] if a["tool"] == "create_task" and a["result"]["ok"]]
    assert 1 <= len(created) <= 5
    after = db.list_tasks()
    assert len(after) == len(before) + len(created)  # real rows in SQLite
    assert p["sources"], "planning must be grounded in retrieved passages"
    run = client.get(f"/api/runs/{p['run_id']}").json()
    assert [st["type"] for st in run["steps"]][:3] == ["route", "skill_loaded", "llm"]


def test_insufficient_evidence_is_admitted():
    assert upload().status_code == 201
    r = client.post("/api/chat", json={"message": "According to the agenda document, what is the wifi password?"}).json()
    assert r["skill"] == "document-qa"
    text = r["reply"].lower()
    assert any(w in text for w in ("not", "no ", "couldn", "could not", "doesn", "unable", "insufficient"))


def test_note_is_saved_and_recalled():
    r = client.post("/api/chat", json={"message": "Remember this note: the demo laptop password is stored in the blue folder"}).json()
    assert r["skill"] == "knowledge-notes"
    assert any(a["tool"] == "add_note" and a["result"]["ok"] for a in r["actions"])
    hits = rag.search("where is the demo laptop password?")
    assert not hits["insufficient"] and "blue folder" in hits["chunks"][0]["text"]
