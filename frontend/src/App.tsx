import { FolderOpen, Menu, PanelRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CaseFile } from "@/components/CaseFile";
import { Composer, type ComposerHandle } from "@/components/Composer";
import { Dossier, type DossierTab } from "@/components/Dossier";
import { EmptyState } from "@/components/EmptyState";
import { Thread } from "@/components/Thread";
import { useConversations } from "@/hooks/useConversations";
import { getHealth, getTaxonomy } from "@/lib/api";
import type { AssistantMessage, Health, Taxonomy } from "@/lib/types";
import { cn, storage } from "@/lib/utils";

const SCOPE_KEY = "inccorpai.scope.v1";

export default function App() {
  const [taxonomy, setTaxonomy] = useState<Taxonomy | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const saved = storage.get(SCOPE_KEY, { jurisdiction: "IN", entity_type: "Pvt Ltd", phase: null as string | null });
  const [jurisdiction, setJurisdiction] = useState(saved.jurisdiction);
  const [entityType, setEntityType] = useState(saved.entity_type);
  const [phase, setPhase] = useState<string | null>(saved.phase);

  const convs = useConversations();
  const composer = useRef<ComposerHandle>(null);

  const [tab, setTab] = useState<DossierTab>("checklist");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [highlight, setHighlight] = useState<number | null>(null);
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  useEffect(() => {
    getTaxonomy().then(setTaxonomy).catch((e) => setLoadError(String(e.message ?? e)));
    getHealth().then(setHealth).catch(() => {});
  }, []);

  useEffect(() => storage.set(SCOPE_KEY, { jurisdiction, entity_type: entityType, phase }), [jurisdiction, entityType, phase]);

  const current = taxonomy?.jurisdictions.find((j) => j.code === jurisdiction);
  const entityLabel = current?.entity_types.find((e) => e.value === entityType)?.label ?? entityType;

  const onJurisdiction = (code: string) => {
    setJurisdiction(code);
    const j = taxonomy?.jurisdictions.find((x) => x.code === code);
    if (j && !j.entity_types.some((e) => e.value === entityType)) setEntityType(j.entity_types[0].value);
  };

  const messages = convs.active?.messages ?? [];
  const assistants = messages.filter((m): m is AssistantMessage => m.role === "assistant");
  const selected = assistants.find((m) => m.id === selectedId) ?? [...assistants].reverse().find((m) => m.sources.length) ?? null;
  const checklistOwner = useMemo(
    () => [...assistants].reverse().find((m) => m.widgets.some((w) => w.template === "checklist")) ?? null,
    [assistants],
  );

  // When a fresh checklist arrives, bring the dossier to it.
  const lastChecklistId = useRef<string | null>(null);
  useEffect(() => {
    if (checklistOwner && checklistOwner.id !== lastChecklistId.current) {
      if (lastChecklistId.current !== null || checklistOwner.stage !== "done") setTab("checklist");
      lastChecklistId.current = checklistOwner.id;
    }
  }, [checklistOwner]);

  const cite = (m: AssistantMessage, i: number) => {
    setSelectedId(m.id);
    setTab("sources");
    setHighlight(i);
    setRightOpen(true);
  };

  const send = (q: string) => {
    setSelectedId(null);
    setHighlight(null);
    convs.send(q, { jurisdiction, entity_type: entityType, compliance_phase: phase });
  };

  const openConversation = (id: string) => {
    const c = convs.conversations.find((x) => x.id === id);
    if (c) {
      setJurisdiction(c.jurisdiction);
      setEntityType(c.entity_type);
    }
    convs.setActiveId(id);
    setSelectedId(null);
    setLeftOpen(false);
  };

  const caseFile = (
    <CaseFile
      jurisdictions={taxonomy?.jurisdictions ?? []}
      phases={taxonomy?.compliance_phases ?? []}
      jurisdiction={jurisdiction}
      entityType={entityType}
      phase={phase}
      onJurisdiction={onJurisdiction}
      onEntityType={setEntityType}
      onPhase={setPhase}
      conversations={convs.conversations}
      activeId={convs.activeId}
      onOpen={openConversation}
      onNew={() => {
        convs.startNew();
        setLeftOpen(false);
      }}
      onDelete={convs.remove}
      health={health}
    />
  );

  const dossier = (onClose?: () => void) => (
    <Dossier
      message={selected}
      checklistOwner={checklistOwner}
      tab={tab}
      onTab={setTab}
      highlight={selected?.id === selectedId ? highlight : null}
      onCite={(i) => checklistOwner && cite(checklistOwner, i)}
      onClose={onClose}
    />
  );

  return (
    <div className="flex h-dvh overflow-hidden bg-paper">
      {/* left rail */}
      <div className="hidden w-[17.5rem] shrink-0 border-r border-rule lg:block">{caseFile}</div>

      {/* conversation */}
      <main className="flex min-w-0 flex-1 flex-col bg-sheet">
        <div className="flex items-center justify-between border-b border-rule px-3 py-2 lg:hidden">
          <button onClick={() => setLeftOpen(true)} className="flex items-center gap-2 rounded-field p-2 text-sm font-medium text-ink" aria-label="Open scope and history">
            <Menu size={18} /> {jurisdiction}, {entityType}
          </button>
          <button onClick={() => setRightOpen(true)} className="flex items-center gap-1.5 rounded-field p-2 text-sm font-medium text-ink xl:hidden" aria-label="Open dossier">
            <FolderOpen size={17} /> Dossier
          </button>
        </div>
        <div className="hidden justify-end px-3 pt-2 lg:flex xl:hidden">
          <button onClick={() => setRightOpen(true)} className="flex items-center gap-1.5 rounded-field p-2 text-sm font-medium text-ink-soft hover:text-ink">
            <PanelRight size={16} /> Dossier
          </button>
        </div>

        <div className="scroll-quiet flex flex-1 flex-col overflow-y-auto">
          {loadError ? (
            <div className="mx-auto my-auto max-w-md px-6 text-center">
              <p className="text-lg font-semibold text-ink">The IncCorpAI API isn't reachable</p>
              <p className="mt-2 text-sm leading-relaxed text-ink-soft">
                Start the backend with <code className="rounded bg-paper px-1">uvicorn main:app --port 8000</code> in{" "}
                <code className="rounded bg-paper px-1">backend/</code>, then reload this page. ({loadError})
              </p>
            </div>
          ) : messages.length === 0 ? (
            <EmptyState jurisdiction={current} entityLabel={entityLabel} onPick={(q) => send(q)} />
          ) : (
            <Thread
              messages={messages}
              selectedId={selected?.id ?? null}
              onSelect={(m) => {
                setSelectedId(m.id);
                setTab("sources");
                setHighlight(null);
              }}
              onCite={cite}
              onOpenChecklist={() => {
                setTab("checklist");
                setRightOpen(true);
              }}
            />
          )}
        </div>
        <Composer ref={composer} onSend={send} onStop={convs.stop} streaming={convs.streaming} scopeLabel={`${current?.name ?? jurisdiction}, ${entityLabel}`} />
      </main>

      {/* dossier */}
      <div className="hidden w-[24rem] shrink-0 border-l border-rule xl:block">{dossier()}</div>

      {/* mobile / tablet drawers */}
      <Drawer side="left" open={leftOpen} onClose={() => setLeftOpen(false)}>
        {caseFile}
      </Drawer>
      <Drawer side="right" open={rightOpen} onClose={() => setRightOpen(false)} className="xl:hidden">
        {dossier(() => setRightOpen(false))}
      </Drawer>
    </div>
  );
}

function Drawer({ side, open, onClose, children, className }: { side: "left" | "right"; open: boolean; onClose: () => void; children: React.ReactNode; className?: string }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  return (
    <div className={cn("fixed inset-0 z-40", open ? "pointer-events-auto" : "pointer-events-none", side === "left" && "lg:hidden", className)} aria-hidden={!open}>
      <div className={cn("absolute inset-0 bg-ink/30 transition-opacity", open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "absolute top-0 h-full w-[min(24rem,88vw)] shadow-xl transition-transform duration-200",
          side === "left" ? "left-0" : "right-0",
          open ? "translate-x-0" : side === "left" ? "-translate-x-full" : "translate-x-full",
        )}
      >
        {children}
      </div>
    </div>
  );
}
