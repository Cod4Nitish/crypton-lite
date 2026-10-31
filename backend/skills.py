"""Agent Skills (SKILL.md, agentskills.io format) with lazy loading.

At startup only frontmatter (name, description, allowed-tools, triggers) is read.
A skill's instruction body is read from disk only when the router selects it, so
the prompt carries one skill's instructions and tools, never all of them.
"""
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")
DEFAULT = "task-management"


@dataclass
class Skill:
    name: str
    description: str
    tools: list[str]
    triggers: set[str]
    path: str
    _body: str | None = field(default=None, repr=False)

    def instructions(self) -> str:
        if self._body is None:  # lazy load
            text = open(self.path, encoding="utf-8").read()
            self._body = text.split("---", 2)[2].strip()
        return self._body

    def card(self) -> dict:
        return {"name": self.name, "description": self.description, "tools": self.tools}


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.S)
    meta, block = {}, None
    for line in (m.group(1) if m else "").splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and block:
            k, _, v = line.strip().partition(":")
            meta.setdefault(block, {})[k.strip()] = v.strip()
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v:
            meta[k], block = v, None
        else:
            block = k
    return meta


@lru_cache(maxsize=1)
def load() -> dict[str, Skill]:
    skills = {}
    for d in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, d, "SKILL.md")
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            head = f.read(2000)  # frontmatter only
        meta = _frontmatter(head)
        triggers = (meta.get("metadata") or {}).get("triggers", "")
        skills[meta["name"]] = Skill(meta["name"], meta.get("description", ""), meta.get("allowed-tools", "").split(),
                                     {_stem(w) for w in triggers.split()}, path)
    return skills


def _stem(w: str) -> str:
    return w.lower()[:5]


def route(message: str, override: str | None = None) -> tuple[Skill, str]:
    """Intent recognition: keyword-stem scoring against each skill's triggers.
    Deterministic and ~0 ms, so no extra LLM call is spent on routing."""
    skills = load()
    if override and override in skills:
        return skills[override], "selected by user"
    words = {_stem(w) for w in re.findall(r"[a-zA-Z]+", message)}
    # A pasted web address means "read this page", unless the user asked to open it.
    if re.search(r"https?://|www\.", message) and "web-research" in skills and not words & {_stem(w) for w in ("open", "launch", "visit")}:
        return skills["web-research"], "message contains a web address"
    scores = {name: len(words & s.triggers) for name, s in skills.items()}
    # A request that mixes documents and tasks ("create prep tasks from the agenda") is planning.
    if scores.get("document-qa", 0) and scores.get("task-management", 0) and "planning-briefing" in skills:
        scores["planning-briefing"] += 2
    best = max(scores, key=lambda n: (scores[n], n == DEFAULT))
    if scores[best] == 0:
        return skills[DEFAULT], "no strong signal; default skill"
    matched = sorted(words & skills[best].triggers)
    return skills[best], f"matched {', '.join(matched[:5])}"
