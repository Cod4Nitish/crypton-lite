import { useState, type FC } from "react"
import {
  AssistantRuntimeProvider, ComposerPrimitive, MessagePrimitive, ThreadPrimitive,
  useAuiState, useLocalRuntime,
  type ChatModelAdapter, type ToolCallMessagePartProps, type TextMessagePartProps,
} from "@assistant-ui/react"
import { ArrowUp, Check, ChevronRight, Loader2, Mic, ShieldAlert, Square, Wrench, X } from "lucide-react"
import { toast } from "sonner"
import { api, type Action, type Pending } from "@/lib/api"
import { getState, recordRun, setState } from "@/lib/store"
import { voice } from "@/lib/voice"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { BorderBeam } from "@/components/ui/border-beam"
import { cn } from "@/lib/utils"

// ---- adapter: assistant-ui <-> FastAPI/LangGraph -------------------------------------------

const textOf = (m: { content: readonly { type: string; text?: string }[] }) =>
  m.content.filter((p) => p.type === "text").map((p) => p.text).join("\n")

const adapter: ChatModelAdapter = {
  async run({ messages, abortSignal }) {
    const last = messages[messages.length - 1]
    const message = textOf(last)
    // send prior turns; assistant turns use the server's `memory` (reply + touched task ids)
    const history = messages.slice(0, -1).slice(-6).map((m) => ({
      role: m.role,
      content: (m.metadata?.custom?.memory as string | undefined) ?? textOf(m),
    }))
    const before = getState().tasks
    setState({ busy: true })
    try {
      const res = await api.chat(message, history, getState().skill, abortSignal)
      recordRun(res, message, before)
      return {
        content: [
          ...res.actions.map((a, i) => ({
            type: "tool-call" as const,
            toolCallId: `${res.run_id}-${i}`,
            toolName: a.tool,
            args: a.args as Record<string, never>,
            argsText: JSON.stringify(a.args),
            result: a.result,
            isError: !a.result.ok,
          })),
          { type: "text" as const, text: res.reply },
        ],
        metadata: { custom: { runId: res.run_id, memory: res.memory, skill: res.skill, latency: res.latency_ms, timing: res.timing } },
      }
    } catch (e) {
      if ((e as Error).name === "AbortError") throw e
      const msg = (e as Error).message || "request failed"
      toast.error(`Agent run failed: ${msg}`)
      return {
        content: [{ type: "text" as const, text: `This command did not run, so nothing was changed. ${msg}. You can edit the text and send it again.` }],
        status: { type: "incomplete" as const, reason: "error" as const, error: msg },
      }
    } finally {
      setState({ busy: false })
    }
  },
}

// ---- message parts -------------------------------------------------------------------------

/** Assistant text with [n] citations rendered as chips that open the source. */
const CitedText: FC<TextMessagePartProps> = ({ text }) => {
  const runId = useAuiState((s) => s.message.metadata?.custom?.runId as number | undefined)
  const parts = text.split(/(\[\d+\])/g)
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((p, i) => {
        const m = p.match(/^\[(\d+)\]$/)
        if (!m) return <span key={i}>{p}</span>
        const n = Number(m[1])
        return (
          <button key={i} onClick={() => setState({ tab: "sources", highlight: n, selectedRun: runId ?? null })}
            className="mx-0.5 inline-flex h-5 min-w-5 items-center justify-center rounded-md bg-primary/15 px-1 align-text-top text-[11px] font-semibold text-primary hover:bg-primary/30"
            title="Show source">{n}</button>
        )
      })}
    </p>
  )
}

function summarize(tool: string, r: Action["result"]): string {
  if (!r.ok) return String(r.error ?? "failed")
  if (r.needs_confirmation) return "awaiting your confirmation"
  if (r.duplicate) return "already exists, not duplicated"
  const t = r.task as { id: number; title: string } | undefined
  if (t) return `#${t.id} “${t.title}”`
  if (Array.isArray(r.tasks)) return `${r.tasks.length} tasks`
  if (Array.isArray(r.chunks)) return `${r.chunks.length} passages${r.insufficient ? " · insufficient evidence" : ""}`
  if (r.note) return "note saved"
  return tool
}

const ConfirmBar: FC<{ pending: Pending }> = ({ pending }) => {
  const [state, setLocal] = useState<"pending" | "busy" | "confirmed" | "cancelled" | "failed">("pending")
  const decide = async (d: "confirm" | "cancel") => {
    setLocal("busy")
    try {
      const r = await api.decide(pending.id, d)
      setState({ tasks: r.tasks })
      setLocal(r.pending.status as typeof state)
      toast(d === "confirm" ? `Confirmed: ${pending.summary}` : "Cancelled. Nothing was changed.")
    } catch (e) {
      setLocal("failed")
      toast.error((e as Error).message)
    }
  }
  if (state !== "pending" && state !== "busy")
    return <div className="mt-2 text-xs text-muted-foreground">Decision: <b className="text-foreground">{state}</b></div>
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-amber/40 bg-amber/10 p-2 text-xs">
      <ShieldAlert className="size-4 text-amber" />
      <span className="flex-1">{pending.summary}?</span>
      <Button size="sm" variant="destructive" disabled={state === "busy"} onClick={() => decide("confirm")}><Check />Confirm</Button>
      <Button size="sm" variant="outline" disabled={state === "busy"} onClick={() => decide("cancel")}><X />Cancel</Button>
    </div>
  )
}

/** Tool inspector card: real tool name, validated args and the raw result. */
const ToolCard: FC<ToolCallMessagePartProps> = ({ toolName, args, result }) => {
  const [open, setOpen] = useState(false)
  const r = (result ?? { ok: false }) as Action["result"]
  const tone = !r.ok ? "border-destructive/50 text-destructive" : r.needs_confirmation ? "border-amber/50 text-amber" : "border-primary/40 text-primary"
  return (
    <div className="my-1.5 rounded-lg border bg-background/40 text-xs">
      <button onClick={() => setOpen(!open)} className="flex w-full items-center gap-2 px-2.5 py-1.5 text-left">
        <ChevronRight className={cn("size-3.5 transition-transform", open && "rotate-90")} />
        <Wrench className="size-3.5 text-muted-foreground" />
        <code className="font-semibold">{toolName}</code>
        <span className="truncate text-muted-foreground">{summarize(toolName, r)}</span>
        <Badge variant="outline" className={cn("ml-auto", tone)}>{!r.ok ? "error" : r.needs_confirmation ? "confirm" : "ok"}</Badge>
      </button>
      {open && (
        <div className="grid gap-1 border-t px-2.5 py-2 font-mono text-[11px]">
          <div><span className="text-muted-foreground">args </span>{JSON.stringify(args)}</div>
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-muted-foreground scrollbar-thin">{JSON.stringify(result, null, 1)}</pre>
        </div>
      )}
      {r.needs_confirmation && r.pending ? <div className="px-2.5 pb-2"><ConfirmBar pending={r.pending as Pending} /></div> : null}
    </div>
  )
}

const UserMessage: FC = () => (
  <MessagePrimitive.Root className="flex justify-end py-2">
    <div className="max-w-[85%] rounded-2xl rounded-br-md bg-secondary px-4 py-2.5">
      <MessagePrimitive.Parts />
    </div>
  </MessagePrimitive.Root>
)

const AssistantMeta: FC = () => {
  const meta = useAuiState((s) => s.message.metadata?.custom as { skill?: string; latency?: number; runId?: number; timing?: { llm_ms: number; tool_ms: number } } | undefined)
  if (!meta?.runId) return null
  return (
    <button onClick={() => setState({ selectedRun: meta.runId, tab: "timeline" })}
      className="mt-1.5 flex items-center gap-2 text-[11px] text-muted-foreground hover:text-foreground">
      <Badge variant="secondary" className="h-5 text-[10px]">{meta.skill}</Badge>
      run #{meta.runId} · {((meta.latency ?? 0) / 1000).toFixed(1)}s total{meta.timing ? ` (model ${(meta.timing.llm_ms / 1000).toFixed(1)}s · tools ${meta.timing.tool_ms} ms)` : ""} · view trace →
    </button>
  )
}

const AssistantMessage: FC = () => (
  <MessagePrimitive.Root className="flex gap-3 py-2">
    <div className="orb mt-1 size-6 shrink-0 rounded-full" />
    <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border bg-card/70 px-4 py-2.5">
      <MessagePrimitive.Parts components={{ Text: CitedText, tools: { Fallback: ToolCard } }} />
      <MessagePrimitive.Error>
        <div className="text-sm text-destructive">The local model did not respond. Is Ollama running?</div>
      </MessagePrimitive.Error>
      <AssistantMeta />
    </div>
  </MessagePrimitive.Root>
)

const SUGGESTIONS = [
  "Summarize the important activities in the event agenda",
  "Create preparation tasks based on the event agenda document",
  "Plan my day",
  "Remember this note: demo laptop charger is in the blue bag",
]

const Welcome: FC = () => (
  <ThreadPrimitive.Empty>
    <div className="mx-auto flex max-w-xl flex-col items-center py-10 text-center">
      <div className="orb mb-5 size-16 rounded-full" />
      <h1 className="text-2xl font-semibold tracking-tight">How can I help?</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        Type what you need, or hold your <b className="text-foreground">Wispr Flow</b> key and speak. Pick an example below to start. Everything stays on this computer.
      </p>
      <div className="mt-6 grid w-full gap-2 sm:grid-cols-2">
        {SUGGESTIONS.map((s) => (
          <ThreadPrimitive.Suggestion key={s} prompt={s} send asChild>
            <button className="rounded-xl border bg-card/60 px-3 py-2.5 text-left text-sm text-muted-foreground transition hover:border-primary/50 hover:text-foreground">{s}</button>
          </ThreadPrimitive.Suggestion>
        ))}
      </div>
    </div>
  </ThreadPrimitive.Empty>
)

const Composer: FC = () => (
  <ComposerPrimitive.Root className="relative mx-auto w-full max-w-3xl overflow-hidden rounded-2xl border bg-card/80 p-2 shadow-lg backdrop-blur">
    <ComposerPrimitive.Input autoFocus placeholder="Type or speak what you need…" rows={1}
      className="max-h-40 min-h-11 w-full resize-none bg-transparent px-2 py-2 text-[15px] outline-none placeholder:text-muted-foreground" />
    <div className="flex items-center gap-2">
      <ComposerPrimitive.If dictation={false}>
        <ComposerPrimitive.Dictate asChild>
          <Button size="sm" variant="ghost" title="Browser dictation (fallback when Wispr Flow is not available)"><Mic />Mic</Button>
        </ComposerPrimitive.Dictate>
      </ComposerPrimitive.If>
      <ComposerPrimitive.If dictation>
        <ComposerPrimitive.StopDictation asChild>
          <Button size="sm" variant="destructive"><Square />Stop</Button>
        </ComposerPrimitive.StopDictation>
        <span className="flex items-center gap-1.5 text-xs text-primary"><span className="size-2 animate-pulse rounded-full bg-primary" />Listening… words appear above, edit before sending</span>
      </ComposerPrimitive.If>
      <span className="hidden text-[11px] text-muted-foreground sm:inline">Enter to send · Shift+Enter new line</span>
      <ThreadPrimitive.If running={false}>
        <ComposerPrimitive.Send asChild>
          <Button size="icon" className="ml-auto rounded-xl" aria-label="Send"><ArrowUp /></Button>
        </ComposerPrimitive.Send>
      </ThreadPrimitive.If>
      <ThreadPrimitive.If running>
        <Button size="icon" className="ml-auto rounded-xl" disabled aria-label="Running"><Loader2 className="animate-spin" /></Button>
      </ThreadPrimitive.If>
    </div>
    <ThreadPrimitive.If running><BorderBeam size={120} duration={4} colorFrom="var(--primary)" colorTo="var(--violet)" /></ThreadPrimitive.If>
  </ComposerPrimitive.Root>
)

export function Chat() {
  const runtime = useLocalRuntime(adapter, { adapters: { dictation: voice } })
  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <ThreadPrimitive.Root className="flex h-full min-h-0 flex-col">
        <ThreadPrimitive.Viewport className="min-h-0 flex-1 overflow-y-auto px-4 scrollbar-thin">
          <div className="mx-auto max-w-3xl pb-6 pt-2">
            <Welcome />
            <ThreadPrimitive.Messages components={{ UserMessage, AssistantMessage }} />
            <ThreadPrimitive.If running>
              <div className="flex items-center gap-3 py-2 text-sm text-muted-foreground">
                <div className="orb busy size-6 rounded-full" />Running: route skill → local model → tools (see Inspector for live timings)…
              </div>
            </ThreadPrimitive.If>
          </div>
        </ThreadPrimitive.Viewport>
        <div className="px-4 pb-4"><Composer /></div>
      </ThreadPrimitive.Root>
    </AssistantRuntimeProvider>
  )
}
