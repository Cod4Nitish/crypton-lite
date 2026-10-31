import { Check } from "lucide-react"
import { toast } from "sonner"
import { api } from "@/lib/api"
import { refresh, useStore } from "@/lib/store"
import { cn } from "@/lib/utils"

/** Plain to-do list for the simple view: tick a task to finish it. */
export function TaskPanel() {
  const tasks = useStore((s) => s.tasks)
  const open = tasks.filter((t) => !t.done)
  const done = tasks.filter((t) => t.done)
  const toggle = async (id: number, value: boolean) => {
    try {
      await api.patchTask(id, { done: value })
      await refresh()
    } catch (e) {
      toast.error(`Could not update the task: ${(e as Error).message}`)
    }
  }
  const row = (t: (typeof tasks)[number]) => (
    <li key={t.id}>
      <button onClick={() => toggle(t.id, !t.done)} className="flex w-full items-start gap-3 rounded-xl px-2 py-2 text-left hover:bg-accent">
        <span className={cn("mt-0.5 grid size-5 shrink-0 place-items-center rounded-full border", t.done && "border-primary bg-primary text-primary-foreground")}>
          {t.done && <Check className="size-3" />}
        </span>
        <span className="min-w-0">
          <span className={cn("block text-[15px]", t.done && "text-muted-foreground line-through")}>{t.title}</span>
          {t.due && !t.done && <span className="text-xs text-muted-foreground">Due {t.due}</span>}
        </span>
      </button>
    </li>
  )
  return (
    <div className="h-full overflow-y-auto p-4">
      <h2 className="mb-2 text-lg font-semibold">My tasks</h2>
      {tasks.length === 0 && <p className="text-sm text-muted-foreground">No tasks yet. Ask CRYPTON to add one.</p>}
      <ul className="space-y-0.5">{open.map(row)}</ul>
      {done.length > 0 && (
        <>
          <h3 className="mb-1 mt-5 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Done</h3>
          <ul className="space-y-0.5">{done.map(row)}</ul>
        </>
      )}
    </div>
  )
}
