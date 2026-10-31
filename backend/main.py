"""CRYPTON Agent Workspace API. Run: uvicorn backend.main:app --host 0.0.0.0 --port 8000"""
import os
import time

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import agent, db, skills, store

ROOT = os.path.join(os.path.dirname(__file__), "..")
LITE = os.path.join(ROOT, "frontend")                  # original no-build UI, kept as /lite
WORKSPACE = os.path.join(ROOT, "web", "dist")          # React workspace build
MAX_UPLOAD = 15 * 1024 * 1024

app = FastAPI(title="CRYPTON Agent Workspace")
db.init_db()
store.init_store()


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    priority: str = "medium"
    due: str | None = None


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    priority: str | None = None
    due: str | None = None
    done: bool | None = None


class TaskFull(TaskIn):
    id: int
    done: bool = False
    created_at: str | None = None
    completed_at: str | None = None


class Turn(BaseModel):
    role: str
    content: str


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[Turn] = []
    skill: str | None = None


class NoteIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


# ---- health ------------------------------------------------------------------------

@app.get("/api/health")
def health():
    try:
        tags = httpx.get(f"{agent.OLLAMA_URL}/api/tags", timeout=3).json()
        models = [m["name"] for m in tags.get("models", [])]
        return {"api": "ok", "ollama": "ok", "model": agent.MODEL, "model_installed": agent.MODEL in models,
                "embed_model_installed": any(m.startswith("nomic-embed-text") for m in models), "models": models}
    except httpx.HTTPError:
        return {"api": "ok", "ollama": "down", "model": agent.MODEL, "model_installed": False, "embed_model_installed": False, "models": []}


# ---- tasks (unchanged contract) ---------------------------------------------------------

@app.get("/api/tasks")
def get_tasks(status: str = "all"):
    return db.list_tasks(status)


@app.post("/api/tasks", status_code=201)
def post_task(t: TaskIn):
    return db.create_task(t.title, t.priority, t.due)


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, p: TaskPatch):
    try:
        return db.update_task(task_id, p.title, p.priority, p.due, p.done)
    except LookupError:
        raise HTTPException(404, "task not found")


@app.post("/api/tasks/{task_id}/complete")
def post_complete(task_id: int):
    return patch_task(task_id, TaskPatch(done=True))


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """Direct UI delete (the user clicked it). Agent deletes go through /api/pending."""
    try:
        return db.delete_task(task_id)
    except LookupError:
        raise HTTPException(404, "task not found")


@app.post("/api/tasks/restore", status_code=201)
def restore_task(t: TaskFull):
    return db.restore_task(t.model_dump())


# ---- agent -------------------------------------------------------------------------

@app.post("/api/chat")
def post_chat(body: ChatIn):
    try:
        return agent.chat(body.message, history=[h.model_dump() for h in body.history], skill=body.skill)
    except httpx.HTTPError as e:
        raise HTTPException(503, f"Ollama unavailable: {e}")
    except Exception as e:  # a bug must never look like an Ollama outage
        raise HTTPException(500, f"The agent hit an unexpected error ({type(e).__name__}). Nothing was changed.")


@app.get("/api/skills")
def get_skills():
    return [s.card() for s in skills.load().values()]


@app.get("/api/runs")
def get_runs(limit: int = 30):
    return store.list_runs(limit)


@app.get("/api/runs/{run_id}")
def get_run(run_id: int):
    r = store.get_run(run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return r


@app.get("/api/pending")
def get_pending():
    return store.list_pending()


@app.post("/api/pending/{pid}/{decision}")
def decide_pending(pid: int, decision: str):
    from . import runtime
    if decision not in ("confirm", "cancel"):
        raise HTTPException(400, "decision must be confirm or cancel")
    try:
        return {"pending": runtime.confirm(pid, decision == "confirm"), "tasks": db.list_tasks()}
    except LookupError:
        raise HTTPException(404, "no such pending action")


# ---- knowledge ------------------------------------------------------------------------

@app.get("/api/documents")
def get_documents():
    return store.list_documents()


@app.post("/api/documents", status_code=201)
async def upload_document(file: UploadFile = File(...)):
    from . import rag
    data = await file.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "file larger than 15 MB")
    t0 = time.perf_counter()
    try:
        out = rag.ingest(os.path.basename(file.filename or "upload.txt"), data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except httpx.HTTPError as e:
        raise HTTPException(503, f"embedding model unavailable: {e}")
    return {**out, "ms": round((time.perf_counter() - t0) * 1000)}


@app.delete("/api/documents/{doc_id}")
def remove_document(doc_id: int):
    from . import rag
    row = rag.remove(doc_id)
    if row is None:
        raise HTTPException(404, "document not found")
    return row


@app.get("/api/search")
def search(q: str):
    from . import rag
    return rag.search(q)


@app.get("/api/notes")
def get_notes():
    return store.list_notes()


@app.post("/api/notes", status_code=201)
def post_note(n: NoteIn):
    from . import tools
    r = tools.execute("add_note", n.model_dump())
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return r["note"]


@app.post("/api/demo/reset")
def demo_reset():
    """Competition demo helper: reset to labelled sample data. The UI asks for a second click first."""
    from . import demo
    try:
        return demo.reset()
    except httpx.HTTPError as e:
        raise HTTPException(503, f"Ollama embeddings unavailable, nothing was changed: {e}")


# ---- performance ---------------------------------------------------------------------------

@app.get("/api/bench")
def bench_models():
    """Live model memory as reported by Ollama (/api/ps). No synthetic numbers."""
    try:
        ps = httpx.get(f"{agent.OLLAMA_URL}/api/ps", timeout=3).json()
    except httpx.HTTPError:
        raise HTTPException(503, "Ollama unavailable")
    return [{"name": m["name"], "size_mb": round(m.get("size", 0) / 2**20), "vram_mb": round(m.get("size_vram", 0) / 2**20),
             "quant": m.get("details", {}).get("quantization_level"), "params": m.get("details", {}).get("parameter_size")}
            for m in ps.get("models", [])]


@app.get("/api/bench/results")
def bench_results():
    import json
    path = os.path.join(ROOT, "docs", "benchmark.json")
    if os.path.exists(path):
        return json.load(open(path, encoding="utf-8"))
    # Real measurements from benchmarks/quantization_bench.py, mapped to the panel's row shape.
    q = os.path.join(ROOT, "benchmarks", "quantization_results.json")
    if not os.path.exists(q):
        return {"results": []}
    d = json.load(open(q, encoding="utf-8"))
    rows = [{"model": f'{m["model"]} ({m["quantization"]})', "scenario": "3 checks x trials", "runs": m["quality"]["total"],
             "passed": m["quality"]["passed"], "p50_ms": round((m["wall_s_median"] or 0) * 1000),
             "max_ms": round((m["wall_s_max"] or 0) * 1000), "tok_per_s": m["gen_tok_s_median"], "vram_mb": m["ollama_vram_mib"]}
            for m in d["models"]]
    return {"results": rows, "generated_at": d["generated_at"], "machine": d["machine"]["gpu"]}


# ---- static: React workspace at /, original UI at /lite --------------------------------------

app.mount("/static", StaticFiles(directory=LITE), name="static")


@app.get("/manifest.webmanifest")
def manifest():
    return FileResponse(os.path.join(LITE, "manifest.webmanifest"), media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    return FileResponse(os.path.join(LITE, "sw.js"), media_type="text/javascript", headers={"Cache-Control": "no-cache"})


NO_CACHE = {"Cache-Control": "no-cache"}  # HTML must revalidate, or browsers show a stale UI after updates


@app.get("/lite")
def lite():
    return FileResponse(os.path.join(LITE, "index.html"), headers=NO_CACHE)


if os.path.isdir(os.path.join(WORKSPACE, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(WORKSPACE, "assets")), name="assets")


@app.get("/")
def index():
    built = os.path.join(WORKSPACE, "index.html")
    return FileResponse(built if os.path.exists(built) else os.path.join(LITE, "index.html"), headers=NO_CACHE)
