import { Check, RotateCcw } from "lucide-react";
import { useChecklist } from "@/hooks/useChecklist";
import type { ChecklistPayload } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Stamp } from "./Stamp";

interface Props {
  checklistKey: string;
  data: ChecklistPayload;
  onCite?: (index: number) => void;
  compact?: boolean;
}

/**
 * Interactive, persisted compliance checklist rendered from a `checklist` widget event.
 * Steps are a real sequence, so they are numbered; filing a step stamps it.
 */
export function ChecklistWidget({ checklistKey, data, onCite, compact }: Props) {
  const { filed, toggle, reset } = useChecklist(checklistKey);
  const total = data.items.length;
  const done = data.items.filter((i) => filed[i.id]).length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  let n = 0;

  return (
    <section
      aria-label={data.header_title}
      className={cn("rounded-panel border border-rule bg-sheet", compact ? "p-4" : "p-5")}
    >
      <header className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold leading-snug text-ink">{data.header_title}</h3>
          <p className="mt-0.5 text-sm text-ink-soft">
            {done === total && total > 0 ? "Every step filed" : `${done} of ${total} steps filed`}
          </p>
        </div>
        {done > 0 && (
          <button
            onClick={reset}
            className="flex shrink-0 items-center gap-1 rounded-field px-2 py-1 text-sm text-ink-soft hover:bg-paper hover:text-ink"
          >
            <RotateCcw size={13} /> Clear
          </button>
        )}
      </header>

      {/* progress: a filing ledger bar */}
      <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-paper" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full bg-stamp transition-[width] duration-500" style={{ width: `${pct}%` }} />
      </div>

      <div className="space-y-5">
        {data.categories.map((cat) => {
          const items = data.items.filter((i) => i.category === cat);
          if (!items.length) return null;
          return (
            <div key={cat}>
              <h4 className="mb-2 text-sm font-semibold text-registry">{cat}</h4>
              <ol className="space-y-1">
                {items.map((item) => {
                  n += 1;
                  const at = filed[item.id];
                  return (
                    <li key={item.id} className="relative">
                      <label
                        className={cn(
                          "group flex cursor-pointer gap-3 rounded-field px-2 py-2.5 transition-colors",
                          at ? "bg-stamp-wash/50" : "hover:bg-paper",
                        )}
                      >
                        <input type="checkbox" className="peer sr-only" checked={!!at} onChange={() => toggle(item.id)} />
                        <span
                          className={cn(
                            "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] border text-xs font-semibold tabular-nums transition-colors peer-focus-visible:ring-2 peer-focus-visible:ring-registry",
                            at ? "border-stamp bg-stamp text-white" : "border-ink-faint/60 text-ink-soft group-hover:border-ink",
                          )}
                        >
                          {at ? <Check size={13} strokeWidth={3} /> : n}
                        </span>
                        <span className="min-w-0 flex-1 pr-16">
                          <span className={cn("block text-[0.95rem] font-medium leading-snug", at ? "text-ink-soft" : "text-ink")}>
                            {item.label}
                          </span>
                          {item.sublines.map((s, i) => (
                            <span key={i} className="mt-1 block text-sm leading-snug text-ink-soft">
                              {s}
                            </span>
                          ))}
                          {item.source_refs.length > 0 && onCite && (
                            <span className="mt-1.5 flex gap-1">
                              {item.source_refs.map((r) => (
                                <button
                                  key={r}
                                  type="button"
                                  onClick={(e) => {
                                    e.preventDefault();
                                    onCite(r);
                                  }}
                                  className="rounded-[4px] border border-stamp/30 px-1.5 text-xs font-semibold text-stamp hover:bg-stamp-wash"
                                  aria-label={`Show source ${r}`}
                                >
                                  Source {r}
                                </button>
                              ))}
                            </span>
                          )}
                        </span>
                      </label>
                      {at && (
                        <div className="pointer-events-none absolute right-1 top-1/2 -translate-y-1/2">
                          <Stamp date={at} className="h-[4.25rem] w-[4.25rem]" />
                        </div>
                      )}
                    </li>
                  );
                })}
              </ol>
            </div>
          );
        })}
      </div>
    </section>
  );
}
