import { X } from "lucide-react";
import { useEffect, useRef } from "react";
import type { AssistantMessage } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ChecklistWidget } from "./ChecklistWidget";
import { SourceCard } from "./SourceCard";

export type DossierTab = "checklist" | "sources";

interface Props {
  message: AssistantMessage | null;     // the answer whose sources are shown
  checklistOwner: AssistantMessage | null; // most recent answer with a checklist
  tab: DossierTab;
  onTab: (t: DossierTab) => void;
  highlight: number | null;
  onCite: (i: number) => void;
  onClose?: () => void;
}

/** Right panel: the working checklist and the clauses behind the selected answer. */
export function Dossier({ message, checklistOwner, tab, onTab, highlight, onCite, onClose }: Props) {
  const refs = useRef<Record<number, HTMLElement | null>>({});
  const sources = message?.sources ?? [];
  const checklist = checklistOwner?.widgets.find((w) => w.template === "checklist");

  useEffect(() => {
    if (tab === "sources" && highlight) {
      refs.current[highlight]?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [highlight, tab, message?.id]);

  const tabs: { id: DossierTab; label: string; count?: number }[] = [
    { id: "checklist", label: "Checklist", count: checklist?.payload.items.length },
    { id: "sources", label: "Sources", count: sources.length || undefined },
  ];

  return (
    <aside className="flex h-full flex-col bg-paper">
      <div className="flex items-center gap-1 border-b border-rule px-4 pt-4" role="tablist">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => onTab(t.id)}
            className={cn(
              "-mb-px flex items-center gap-1.5 border-b-2 px-2.5 pb-2.5 text-sm font-semibold transition-colors",
              tab === t.id ? "border-registry text-ink" : "border-transparent text-ink-soft hover:text-ink",
            )}
          >
            {t.label}
            {t.count ? <span className="rounded-full bg-sheet px-1.5 text-xs tabular-nums text-ink-soft ring-1 ring-rule">{t.count}</span> : null}
          </button>
        ))}
        {onClose && (
          <button onClick={onClose} className="ml-auto mb-2 rounded p-1.5 text-ink-soft hover:bg-sheet" aria-label="Close panel">
            <X size={16} />
          </button>
        )}
      </div>

      <div className="scroll-quiet flex-1 overflow-y-auto p-4" role="tabpanel">
        {tab === "checklist" &&
          (checklist && checklistOwner ? (
            <ChecklistWidget compact checklistKey={checklistOwner.id} data={checklist.payload} onCite={onCite} />
          ) : (
            <Empty
              title="No checklist yet"
              body="Ask for a process, such as “steps to incorporate a Pvt Ltd company”, and the filing steps will appear here for you to tick off."
            />
          ))}

        {tab === "sources" &&
          (sources.length ? (
            <div className="space-y-2.5">
              <p className="text-sm text-ink-soft">
                Clauses used for this answer, filtered to{" "}
                <span className="font-semibold text-ink">
                  {message?.filters?.jurisdiction}, {message?.filters?.entity_type}
                </span>
                .
              </p>
              {sources.map((s) => (
                <SourceCard
                  key={s.chunk_id}
                  ref={(el) => (refs.current[s.index] = el)}
                  source={s}
                  highlighted={highlight === s.index}
                />
              ))}
            </div>
          ) : (
            <Empty title="No sources to show" body="Sources appear here as soon as an answer starts. Select a citation number in any answer to open its clause." />
          ))}
      </div>
    </aside>
  );
}

function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-panel border border-dashed border-rule p-5">
      <p className="text-sm font-semibold text-ink">{title}</p>
      <p className="mt-1 text-sm leading-relaxed text-ink-soft">{body}</p>
    </div>
  );
}
