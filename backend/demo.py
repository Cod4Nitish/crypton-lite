"""Competition-specific: one-click demo preparation with clearly labelled SAMPLE data.

Not part of the reusable starter. Wipes tasks, runs, notes and the knowledge base, then
indexes docs/sample/event-agenda.pdf (a hand-written sample, not the official agenda) and
adds two tasks prefixed "[Sample]". Embeds first, so an Ollama outage never leaves the app empty.
"""
import os

from . import db, rag, store

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "..", "docs", "sample", "event-agenda.pdf")
SAMPLE_DOC_NAME = "SAMPLE-event-agenda.pdf"
SAMPLE_TASKS = [
    ("[Sample] Rehearse the 2-minute demo", "high", None),
    ("[Sample] Check Ollama is running", "medium", None),
]


def reset() -> dict:
    with open(SAMPLE_PDF, "rb") as f:
        data = f.read()
    rag.embed(["ping"], "query")  # raises httpx.HTTPError before anything is deleted if embeddings are down
    rag.wipe()
    with db._conn() as c:
        for t in ("tasks", "runs", "pending_actions", "notes", "documents"):
            c.execute(f"DELETE FROM {t}")
        c.execute("DELETE FROM sqlite_sequence")
    doc = rag.ingest(SAMPLE_DOC_NAME, data)["document"]
    tasks = [db.create_task(t, p, d) for t, p, d in SAMPLE_TASKS]
    return {"document": doc, "tasks": tasks, "label": "sample data"}
