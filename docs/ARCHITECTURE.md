# CRYPTON architecture (one page)

**Problem / user:** an event attendee or organizer turns spoken or typed commands and an event agenda into tracked prep tasks, privately and quickly, on a laptop.

```
Wispr Flow / browser mic / keyboard  ->  text box (React, assistant-ui)
        (speech is cloud; typing works offline)
                |  POST /api/chat
                v
FastAPI -> LangGraph:  route -> load_skill -> llm <-> tools -> finalize
                         |            |         |        |
                  keyword router  SKILL.md   Ollama   Pydantic-validated
                  (0 ms, no LLM)  lazy load  qwen3.5  allow-listed tools
                                              :4b      (delete needs confirm)
                |                                        |
        SQLite (tasks, runs/traces,              ChromaDB + nomic-embed-text
        notes, pending, documents)               (page-aware chunks, cosine)
```

- **Skills** (`skills/*/SKILL.md`): only the chosen skill's instructions and tools enter the prompt.
- **Trace:** every node records a real step with `perf_counter` ms; LLM steps add token counts and tok/s from Ollama; stored in SQLite and shown in the Inspector.
- **Citations:** passages are numbered globally; any `[n]` the model invents that has no real chunk is stripped.
- **Safety:** unknown tool or bad arguments return an error to the model; `create_task` is idempotent; the LLM call retries once on transport errors; tool calls are never retried; deletes wait for user confirmation.
- **Local vs cloud:** model, embeddings, vector store, tools, DB are local. Speech-to-text is not.
- **Limits:** one 4B model, keyword routing, 15 MB uploads, no OCR, no multi-user auth.
