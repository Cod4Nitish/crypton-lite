"""Model config + compatibility entry point.

The agent loop itself lives in runtime.py (LangGraph); tools live in tools.py.
`chat()` is kept so existing callers and tests keep working.
"""
import json
import os
import re

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("CRYPTON_MODEL", "qwen3.5:4b")


def _content_tool_call(content: str) -> list[dict]:
    """Some models (e.g. qwen2.5-coder) emit the call as JSON text instead of tool_calls."""
    from .tools import REGISTRY
    m = re.search(r"\{.*\}", content or "", re.S)
    if not m:
        return []
    try:
        obj = json.loads(m.group(0))
    except json.JSONDecodeError:
        return []
    if isinstance(obj, dict) and obj.get("name") in REGISTRY:
        return [{"function": {"name": obj["name"], "arguments": obj.get("arguments") or {}}}]
    return []


def chat(message: str, client=None, history: list[dict] | None = None, skill: str | None = None) -> dict:
    from . import runtime
    return runtime.run(message, history=history, skill=skill, client=client)
