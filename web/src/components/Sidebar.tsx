import { useRef, useState, type FC } from "react"
import { Check, FileText, Loader2, RotateCcw, Sparkles, Trash2, Upload } from "lucide-react"
import { toast } from "sonner"
import { api } from "@/lib/api"
import { refresh, setState, useStore } from "@/lib/store"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

const Dot: FC<{ ok: boolean | undefined; label: string; detail?: string }> = ({ ok, label, detail }) => (
  <div className="flex items-center gap-2 text-xs">
    <span className={cn("size-2 rounded-full", ok ? "bg-primary shadow-[0_0_8px_var(--primary)]" : "bg-destructive")} />
    <span>{label}</span>
    {detail && <span className="ml-auto truncate font-mono text-[10px] text-muted-foreground">{detail}</span>}
  </div>
)

export function Status() {
  const h = useStore((s) => s.health)
  return (
    <div className="space-y-1.5 rounded-xl border bg-card/60 p-3">
      <Dot ok={!!h} label="API" detail="FastAPI" />
      <Dot ok={h?.ollama === "ok"} label="Ollama" detail="local" />
      <Dot ok={h?.model_installed} label="Agent model" detail={h?.model} />
      <Dot ok={h?.embed_model_installed} label="Embeddings" detail="nomic-embed-text" />
    </div>
  )
}

export function SkillPicker() {
  const skills = useStore((s) => s.skills)
  const current = useStore((s) => s.skill)
  const opts = [{ name: null as string | null, description: "Route each command to the best skill automatically.", tools: [] as string[] }, ...skills]
  return (
    <div className="space-y-1">
      {opts.map((s) => (
        <button key={s.name ?? "auto"} onClick={() => setState({ skill: s.name })}
          className={cn("w-full rounded-lg border border-transparent px-2.5 py-2 text-left transition hover:bg-accent",
            current === s.name && "border-primary/40 bg-primary/10")}>
          <div className="flex items-center gap-2 text-sm font-medium">
            {s.name === null ? <Sparkles className="size-3.5 text-primary" /> : <span className="size-1.5 rounded-full bg-violet" />}
            {s.name ?? "Auto"}
            {current === s.name && <Check className="ml-auto size-3.5 text-primary" />}
          </div>
          <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{s.description}</p>
          {s.tools.length > 0 && <p className="mt-1 font-mono text-[10px] text-muted-foreground/80">{s.tools.join(" · ")}</p>}
        </button>
      ))}
    </div>
  )
}

export function Knowledge() {
  const docs = useStore((s) => s.docs)
  const [busy, setBusy] = useState(false)
  const [drag, setDrag] = useState(false)
  const input = useRef<HTMLInputElement>(null)
  const upload = async (files: FileList | null) => {
    if (!files?.length) return
    setBusy(true)
    for (const f of Array.from(files)) {
      try {
        const r = await api.upload(f)
        toast(r.cached ? `${f.name}: unchanged, reused cached embeddings` : `${f.name}: ${r.document.chunks} chunks indexed in ${(r.ms / 1000).toFixed(1)}s`)
      } catch (e) {
        toast.error(`${f.name}: ${(e as Error).message}`)
      }
    }
    setState({ docs: await api.docs() })
    setBusy(false)
  }
  const remove = async (id: number) => { await api.removeDoc(id); setState({ docs: await api.docs() }) }
  const files = docs.filter((d) => !d.name.startsWith("note-"))
  const notes = docs.length - files.length
  return (
    <div className="space-y-2">
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true) }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); upload(e.dataTransfer.files) }}
        className={cn("rounded-xl border border-dashed p-3 text-center text-xs text-muted-foreground transition", drag && "border-primary bg-primary/10")}>
        <input ref={input} type="file" accept=".pdf,.txt,.md,.markdown" multiple hidden onChange={(e) => upload(e.target.files)} />
        <Button size="sm" variant="secondary" disabled={busy} onClick={() => input.current?.click()}>
          {busy ? <Loader2 className="animate-spin" /> : <Upload />}{busy ? "Embedding…" : "Upload"}
        </Button>
        <p className="mt-1.5">PDF, TXT, Markdown · drop here</p>
      </div>
      <ul className="space-y-1">
        {files.map((d) => (
          <li key={d.id} className="group flex items-center gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-accent">
            <FileText className="size-3.5 shrink-0 text-primary" />
            <span className="min-w-0 flex-1 truncate" title={d.name}>{d.name}</span>
            <Badge variant="outline" className="h-5 text-[10px]">{d.pages ? `${d.pages}p · ` : ""}{d.chunks}c</Badge>
            <button onClick={() => remove(d.id)} className="opacity-0 transition group-hover:opacity-100" aria-label={`Remove ${d.name}`}>
              <Trash2 className="size-3.5 text-muted-foreground hover:text-destructive" />
            </button>
          </li>
        ))}
      </ul>
      {notes > 0 && <p className="px-2 text-[11px] text-muted-foreground">+ {notes} saved note{notes > 1 ? "s" : ""} indexed</p>}
    </div>
  )
}

/** Competition helper: wipes tasks, runs, notes and documents, then loads clearly labelled SAMPLE data. */
export function DemoReset() {
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const click = async () => {
    if (!armed) { setArmed(true); setTimeout(() => setArmed(false), 4000); return }
    setArmed(false); setBusy(true)
    try {
      const r = await api.demoReset()
      await refresh()
      setState({ selectedRun: null, diff: null })
      toast.success(`Demo reset: indexed ${r.document.name} (${r.document.chunks} chunks), ${r.tasks.length} sample tasks`)
    } catch (e) {
      toast.error(`Demo reset failed, your data was not changed: ${(e as Error).message}`)
    } finally { setBusy(false) }
  }
  return (
    <div className="space-y-1">
      <Button size="sm" variant={armed ? "destructive" : "outline"} className="w-full" disabled={busy} onClick={click}>
        {busy ? <Loader2 className="animate-spin" /> : <RotateCcw />}{busy ? "Preparing…" : armed ? "Click again: erase all data" : "Prepare demo (sample data)"}
      </Button>
      <p className="px-1 text-[10px] text-muted-foreground">Erases everything, then loads a labelled sample agenda and 2 [Sample] tasks.</p>
    </div>
  )
}
