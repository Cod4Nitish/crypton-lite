"""CRYPTON agent runtime as an explicit LangGraph state graph.

    route ─> load_skill ─> llm ──(tool calls?)──> tools ─┐
                            ^                            │
                            └────────────────────────────┘
                            └──(final answer / step cap)──> finalize ─> END

Every node appends a real, timed step to `steps`; the UI timeline renders exactly
these. Nothing is simulated: timings come from perf_counter, token stats from Ollama.
"""
import json
import re
import time
from datetime import date
from typing import Any, TypedDict

import httpx
from langgraph.graph import END, StateGraph

from . import db, skills, store, tools
from . import agent
from .agent import _content_tool_call

MAX_LLM_CALLS = 6
MAX_TOOL_CALLS = 8
LLM_TIMEOUT = 90
PASSAGE_CHARS = 700


class State(TypedDict, total=False):
    message: str
    history: list[dict]
    skill_override: str | None
    client: Any
    skill: str
    allowed: list[str]
    messages: list[dict]
    pending_calls: list[dict]
    steps: list[dict]
    actions: list[dict]
    sources: list[dict]
    pending: list[dict]
    llm_calls: int
    tool_calls: int
    reply: str
    status: str


def _ms(t0: float) -> int:
    return round((time.perf_counter() - t0) * 1000)


def _step(state: State, kind: str, t0: float, **data) -> list[dict]:
    return state.get("steps", []) + [{"type": kind, "ms": _ms(t0), **data}]


# ---- nodes --------------------------------------------------------------------------

def route_node(state: State) -> State:
    t0 = time.perf_counter()
    skill, why = skills.route(state["message"], state.get("skill_override"))
    return {"skill": skill.name, "steps": _step(state, "route", t0, skill=skill.name, reason=why)}


def load_skill_node(state: State) -> State:
    t0 = time.perf_counter()
    skill = skills.load()[state["skill"]]
    today = date.today()
    system = (
        f"You are CRYPTON, a concise local voice agent. Today is {today.strftime('%A')} {today.isoformat()}.\n"
        f"Active skill: {skill.name}. Use only the provided tools; never claim an action a tool did not perform.\n\n"
        + skill.instructions()
    )
    msgs = [{"role": "system", "content": system}]
    msgs += [m for m in (state.get("history") or [])[-6:] if m.get("role") in ("user", "assistant") and m.get("content")]
    msgs.append({"role": "user", "content": state["message"]})
    return {
        "allowed": skill.tools,
        "messages": msgs,
        "steps": _step(state, "skill_loaded", t0, skill=skill.name, tools=skill.tools, prompt_chars=len(system)),
    }


LLM_RETRIES = 1  # one extra attempt, only for transient transport errors; the LLM call has no side effects


def _ns_to_ms(ns) -> int | None:
    return round(ns / 1e6) if ns else None


def _post_llm(client, payload: dict) -> tuple[dict, int]:
    """POST to Ollama. Retries once on connection/timeout/5xx. Tool calls are never retried here."""
    for attempt in range(1, LLM_RETRIES + 2):
        try:
            r = client.post(f"{agent.OLLAMA_URL}/api/chat", json=payload)
            if r.status_code >= 500 and attempt <= LLM_RETRIES:
                continue
            r.raise_for_status()
            return r.json(), attempt
        except (httpx.TransportError, httpx.TimeoutException):
            if attempt > LLM_RETRIES:
                raise
    raise httpx.HTTPError("unreachable")


def llm_node(state: State) -> State:
    t0 = time.perf_counter()
    client = state.get("client") or httpx.Client(timeout=LLM_TIMEOUT)
    schemas = [tools.REGISTRY[n].schema() for n in state["allowed"] if n in tools.REGISTRY]
    payload = {
        "model": agent.MODEL, "messages": state["messages"], "tools": schemas, "stream": False, "think": False,
        "keep_alive": "30m", "options": {"temperature": 0.2},
    }
    data, attempts = _post_llm(client, payload)
    msg = data["message"]
    calls = msg.get("tool_calls") or _content_tool_call(msg.get("content", ""))
    ev, dur = data.get("eval_count"), data.get("eval_duration")
    stats = {"prompt_tokens": data.get("prompt_eval_count"), "output_tokens": ev,
             "tok_per_s": round(ev / (dur / 1e9), 1) if ev and dur else None}
    out: State = {
        "llm_calls": state.get("llm_calls", 0) + 1,
        "pending_calls": calls,
        "steps": _step(state, "llm", t0, model=agent.MODEL, planned=[c["function"]["name"] for c in calls],
                       attempts=attempts, load_ms=_ns_to_ms(data.get("load_duration")), **stats),
    }
    if calls:
        out["messages"] = state["messages"] + [{"role": "assistant", "content": msg.get("content", ""), "tool_calls": calls}]
    else:
        out["reply"] = (msg.get("content") or "").strip()
    return out


def tools_node(state: State) -> State:
    steps, actions = list(state.get("steps", [])), list(state.get("actions", []))
    sources, pending = list(state.get("sources", [])), list(state.get("pending", []))
    messages, count = list(state["messages"]), state.get("tool_calls", 0)
    for call in state.get("pending_calls", []):
        t0 = time.perf_counter()
        name = call["function"]["name"]
        args = call["function"].get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args or "{}")
            except json.JSONDecodeError:
                args = {}
        if count >= MAX_TOOL_CALLS:
            result = {"ok": False, "error": "tool call limit reached"}
        else:
            count += 1
            result = tools.execute(name, args, allowed=set(state["allowed"]))
        model_view = result
        if name == "search_documents" and result.get("ok"):
            # number passages globally so citations [n] map to exactly one real chunk
            numbered = []
            for ch in result.get("chunks", []):
                sources.append({"n": len(sources) + 1, **ch})
                numbered.append({"n": len(sources), "doc": ch["doc"], "page": ch["page"], "text": ch["text"][:PASSAGE_CHARS]})
            model_view = {"ok": True, "passages": numbered, "insufficient": result["insufficient"], **({"reason": result["reason"]} if "reason" in result else {})}
        if result.get("needs_confirmation"):
            pending.append(result["pending"])
        actions.append({"tool": name, "args": args, "result": result})
        steps.append({"type": "tool", "ms": _ms(t0), "tool": name, "args": args, "ok": result.get("ok", False),
                      "needs_confirmation": bool(result.get("needs_confirmation")),
                      "error": result.get("error"), "summary": _summarize(name, result)})
        messages.append({"role": "tool", "tool_name": name, "content": json.dumps(model_view, default=str)})
    return {"steps": steps, "actions": actions, "sources": sources, "pending": pending,
            "messages": messages, "tool_calls": count, "pending_calls": []}


def finalize_node(state: State) -> State:
    t0 = time.perf_counter()
    reply = state.get("reply") or ("Stopped after the step limit." if state.get("pending_calls") else "Done.")
    n_sources = len(state.get("sources", []))
    cited = {int(n) for n in re.findall(r"\[(\d+)\]", reply)}
    invalid = sorted(n for n in cited if n < 1 or n > n_sources)
    if invalid:  # never let an invented citation through
        reply = re.sub(r"\[(\d+)\]", lambda m: m.group(0) if 1 <= int(m.group(1)) <= n_sources else "", reply).strip()
    status = "needs_confirmation" if state.get("pending") else "ok"
    return {"reply": reply, "status": status,
            "steps": _step(state, "final", t0, citations=sorted(cited - set(invalid)), removed_citations=invalid)}


def _summarize(name: str, r: dict) -> str:
    if not r.get("ok"):
        return r.get("error", "failed")
    if r.get("needs_confirmation"):
        return "awaiting confirmation: " + r["pending"]["summary"]
    if r.get("duplicate"):
        return f'already exists: #{r["task"]["id"]} "{r["task"]["title"]}" (not duplicated)'
    if "task" in r:
        return f'#{r["task"]["id"]} "{r["task"]["title"]}"'
    if "tasks" in r:
        return f'{len(r["tasks"])} tasks'
    if "chunks" in r:
        return f'{len(r["chunks"])} passages' + (" (insufficient evidence)" if r["insufficient"] else "")
    if "note" in r:
        return f'note #{r["note"]["id"]} saved'
    if "notes" in r:
        return f'{len(r["notes"])} notes'
    return "ok"


def _after_llm(state: State) -> str:
    if state.get("pending_calls") and state.get("llm_calls", 0) < MAX_LLM_CALLS:
        return "tools"
    return "finalize"


def build_graph():
    g = StateGraph(State)
    g.add_node("route", route_node)
    g.add_node("load_skill", load_skill_node)
    g.add_node("llm", llm_node)
    g.add_node("tools", tools_node)
    g.add_node("finalize", finalize_node)
    g.set_entry_point("route")
    g.add_edge("route", "load_skill")
    g.add_edge("load_skill", "llm")
    g.add_conditional_edges("llm", _after_llm, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "llm")
    g.add_edge("finalize", END)
    return g.compile()


GRAPH = build_graph()


def run(message: str, history: list[dict] | None = None, skill: str | None = None, client=None) -> dict:
    """Execute one agent run and persist its trace. Raises httpx.HTTPError if Ollama is down."""
    t0 = time.perf_counter()
    try:
        final = GRAPH.invoke({"message": message, "history": history or [], "skill_override": skill, "client": client,
                              "steps": [], "actions": [], "sources": [], "pending": []},
                             {"recursion_limit": 4 + MAX_LLM_CALLS * 2})
    except httpx.HTTPError as e:
        store.save_run(message, None, None, "error", [{"type": "error", "ms": _ms(t0), "error": str(e)}], [], _ms(t0))
        raise
    latency = _ms(t0)
    run_id = store.save_run(message, final["skill"], final["reply"], final["status"], final["steps"], final["sources"], latency)
    store.attach_pending_to_run([p["id"] for p in final["pending"]], run_id)
    touched = [f'{a["tool"]} #{a["result"]["task"]["id"]} "{a["result"]["task"]["title"]}"'
               for a in final["actions"] if a["result"].get("ok") and "task" in a["result"]]
    llm_ms = sum(x["ms"] for x in final["steps"] if x["type"] == "llm")
    tool_ms = sum(x["ms"] for x in final["steps"] if x["type"] == "tool")
    return {
        "timing": {"total_ms": latency, "llm_ms": llm_ms, "tool_ms": tool_ms,
                   "llm_calls": sum(1 for x in final["steps"] if x["type"] == "llm"),
                   "tool_calls": sum(1 for x in final["steps"] if x["type"] == "tool")},
        "run_id": run_id, "skill": final["skill"], "reply": final["reply"], "status": final["status"],
        "actions": final["actions"], "steps": final["steps"], "sources": final["sources"],
        "pending": final["pending"], "latency_ms": latency,
        "memory": final["reply"] + (f" [actions: {'; '.join(touched)}]" if touched else ""),
        "tasks": db.list_tasks(),
    }


def confirm(pending_id: int, approve: bool) -> dict:
    p = store.get_pending(pending_id)
    if p is None or p["status"] != "pending":
        raise LookupError("no such pending action")
    if not approve:
        return store.resolve_pending(pending_id, "cancelled")
    result = tools.execute(p["tool"], p["args"], confirmed=True)
    return store.resolve_pending(pending_id, "confirmed" if result.get("ok") else "failed", result)
