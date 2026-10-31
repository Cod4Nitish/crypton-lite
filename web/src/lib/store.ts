// Tiny external store (observer pattern) shared by chat, inspector and sidebar.
import { useSyncExternalStore } from "react"
import { api } from "./api"
import type { ChatResult, Doc, Health, Run, SkillCard, Task } from "./api"

export type InspectorTab = "timeline" | "sources" | "tasks" | "runs" | "perf"
export interface TaskDiff { added: number[]; changed: number[]; removed: Task[] }

interface State {
  tasks: Task[]
  runs: Run[]
  docs: Doc[]
  skills: SkillCard[]
  skill: string | null // null = auto-route
  health: Health | null
  selectedRun: number | null
  highlight: number | null // citation number to highlight in Sources
  tab: InspectorTab
  diff: TaskDiff | null
  busy: boolean
}

let state: State = {
  tasks: [], runs: [], docs: [], skills: [], skill: null, health: null,
  selectedRun: null, highlight: null, tab: "timeline", diff: null, busy: false,
}
const listeners = new Set<() => void>()

export function setState(patch: Partial<State> | ((s: State) => Partial<State>)) {
  state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) }
  listeners.forEach((l) => l())
}
export const getState = () => state
export function useStore<T>(select: (s: State) => T): T {
  return useSyncExternalStore((l) => (listeners.add(l), () => listeners.delete(l)), () => select(state))
}

export function diffTasks(before: Task[], after: Task[]): TaskDiff {
  const prev = new Map(before.map((t) => [t.id, t]))
  const next = new Set(after.map((t) => t.id))
  return {
    added: after.filter((t) => !prev.has(t.id)).map((t) => t.id),
    changed: after.filter((t) => prev.has(t.id) && JSON.stringify(prev.get(t.id)) !== JSON.stringify(t)).map((t) => t.id),
    removed: before.filter((t) => !next.has(t.id)),
  }
}

/** Called by the chat adapter after every real agent run. */
export function recordRun(res: ChatResult, message: string, before: Task[]) {
  const run: Run = {
    id: res.run_id, message, skill: res.skill, reply: res.reply, status: res.status,
    steps: res.steps, sources: res.sources, latency_ms: res.latency_ms, created_at: new Date().toISOString(),
  }
  setState((s) => ({
    tasks: res.tasks,
    diff: diffTasks(before, res.tasks),
    runs: [run, ...s.runs.filter((r) => r.id !== run.id)],
    selectedRun: run.id,
    highlight: null,
  }))
}

export async function refresh() {
  const [tasks, runs, docs, skills] = await Promise.all([api.tasks(), api.runs(), api.docs(), api.skills()])
  setState({ tasks, runs, docs, skills })
}

export async function refreshHealth() {
  try {
    setState({ health: await api.health() })
  } catch {
    setState({ health: null })
  }
}
