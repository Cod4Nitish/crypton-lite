import { useEffect, useRef, useState, type FC } from "react"
import { Activity, BookOpen, Brain, CheckCircle2, Circle, Cpu, FileText, GitBranch, History, ListTodo, Route, ShieldAlert, Sparkles, Wrench, XCircle } from "lucide-react"
import { api, type BenchRow, type LoadedModel, type Priority, type Step, type Task } from "@/lib/api"
import { setState, useStore, type InspectorTab } from "@/lib/store"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"

const NODE: Record<Step["type"], { label: string; icon: FC<{ className?: string }> }> = {
  route: { label: "route · intent", icon: Route },
  skill_loaded: { label: "load_skill", icon: Sparkles },
  llm: { label: "llm · plan", icon: Brain },
  tool: { label: "tools · execute", icon: Wrench },
  final: { label: "finalize", icon: CheckCircle2 },
  error: { label: "error", icon: XCircle },
}

function StepRow({ s, max }: { s: Step; max: number }) {
  const { label, icon: Icon } = NODE[s.type]
  const bad = s.type === "error" || s.ok === false
  const warn = s.needs_confirmation
  return (
    <li className="relative pl-7">
      <span className={cn("absolute left-0 top-0.5 grid size-5 place-items-center rounded-full border bg-card",
        bad ? "border-destructive text-destructive" : warn ? "border-amber text-amber" : "border-primary/60 text-primary")}>
        <Icon className="size-3" />
      </span>
      <div className="flex items-baseline gap-2">
        <code className="text-xs font-semibold">{s.type === "tool" ? s.tool : label}</code>
        <span className="ml-auto font-mono text-[11px] text-muted-foreground">{s.ms} ms</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded bg-muted">
        <div className={cn("h-full rounded", s.type === "llm" ? "bg-violet" : bad ? "bg-destructive" : "bg-primary")} style={{ width: `${Math.max(2, (s.ms / max) * 100)}%` }} />
      </div>
      <div className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
        {s.type === "route" && <>skill <b className="text-foreground">{s.skill}</b> · {s.reason}</>}
        {s.type === "skill_loaded" && <>lazy-loaded {s.prompt_chars} chars · tools: {s.tools?.join(", ")}</>}
        {s.type === "llm" && <>{s.model} · {s.prompt_tokens ?? "?"} in / {s.output_tokens ?? "?"} out{s.tok_per_s ? ` · ${s.tok_per_s} tok/s` : ""} · {s.planned?.length ? `planned ${s.planned.join(", ")}` : "final answer"}</>}
        {s.type === "tool" && <>{warn && <ShieldAlert className="mr-1 inline size-3 text-amber" />}{s.summary}<div className="font-mono text-[10px] opacity-80">{JSON.stringify(s.args)}</div></>}
        {s.type === "final" && <>citations {s.citations?.length ? s.citations.map((c) => `[${c}]`).join(" ") : "none"}{s.removed_citations?.length ? ` · removed invalid ${s.removed_citations.map((c) => `[${c}]`).join(" ")}` : ""}</>}
        {s.type === "error" && s.error}
      </div>
    </li>
  )
}

function Timeline() {
  const run = useStore((s) => s.runs.find((r) => r.id === s.selectedRun) ?? s.runs[0])
  const busy = useStore((s) => s.busy)
  if (!run) return <Empty icon={GitBranch} text="Run a command to see the real LangGraph execution trace here." />
  const max = Math.max(...run.steps.map((s) => s.ms), 1)
  return (
    <div>
      <div className="mb-3 rounded-lg border bg-background/40 p-2.5 text-xs">
        <div className="flex items-center gap-2"><Badge variant="secondary">run #{run.id}</Badge><Badge variant="outline">{run.skill}</Badge>
          <span className="ml-auto font-mono">{(run.latency_ms / 1000).toFixed(2)} s</span></div>
        <p className="mt-1.5 line-clamp-2 text-muted-foreground">“{run.message}”</p>
      </div>
      {busy && <p className="mb-2 text-xs text-violet">A new run is in progress…</p>}
      <ol className="relative space-y-3 before:absolute before:bottom-2 before:left-2.5 before:top-2 before:w-px before:bg-border">
        {run.steps.map((s, i) => <StepRow key={i} s={s} max={max} />)}
      </ol>
      <p className="mt-4 text-[10px] text-muted-foreground">Graph: route → load_skill → llm ⇄ tools → finalize. Timings are measured server-side; token stats come from Ollama.</p>
    </div>
  )
}

function Sources() {
  const run = useStore((s) => s.runs.find((r) => r.id === s.selectedRun) ?? s.runs[0])
  const hl = useStore((s) => s.highlight)
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => ref.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }), [hl])
  if (!run?.sources.length) return <Empty icon={BookOpen} text="Retrieved passages appear here with document and page. Ask about an uploaded document." />
  return (
    <ul className="space-y-2">
      {run.sources.map((src) => (
        <li key={src.n} ref={src.n === hl ? ref : undefined}
          className={cn("rounded-lg border bg-background/40 p-2.5 text-xs transition", src.n === hl && "border-primary ring-2 ring-primary/30")}>
          <div className="mb-1 flex items-center gap-2">
            <span className="grid size-5 place-items-center rounded bg-primary/15 text-[11px] font-semibold text-primary">{src.n}</span>
            <FileText className="size-3.5 text-muted-foreground" /><b className="truncate">{src.doc}</b>
            {src.page && <Badge variant="outline" className="h-5 text-[10px]">p.{src.page}</Badge>}
            <span className="ml-auto font-mono text-[10px] text-muted-foreground">sim {src.score}</span>
          </div>
          <p className="line-clamp-6 whitespace-pre-wrap text-muted-foreground">{src.text}</p>
        </li>
      ))}
    </ul>
  )
}

const PRI: Record<Priority, string> = { high: "text-destructive border-destructive/50", medium: "text-amber border-amber/50", low: "text-sky-400 border-sky-400/50" }

function Tasks() {
  const tasks = useStore((s) => s.tasks)
  const diff = useStore((s) => s.diff)
  const [title, setTitle] = useState("")
  const [filter, setFilter] = useState<"open" | "all" | "done">("open")
  const shown = tasks.filter((t) => filter === "all" || (filter === "open" ? !t.done : t.done))
  const today = new Date().toLocaleDateString("en-CA")
  const toggle = async (t: Task) => { await api.patchTask(t.id, { done: !t.done }); setState({ tasks: await api.tasks() }) }
  const add = async () => { if (!title.trim()) return; await api.createTask(title.trim(), "medium"); setTitle(""); setState({ tasks: await api.tasks() }) }
  return (
    <div>
      {diff && (diff.added.length + diff.changed.length + diff.removed.length > 0) && (
        <div className="mb-3 rounded-lg border border-primary/40 bg-primary/5 p-2 text-xs">
          <b>Last run changed SQLite:</b> {diff.added.length} added · {diff.changed.length} updated · {diff.removed.length} removed
          {diff.removed.map((t) => <div key={t.id} className="text-destructive line-through">#{t.id} {t.title}</div>)}
        </div>
      )}
      <div className="mb-2 flex gap-1">
        {(["open", "all", "done"] as const).map((f) => (
          <Button key={f} size="sm" variant={filter === f ? "secondary" : "ghost"} onClick={() => setFilter(f)} className="h-7 capitalize">{f}</Button>
        ))}
        <span className="ml-auto self-center text-[11px] text-muted-foreground">{tasks.filter((t) => !t.done).length} open / {tasks.length}</span>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); add() }} className="mb-2 flex gap-2">
        <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Quick add (manual fallback)" className="h-8 text-sm" />
        <Button size="sm" type="submit">Add</Button>
      </form>
      <ul className="space-y-1.5">
        {shown.map((t) => {
          const isNew = diff?.added.includes(t.id), changed = diff?.changed.includes(t.id)
          const over = !t.done && t.due && t.due < today
          return (
            <li key={t.id} className={cn("flex items-center gap-2 rounded-lg border bg-background/40 px-2.5 py-2 text-sm",
              isNew && "border-primary/70 bg-primary/5", changed && "border-violet/70")}>
              <button onClick={() => toggle(t)} aria-label={t.done ? "Reopen" : "Complete"} className="text-muted-foreground hover:text-primary">
                {t.done ? <CheckCircle2 className="size-4 text-primary" /> : <Circle className="size-4" />}
              </button>
              <span className={cn("min-w-0 flex-1 break-words", t.done && "text-muted-foreground line-through")}>{t.title}</span>
              {isNew && <Badge className="h-5 text-[10px]">new</Badge>}
              {changed && <Badge variant="outline" className="h-5 border-violet text-[10px] text-violet">updated</Badge>}
              {t.due && <span className={cn("text-[11px] text-muted-foreground", over && "font-semibold text-destructive")}>{over ? "overdue " : ""}{t.due}</span>}
              <Badge variant="outline" className={cn("h-5 text-[10px] uppercase", PRI[t.priority])}>{t.priority}</Badge>
            </li>
          )
        })}
        {!shown.length && <Empty icon={ListTodo} text={filter === "done" ? "Nothing completed yet." : "No open tasks."} />}
      </ul>
    </div>
  )
}

function Runs() {
  const runs = useStore((s) => s.runs)
  const sel = useStore((s) => s.selectedRun)
  if (!runs.length) return <Empty icon={History} text="Every agent run is persisted with its full trace." />
  return (
    <ul className="space-y-1.5">
      {runs.map((r) => (
        <li key={r.id}>
          <button onClick={() => setState({ selectedRun: r.id, tab: "timeline" })}
            className={cn("w-full rounded-lg border bg-background/40 p-2 text-left text-xs hover:border-primary/50", sel === r.id && "border-primary/60")}>
            <div className="flex items-center gap-2">
              <span className="font-mono text-muted-foreground">#{r.id}</span>
              <Badge variant="outline" className="h-5 text-[10px]">{r.skill ?? "-"}</Badge>
              {r.status !== "ok" && <Badge variant="outline" className={cn("h-5 text-[10px]", r.status === "error" ? "text-destructive" : "text-amber")}>{r.status}</Badge>}
              <span className="ml-auto font-mono text-muted-foreground">{(r.latency_ms / 1000).toFixed(1)}s</span>
            </div>
            <p className="mt-1 truncate">{r.message}</p>
          </button>
        </li>
      ))}
    </ul>
  )
}

function Perf() {
  const [loaded, setLoaded] = useState<LoadedModel[] | null>(null)
  const [bench, setBench] = useState<{ results: BenchRow[]; generated_at?: string; machine?: string }>({ results: [] })
  const runs = useStore((s) => s.runs)
  useEffect(() => {
    api.loaded().then(setLoaded).catch(() => setLoaded([]))
    api.benchResults().then(setBench).catch(() => {})
  }, [runs.length])
  const lat = runs.filter((r) => r.status !== "error").map((r) => r.latency_ms).sort((a, b) => a - b)
  const p50 = lat.length ? lat[Math.floor(lat.length / 2)] : null
  return (
    <div className="space-y-4 text-xs">
      <section>
        <h4 className="mb-1.5 font-semibold">Loaded in memory now (ollama ps)</h4>
        {loaded?.length ? loaded.map((m) => (
          <div key={m.name} className="flex items-center gap-2 rounded-lg border bg-background/40 p-2">
            <Cpu className="size-3.5 text-primary" /><b>{m.name}</b>
            <Badge variant="outline" className="h-5 text-[10px]">{m.quant}</Badge>
            <span className="ml-auto font-mono">{m.vram_mb} MB VRAM / {m.size_mb} MB</span>
          </div>
        )) : <p className="text-muted-foreground">No model loaded (it loads on the first request).</p>}
      </section>
      <section>
        <h4 className="mb-1.5 font-semibold">This session</h4>
        <p className="text-muted-foreground">{lat.length} runs · median {p50 ? (p50 / 1000).toFixed(2) + " s" : "-"} end-to-end</p>
      </section>
      <section>
        <h4 className="mb-1.5 font-semibold">Quantization benchmark {bench.generated_at && <span className="font-normal text-muted-foreground">· {bench.generated_at}</span>}</h4>
        {bench.results.length ? (
          <table className="w-full text-left">
            <thead className="text-muted-foreground"><tr><th className="py-1">model</th><th>scenario</th><th>pass</th><th>p50</th><th>tok/s</th></tr></thead>
            <tbody>{bench.results.map((b, i) => (
              <tr key={i} className="border-t"><td className="py-1 font-mono">{b.model}</td><td>{b.scenario}</td><td>{b.passed}/{b.runs}</td><td>{(b.p50_ms / 1000).toFixed(2)}s</td><td>{b.tok_per_s ?? "-"}</td></tr>
            ))}</tbody>
          </table>
        ) : <p className="text-muted-foreground">Run <code>python scripts/benchmark.py</code> to measure.</p>}
        {bench.machine && <p className="mt-1 text-[10px] text-muted-foreground">{bench.machine}</p>}
      </section>
    </div>
  )
}

function Empty({ icon: Icon, text }: { icon: FC<{ className?: string }>; text: string }) {
  return <div className="flex flex-col items-center gap-2 py-10 text-center text-xs text-muted-foreground"><Icon className="size-6 opacity-50" />{text}</div>
}

const TABS: { id: InspectorTab; label: string; icon: FC<{ className?: string }> }[] = [
  { id: "timeline", label: "Trace", icon: Activity },
  { id: "sources", label: "Sources", icon: BookOpen },
  { id: "tasks", label: "Tasks", icon: ListTodo },
  { id: "runs", label: "Runs", icon: History },
  { id: "perf", label: "Perf", icon: Cpu },
]

export function Inspector() {
  const tab = useStore((s) => s.tab)
  return (
    <Tabs value={tab} onValueChange={(v) => setState({ tab: v as InspectorTab })} className="flex h-full min-h-0 flex-col">
      <TabsList className="mx-3 mt-3 grid grid-cols-5">
        {TABS.map(({ id, label, icon: Icon }) => (
          <TabsTrigger key={id} value={id} className="gap-1 px-1 text-xs"><Icon className="size-3.5" /><span className="hidden xl:inline">{label}</span></TabsTrigger>
        ))}
      </TabsList>
      <div className="min-h-0 flex-1 overflow-y-auto p-3 scrollbar-thin">
        <TabsContent value="timeline"><Timeline /></TabsContent>
        <TabsContent value="sources"><Sources /></TabsContent>
        <TabsContent value="tasks"><Tasks /></TabsContent>
        <TabsContent value="runs"><Runs /></TabsContent>
        <TabsContent value="perf"><Perf /></TabsContent>
      </div>
    </Tabs>
  )
}
