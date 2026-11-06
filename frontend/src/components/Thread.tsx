import { AlertTriangle, ClipboardCheck, Info, SearchX } from "lucide-react";
import { useChecklist } from "@/hooks/useChecklist";
import { useEffect, useRef } from "react";
import type { AssistantMessage, Message } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Answer } from "./Answer";
import { ChecklistWidget } from "./ChecklistWidget";
import { PipelineStatus } from "./PipelineStatus";

interface Props {
  messages: Message[];
  selectedId: string | null;
  onSelect: (m: AssistantMessage) => void;
  onCite: (m: AssistantMessage, index: number) => void;
  onOpenChecklist: (m: AssistantMessage) => void;
}

export function Thread({ messages, selectedId, onSelect, onCite, onOpenChecklist }: Props) {
  const end = useRef<HTMLDivElement>(null);
  const last = messages[messages.length - 1];
  const lastLen = last?.content.length ?? 0;

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages.length, lastLen]);

  return (
    <div className="mx-auto w-full max-w-[46rem] px-5 py-8 sm:px-8">
      {messages.map((m) =>
        m.role === "user" ? (
          <div key={m.id} className="mb-6 mt-10 first:mt-0">
            <p className="text-xl font-semibold leading-snug tracking-tight text-ink">{m.content}</p>
          </div>
        ) : (
          <AssistantBlock
            key={m.id}
            m={m}
            selected={selectedId === m.id}
            onSelect={() => onSelect(m)}
            onCite={(i) => onCite(m, i)}
            onOpenChecklist={() => onOpenChecklist(m)}
          />
        ),
      )}
      <div ref={end} />
    </div>
  );
}

function AssistantBlock({ m, selected, onSelect, onCite, onOpenChecklist }: { m: AssistantMessage; selected: boolean; onSelect: () => void; onCite: (i: number) => void; onOpenChecklist: () => void }) {
  const pending = m.stage === "retrieving" || m.stage === "reranking" || (m.stage === "generating" && !m.content);
  const streaming = m.stage === "generating";
  const rejected = m.done?.rejected;
  const checklist = m.widgets.find((w) => w.template === "checklist");

  return (
    <div
      className={cn("relative border-l-2 pl-5 transition-colors", selected && m.sources.length ? "border-stamp/50" : "border-rule")}
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("button,a,label,input")) return;
        if (m.sources.length) onSelect();
      }}
    >
      {m.filters?.note && (
        <p className="mb-3 flex items-start gap-2 rounded-field bg-notice-wash px-3 py-2 font-sans text-sm text-notice">
          <Info size={15} className="mt-0.5 shrink-0" />
          {m.filters.note}
        </p>
      )}

      {pending && <PipelineStatus stage={m.stage as "retrieving"} />}

      {rejected ? (
        <div className="flex gap-3 rounded-panel border border-rule bg-sheet p-4">
          <SearchX size={18} className="mt-0.5 shrink-0 text-ink-soft" />
          <div>
            <p className="text-sm font-semibold text-ink">Not covered by the indexed regulations</p>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">{m.content}</p>
          </div>
        </div>
      ) : (
        m.content && <Answer text={m.content} sources={m.sources} onCite={onCite} streaming={streaming} />
      )}

      {checklist && (
        <>
          <div className="mt-5 xl:hidden">
            <ChecklistWidget checklistKey={m.id} data={checklist.payload} onCite={onCite} />
          </div>
          <ChecklistSummary className="mt-5 hidden xl:flex" checklistKey={m.id} title={checklist.payload.header_title} ids={checklist.payload.items.map((i) => i.id)} onOpen={onOpenChecklist} />
        </>
      )}

      {m.error && (
        <p className="mt-3 flex items-start gap-2 rounded-field border border-notice/30 bg-notice-wash px-3 py-2 text-sm text-notice">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          {m.error}
        </p>
      )}

      {m.stage === "done" && m.done && !rejected && (
        <p className="mt-3 font-sans text-xs text-ink-faint">
          {m.sources.length} sources, {(m.done.latency_ms / 1000).toFixed(1)} s
          {m.done.model ? `, ${m.done.model}` : ""}
        </p>
      )}
    </div>
  );
}

function ChecklistSummary({ checklistKey, title, ids, onOpen, className }: { checklistKey: string; title: string; ids: string[]; onOpen: () => void; className?: string }) {
  const { filed } = useChecklist(checklistKey);
  const done = ids.filter((id) => filed[id]).length;
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn("w-full items-center gap-3 rounded-panel border border-rule bg-sheet p-3.5 text-left font-sans hover:border-stamp/40", className)}
    >
      <ClipboardCheck size={18} className="shrink-0 text-stamp" />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-ink">{title}</span>
        <span className="block text-xs text-ink-soft">
          {done} of {ids.length} steps filed. Tick them off in the dossier.
        </span>
      </span>
      <span className="h-1.5 w-20 shrink-0 overflow-hidden rounded-full bg-paper">
        <span className="block h-full bg-stamp" style={{ width: `${ids.length ? (done / ids.length) * 100 : 0}%` }} />
      </span>
    </button>
  );
}
