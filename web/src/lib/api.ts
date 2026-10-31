// Typed client for the FastAPI backend. All URLs are relative (same origin in prod, Vite proxy in dev).

export type Priority = "low" | "medium" | "high"
export interface Task {
  id: number
  title: string
  priority: Priority
  due: string | null
  done: boolean
  created_at: string
  completed_at: string | null
}
export interface Step {
  type: "route" | "skill_loaded" | "llm" | "tool" | "final" | "error"
  ms: number
  skill?: string
  reason?: string
  tools?: string[]
  prompt_chars?: number
  model?: string
  planned?: string[]
  prompt_tokens?: number | null
  output_tokens?: number | null
  tok_per_s?: number | null
  tool?: string
  args?: Record<string, unknown>
  ok?: boolean
  needs_confirmation?: boolean
  error?: string | null
  summary?: string
  citations?: number[]
  removed_citations?: number[]
  attempts?: number
  load_ms?: number | null
}
export interface Source { n: number; doc: string; page: number | null; text: string; score: number }
export interface Pending { id: number; tool: string; args: Record<string, unknown>; summary: string; status: string }
export interface Action { tool: string; args: Record<string, unknown>; result: Record<string, unknown> & { ok: boolean; error?: string } }
export interface ChatResult {
  run_id: number
  skill: string
  reply: string
  status: "ok" | "needs_confirmation"
  actions: Action[]
  steps: Step[]
  sources: Source[]
  pending: Pending[]
  latency_ms: number
  timing: { total_ms: number; llm_ms: number; tool_ms: number; llm_calls: number; tool_calls: number }
  memory: string
  tasks: Task[]
}
export interface Run {
  id: number
  message: string
  skill: string | null
  reply: string | null
  status: string
  steps: Step[]
  sources: Source[]
  latency_ms: number
  created_at: string
}
export interface SkillCard { name: string; description: string; tools: string[] }
export interface Doc { id: number; name: string; sha256: string; pages: number | null; chunks: number; created_at: string }
export interface Health { api: string; ollama: string; model: string; model_installed: boolean; embed_model_installed: boolean; models: string[] }
export interface LoadedModel { name: string; size_mb: number; vram_mb: number; quant: string | null; params: string | null }

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  const r = await fetch(path, init)
  const data = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error((data as { detail?: string }).detail || r.statusText)
  return data as T
}
const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
})

export const api = {
  health: () => req<Health>("/api/health"),
  tasks: () => req<Task[]>("/api/tasks"),
  createTask: (title: string, priority: Priority) => req<Task>("/api/tasks", json("POST", { title, priority })),
  patchTask: (id: number, patch: Partial<Pick<Task, "title" | "priority" | "due" | "done">>) => req<Task>(`/api/tasks/${id}`, json("PATCH", patch)),
  chat: (message: string, history: { role: string; content: string }[], skill: string | null, signal?: AbortSignal) =>
    req<ChatResult>("/api/chat", { ...json("POST", { message, history, skill }), signal }),
  skills: () => req<SkillCard[]>("/api/skills"),
  runs: () => req<Run[]>("/api/runs"),
  decide: (id: number, decision: "confirm" | "cancel") => req<{ pending: Pending & { result?: Action["result"] }; tasks: Task[] }>(`/api/pending/${id}/${decision}`, json("POST")),
  docs: () => req<Doc[]>("/api/documents"),
  upload: (file: File) => {
    const fd = new FormData()
    fd.append("file", file)
    return req<{ document: Doc; cached: boolean; ms: number }>("/api/documents", { method: "POST", body: fd })
  },
  removeDoc: (id: number) => req<Doc>(`/api/documents/${id}`, json("DELETE")),
  demoReset: () => req<{ document: Doc; tasks: Task[]; label: string }>("/api/demo/reset", json("POST")),
  loaded: () => req<LoadedModel[]>("/api/bench"),
  benchResults: () => req<{ results: BenchRow[]; generated_at?: string; machine?: string }>("/api/bench/results"),
}

export interface BenchRow { model: string; scenario: string; runs: number; passed: number; p50_ms: number; max_ms: number; tok_per_s: number | null; vram_mb: number | null }
