import { useEffect, useState } from "react"
import { PanelRight } from "lucide-react"
import { Chat } from "@/components/Chat"
import { Inspector } from "@/components/Inspector"
import { DemoReset, Knowledge, SkillPicker, Status } from "@/components/Sidebar"
import { AnimatedShinyText } from "@/components/ui/animated-shiny-text"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/sonner"
import { refresh, refreshHealth, useStore } from "@/lib/store"
import { cn } from "@/lib/utils"

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 px-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">{title}</h3>
      {children}
    </section>
  )
}

export default function App() {
  const busy = useStore((s) => s.busy)
  const [inspector, setInspector] = useState(true)

  useEffect(() => {
    refresh().catch(() => {})
    refreshHealth()
    const t = setInterval(refreshHealth, 15000)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="relative flex h-dvh flex-col">
      <div className="grid-bg pointer-events-none fixed inset-0 opacity-40" />
      <header className="relative z-10 flex items-center gap-3 border-b bg-background/70 px-4 py-2.5 backdrop-blur">
        <div className={cn("orb size-5 rounded-full", busy && "busy")} />
        <span className="font-bold tracking-[0.25em]">CRYPTON</span>
        <AnimatedShinyText className="hidden text-xs sm:block">Agent Workspace · local-first</AnimatedShinyText>
        <Button size="sm" variant="ghost" className="ml-auto" onClick={() => setInspector(!inspector)} aria-label="Toggle inspector">
          <PanelRight />Inspector
        </Button>
      </header>

      <div className={cn("relative z-10 grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[270px_1fr]", inspector && "xl:grid-cols-[270px_1fr_380px] md:grid-cols-[1fr_340px] lg:grid-cols-[270px_1fr_360px]")}>
        <aside className="hidden min-h-0 space-y-5 overflow-y-auto border-r bg-background/40 p-3 scrollbar-thin lg:block">
          <Section title="System"><Status /></Section>
          <Section title="Skills"><SkillPicker /></Section>
          <Section title="Knowledge"><Knowledge /></Section>
          <Section title="Demo"><DemoReset /></Section>
        </aside>
        <main className="min-h-0">
          <Chat />
        </main>
        {inspector && (
          <aside className="hidden min-h-0 border-l bg-background/40 md:block">
            <Inspector />
          </aside>
        )}
      </div>
      {/* phones: inspector below the chat as a sheet */}
      {inspector && (
        <div className="relative z-10 h-[42dvh] border-t bg-background/90 md:hidden">
          <Inspector />
        </div>
      )}
      <Toaster position="bottom-center" theme="dark" />
    </div>
  )
}
