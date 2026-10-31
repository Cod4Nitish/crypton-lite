# Which skill / agent to use when (fast work process)

Rule from `~/.claude/CLAUDE.md`: single-domain job, do it directly; multi-domain job, decompose and delegate. Skip pipeline stages that are trivial.

## Order of work (fast path)
1. **Look first** (30 s): `ls`, read the 2-3 files involved, run the tests. Never guess state.
2. **Fix what blocks the demo** before anything visual.
3. **Test after every change**: `.venv/Scripts/python -m pytest -q` (about 40 s), `cd web && npx tsc -b && npm run build`.
4. **Document last**, from measured facts only.

## Pick by situation
| Situation | Use |
|---|---|
| Something broke, cause unknown | `debugging` skill / `debugging-agent` |
| New or changed endpoint / tool | `backend-agent` + `backend-development` |
| UI change in `web/` | `frontend-agent`; keep the existing shadcn design system |
| Schema, migration, slow query | `database-agent` |
| RAG quality, chunking, citations | `rag-agent` + `rag-engineering` |
| Prompt / tool-calling behaviour | `ai-agent`, `prompt-engineering`, `tool-engineering` |
| Write or fix tests | `testing-agent` + `testing` |
| Facts you cannot verify (rules, library status, past winners) | `research-agent` (read-only, web) |
| Review before submitting | `/code-review`, `security-review-agent` |
| Docs / README / runbook | `documentation-agent` |
| Pipeline, CI, env | `devops-agent`; releases: `deployment-agent` (asks before prod) |
| Unclear goal or big task | `planner` first, then the specialists |

## CRYPTON's own runtime skills (`skills/`)
| Skill | Say things like | Tools |
|---|---|---|
| `task-management` (default) | "add a task...", "complete...", "delete..." | create/list/complete/update/delete_task |
| `document-qa` | "summarize the agenda", "when do submissions close" | search_documents |
| `planning-briefing` | "create prep tasks from the agenda", "plan my day" | search_documents, list_tasks, create_task |
| `knowledge-notes` | "remember that...", "what notes do I have" | add_note, list_notes, search_documents |

## Parallel vs sequential
Parallel: docs + benchmark + tests (independent). Sequential: architecture, then implementation, then tests.

## Winning research
You mentioned an agent for researching past winners. Use `research-agent` with: "Find past WeMakeDevs hackathon winners and judging criteria; cite sources; separate facts from guesses." It cannot be verified from this machine, and no result is included here.
