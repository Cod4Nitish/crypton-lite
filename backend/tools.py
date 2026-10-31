"""Tool registry: every tool the agent may call, with Pydantic-validated arguments.

Strict allowlist: the runtime only executes names in REGISTRY *and* in the active
skill's allowed-tools. Tools marked `confirm=True` never run directly; they create a
pending action that the user must approve in the UI.
"""
from datetime import date, timedelta
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from . import db, store


class Args(BaseModel):
    model_config = ConfigDict(extra="ignore")  # models sometimes add stray keys


def _norm_due(v):
    if v in (None, ""):
        return None
    s = str(v).strip().lower()
    if s == "today":
        return date.today().isoformat()
    if s == "tomorrow":
        return (date.today() + timedelta(days=1)).isoformat()
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        raise ValueError("due must be YYYY-MM-DD")


def _norm_priority(v):
    return None if v in (None, "") else str(v).strip().lower()


class TaskRef(Args):
    task_id: int | None = Field(None, description="Task id if known")
    title: str | None = Field(None, description="Part of the task title, if the id is unknown")


class CreateTask(Args):
    title: str = Field(min_length=1, max_length=200, description="Short task title without priority/date words")
    priority: Literal["low", "medium", "high"] = "medium"
    due: str | None = Field(None, description="Due date YYYY-MM-DD, only if the user or document gave one")

    @field_validator("priority", mode="before")
    @classmethod
    def _prio(cls, v):
        return _norm_priority(v) or "medium"

    @field_validator("due", mode="before")
    @classmethod
    def _due(cls, v):
        return _norm_due(v)


class ListTasks(Args):
    status: Literal["all", "open", "done"] = "all"


class UpdateTask(TaskRef):
    new_title: str | None = Field(None, max_length=200)
    priority: Literal["low", "medium", "high"] | None = None
    due: str | None = Field(None, description="Due date YYYY-MM-DD")

    @field_validator("priority", mode="before")
    @classmethod
    def _prio(cls, v):
        return _norm_priority(v)

    @field_validator("due", mode="before")
    @classmethod
    def _due(cls, v):
        return _norm_due(v)


class SearchDocuments(Args):
    query: str = Field(min_length=2, max_length=300, description="What to look for in the uploaded documents and notes")


class AddNote(Args):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


class WebSearch(Args):
    query: str = Field(min_length=2, max_length=300, description="What to look up on the web")


class ScrapeUrl(Args):
    url: str = Field(min_length=8, max_length=500, description="Full page URL starting with http:// or https://")


class NoArgs(Args):
    pass


class Tool(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    name: str
    description: str
    args: type[Args]
    handler: Callable[..., dict]
    confirm: bool = False

    def schema(self) -> dict:
        params = self.args.model_json_schema()
        params.pop("title", None)
        for p in params.get("properties", {}).values():
            p.pop("title", None)
            p.pop("default", None)
            if "anyOf" in p:  # flatten Optional[X] -> X for small models
                types = [t for t in p.pop("anyOf") if t.get("type") != "null"]
                p.update(types[0] if types else {})
        return {"type": "function", "function": {"name": self.name, "description": self.description, "parameters": params}}


def resolve_id(ref: TaskRef) -> int:
    if ref.task_id is not None:
        return ref.task_id
    if ref.title:
        t = db.find_open_by_title(ref.title)
        if t:
            return t["id"]
    raise LookupError("task not found")


# ---- handlers (args are already validated) --------------------------------------

def _create(a: CreateTask):
    # Idempotent: a repeated command (model retry, double voice send) must not duplicate a task.
    dup = db.find_duplicate_open(a.title, a.due)
    if dup:
        return {"task": dup, "duplicate": True}
    return {"task": db.create_task(a.title, a.priority, a.due)}


def _list(a: ListTasks):
    return {"tasks": db.list_tasks(a.status)}


def _complete(a: TaskRef):
    return {"task": db.update_task(resolve_id(a), done=True)}


def _update(a: UpdateTask):
    return {"task": db.update_task(resolve_id(a), title=a.new_title, priority=a.priority, due=a.due)}


def _delete(a: TaskRef):
    return {"task": db.delete_task(resolve_id(a))}


def _search(a: SearchDocuments):
    from . import rag  # lazy: chromadb import is slow and only needed here
    return rag.search(a.query)


def _web_search(a: WebSearch):
    from . import anakin
    try:
        return anakin.search(a.query)
    except anakin.AnakinError as e:
        raise ValueError(str(e))


def _scrape_url(a: ScrapeUrl):
    from . import anakin
    try:
        return anakin.scrape(a.url)
    except anakin.AnakinError as e:
        raise ValueError(str(e))


def _add_note(a: AddNote):
    from . import rag
    note = store.add_note(a.title, a.body)
    rag.ingest(f"note-{note['id']}-{a.title[:40]}.md", f"# {a.title}\n\n{a.body}".encode(), source_id="note")
    return {"note": note}


def _list_notes(a: NoArgs):
    return {"notes": store.list_notes()[:20]}


REGISTRY: dict[str, Tool] = {t.name: t for t in [
    Tool(name="create_task", description="Create a new task.", args=CreateTask, handler=_create),
    Tool(name="list_tasks", description="List the user's tasks.", args=ListTasks, handler=_list),
    Tool(name="complete_task", description="Mark a task as done.", args=TaskRef, handler=_complete),
    Tool(name="update_task", description="Change a task's title, priority or due date.", args=UpdateTask, handler=_update),
    Tool(name="delete_task", description="Delete a task permanently (the user must confirm).", args=TaskRef, handler=_delete, confirm=True),
    Tool(name="search_documents", description="Semantic search over uploaded documents and saved notes.", args=SearchDocuments, handler=_search),
    Tool(name="web_search", description="Search the live web (Anakin.io). Returns titles, URLs and snippets.", args=WebSearch, handler=_web_search),
    Tool(name="scrape_url", description="Read the text of one web page (Anakin.io).", args=ScrapeUrl, handler=_scrape_url),
    Tool(name="add_note", description="Save a knowledge note.", args=AddNote, handler=_add_note),
    Tool(name="list_notes", description="List saved notes.", args=NoArgs, handler=_list_notes),
]}


def validate(name: str, raw: dict) -> Args:
    return REGISTRY[name].args.model_validate(raw or {})


def execute(name: str, raw: dict, allowed: set[str] | None = None, confirmed: bool = False) -> dict:
    """Validate and run one tool call. Never raises; errors go back to the model."""
    if name not in REGISTRY or (allowed is not None and name not in allowed):
        return {"ok": False, "error": f"tool '{name}' is not allowed here"}
    tool = REGISTRY[name]
    try:
        args = validate(name, raw)
    except ValidationError as e:
        return {"ok": False, "error": "invalid arguments: " + "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors())}
    try:
        if tool.confirm and not confirmed:
            tid = resolve_id(args)
            task = next((t for t in db.list_tasks() if t["id"] == tid), None)
            pending = store.add_pending(name, {"task_id": tid}, f'Delete task #{tid} "{task["title"] if task else "?"}"')
            return {"ok": True, "needs_confirmation": True, "pending": pending,
                    "note": "Not executed yet. Waiting for the user to confirm in the UI."}
        return {"ok": True, **tool.handler(args)}
    except (ValueError, LookupError) as e:
        return {"ok": False, "error": str(e)}
