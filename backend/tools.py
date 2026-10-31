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
    part: int = Field(1, ge=1, le=50, description="Which part of a long page to read; 1 is the start")


class ResearchWeb(Args):
    query: str = Field(min_length=2, max_length=300, description="Topic to research: searches the web and reads the top pages")


class SavePage(Args):
    url: str = Field(min_length=8, max_length=500, description="Full page URL to save into the user's documents")


class OpenApp(Args):
    name: str = Field(description="App to open, e.g. notepad, calculator, chrome, vscode, file explorer, paint, word, excel")


class OpenFolder(Args):
    name: str = Field(description="Folder to open: downloads, documents, desktop, pictures or project")


class OpenUrl(Args):
    url: str = Field(min_length=8, max_length=500, description="Website address starting with http:// or https://")


class SearchBrowser(Args):
    query: str = Field(min_length=2, max_length=200, description="What to search for in the web browser")


class PlayMusic(Args):
    query: str = Field(min_length=2, max_length=200, description="Song, artist or video to play, e.g. 'Karan Aujla song'")


class ListFiles(Args):
    folder: str = Field("downloads", description="desktop, documents, downloads, pictures, videos or project")
    sub: str = Field("", description="Optional sub-folder inside it")


class FindFiles(Args):
    query: str = Field(min_length=2, max_length=100, description="Part of a file or folder name to look for")
    folder: str = Field("all", description="all, or desktop, documents, downloads, pictures, videos, project")


class FilePath(Args):
    path: str = Field(min_length=2, max_length=400, description="File path, e.g. downloads/notes.txt, or a full path from list_files/find_files")


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
        return anakin.scrape(a.url, a.part)
    except anakin.AnakinError as e:
        raise ValueError(str(e))


def _open_app(a: OpenApp):
    from . import system
    return system.open_app(a.name.strip().lower())


def _open_folder(a: OpenFolder):
    from . import system
    return system.open_folder(a.name.strip().lower())


def _open_url(a: OpenUrl):
    from . import system
    return system.open_url(a.url)


def _search_browser(a: SearchBrowser):
    from . import system
    return system.search_in_browser(a.query)


def _research_web(a: ResearchWeb):
    from . import anakin
    try:
        return anakin.research(a.query)
    except anakin.AnakinError as e:
        raise ValueError(str(e))


def _save_page(a: SavePage):
    from . import anakin, rag
    try:
        host, text = anakin.page_for_saving(a.url)
    except anakin.AnakinError as e:
        raise ValueError(str(e))
    out = rag.ingest(f"web-{host}.md", text.encode("utf-8"), source_id="web")
    doc = out["document"]
    return {"saved_as": doc["name"], "chunks": doc["chunks"], "already_saved": out["cached"],
            "note": "The user can now ask questions about it and get citations."}


def _play_music(a: PlayMusic):
    from . import system
    return system.play_media(a.query)


def _list_files(a: ListFiles):
    from . import system
    return system.list_files(a.folder, a.sub)


def _find_files(a: FindFiles):
    from . import system
    return system.find_files(a.query, a.folder)


def _read_file(a: FilePath):
    from . import system
    return system.read_file(a.path)


def _open_file(a: FilePath):
    from . import system
    return system.open_file(a.path)


def _screenshot(a: NoArgs):
    from . import system
    return system.screenshot()


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
    Tool(name="open_app", description="Open an app on the user's computer (notepad, calculator, chrome, vscode...).", args=OpenApp, handler=_open_app),
    Tool(name="open_folder", description="Open a folder in File Explorer (downloads, documents, desktop, pictures, project).", args=OpenFolder, handler=_open_folder),
    Tool(name="open_url", description="Open a website in the user's browser.", args=OpenUrl, handler=_open_url),
    Tool(name="search_browser", description="Open a Google search for a query in the user's browser.", args=SearchBrowser, handler=_search_browser),
    Tool(name="research_web", description="Research a topic: search the web and read the top pages (Anakin.io). Best for questions needing facts from several sources.", args=ResearchWeb, handler=_research_web),
    Tool(name="save_page", description="Scrape a web page and save it into the user's documents so it can be searched with citations.", args=SavePage, handler=_save_page),
    Tool(name="play_music", description="Play a song or video: finds it on YouTube and opens it in the user's browser.", args=PlayMusic, handler=_play_music),
    Tool(name="list_files", description="List the newest files in one of the user's folders (desktop, documents, downloads, pictures, videos, project).", args=ListFiles, handler=_list_files),
    Tool(name="find_files", description="Find files or folders by name in the user's folders.", args=FindFiles, handler=_find_files),
    Tool(name="read_file", description="Read a text file from the user's folders.", args=FilePath, handler=_read_file),
    Tool(name="open_file", description="Open a file in its normal app (pdf, image, document). Programs and scripts are refused.", args=FilePath, handler=_open_file),
    Tool(name="take_screenshot", description="Take a screenshot of the whole screen and save it to Pictures/Screenshots.", args=NoArgs, handler=_screenshot),
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
