import { MessageSquarePlus, Trash2 } from "lucide-react";
import type { Conversation, Health, Jurisdiction } from "@/lib/types";
import { cn, relativeTime } from "@/lib/utils";

interface Props {
  jurisdictions: Jurisdiction[];
  phases: string[];
  jurisdiction: string;
  entityType: string;
  phase: string | null;
  onJurisdiction: (code: string) => void;
  onEntityType: (v: string) => void;
  onPhase: (v: string | null) => void;
  conversations: Conversation[];
  activeId: string | null;
  onOpen: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  health: Health | null;
}

/** Left rail: the scope every answer is filtered to, plus conversation history. */
export function CaseFile(p: Props) {
  const current = p.jurisdictions.find((j) => j.code === p.jurisdiction);

  return (
    <aside className="flex h-full flex-col bg-paper">
      <div className="flex items-center justify-between px-5 pb-4 pt-5">
        <a href="/" className="flex items-center gap-2" aria-label="IncCorpAI home">
          <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
            <circle cx="16" cy="16" r="13" fill="none" stroke="rgb(var(--stamp))" strokeWidth="3" />
            <circle cx="16" cy="16" r="7.5" fill="rgb(var(--registry))" />
          </svg>
          <span className="text-lg font-bold tracking-tight text-ink">IncCorpAI</span>
        </a>
        <button
          onClick={p.onNew}
          className="flex items-center gap-1.5 rounded-field border border-rule bg-sheet px-2.5 py-1.5 text-sm font-medium text-ink hover:border-ink-faint"
        >
          <MessageSquarePlus size={15} /> New
        </button>
      </div>

      <div className="scroll-quiet flex-1 overflow-y-auto px-5 pb-5">
        <fieldset>
          <legend className="mb-2 text-sm font-semibold text-ink">Jurisdiction</legend>
          <div className="space-y-1.5">
            {p.jurisdictions.map((j) => {
              const on = j.code === p.jurisdiction;
              return (
                <label
                  key={j.code}
                  className={cn(
                    "relative flex cursor-pointer gap-3 rounded-field border px-3 py-2.5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-registry",
                    on ? "border-registry bg-sheet" : "border-transparent hover:bg-sheet/70",
                  )}
                >
                  <input type="radio" name="jurisdiction" className="sr-only" checked={on} onChange={() => p.onJurisdiction(j.code)} />
                  <span
                    className={cn(
                      "mt-0.5 flex h-6 min-w-[3.1rem] items-center justify-center whitespace-nowrap rounded-[4px] px-1.5 text-xs font-bold tabular-nums",
                      on ? "bg-registry text-white" : "bg-sheet text-ink-soft ring-1 ring-rule",
                    )}
                  >
                    {j.code}
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-semibold leading-snug text-ink">{j.name}</span>
                    <span className="block text-xs leading-snug text-ink-soft">{j.summary}</span>
                  </span>
                </label>
              );
            })}
          </div>
        </fieldset>

        {current && (
          <fieldset className="mt-6">
            <legend className="mb-2 text-sm font-semibold text-ink">Entity type</legend>
            <div className="flex flex-wrap gap-1.5">
              {current.entity_types.map((e) => {
                const on = e.value === p.entityType;
                return (
                  <label
                    key={e.value}
                    title={e.label}
                    className={cn(
                      "cursor-pointer rounded-field border px-3 py-1.5 text-sm font-medium transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-registry",
                      on ? "border-ink bg-ink text-white" : "border-rule bg-sheet text-ink hover:border-ink-faint",
                    )}
                  >
                    <input type="radio" name="entity" className="sr-only" checked={on} onChange={() => p.onEntityType(e.value)} />
                    {e.value === "Any" ? "Any entity" : e.label}
                  </label>
                );
              })}
            </div>
          </fieldset>
        )}

        <div className="mt-6">
          <label htmlFor="phase" className="mb-2 block text-sm font-semibold text-ink">
            Stage
          </label>
          <select
            id="phase"
            value={p.phase ?? ""}
            onChange={(e) => p.onPhase(e.target.value || null)}
            className="w-full rounded-field border border-rule bg-sheet px-2.5 py-2 text-sm text-ink focus:border-registry focus:outline-none"
          >
            <option value="">Every stage</option>
            {p.phases.map((ph) => (
              <option key={ph} value={ph}>
                {ph}
              </option>
            ))}
          </select>
        </div>

        {p.conversations.length > 0 && (
          <nav className="mt-8" aria-label="Previous questions">
            <h2 className="mb-2 text-sm font-semibold text-ink">Previous questions</h2>
            <ul className="space-y-0.5">
              {p.conversations.map((c) => (
                <li key={c.id} className="group relative">
                  <button
                    onClick={() => p.onOpen(c.id)}
                    className={cn(
                      "w-full rounded-field px-2.5 py-2 pr-8 text-left transition-colors",
                      c.id === p.activeId ? "bg-sheet shadow-[inset_2px_0_0_rgb(var(--registry))]" : "hover:bg-sheet/70",
                    )}
                  >
                    <span className="block truncate text-sm text-ink">{c.title}</span>
                    <span className="block text-xs text-ink-faint">
                      {c.jurisdiction}, {c.entity_type}, {relativeTime(c.updated_at)}
                    </span>
                  </button>
                  <button
                    onClick={() => p.onDelete(c.id)}
                    className="absolute right-1.5 top-2 rounded p-1 text-ink-faint opacity-0 hover:bg-paper hover:text-ink group-hover:opacity-100 focus:opacity-100"
                    aria-label={`Delete "${c.title}"`}
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        )}
      </div>

      {p.health && (
        <div className="border-t border-rule px-5 py-3 text-xs text-ink-soft">
          <span className="font-semibold text-ink">{p.health.documents}</span> documents,{" "}
          <span className="font-semibold text-ink">{p.health.chunks}</span> clauses indexed
          {p.health.offline && (
            <span className="mt-1 block text-notice">Offline mode: add an Anthropic API key for written answers.</span>
          )}
        </div>
      )}
    </aside>
  );
}
