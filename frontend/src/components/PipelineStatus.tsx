import { Check } from "lucide-react";
import type { Stage } from "@/lib/types";
import { cn } from "@/lib/utils";

const STEPS: { stage: Stage; label: string }[] = [
  { stage: "retrieving", label: "Searching regulations" },
  { stage: "reranking", label: "Ranking clauses" },
  { stage: "generating", label: "Drafting answer" },
];

/** Shows where the request is in the retrieve → rerank → generate sequence. */
export function PipelineStatus({ stage }: { stage: Stage }) {
  const current = STEPS.findIndex((s) => s.stage === stage);
  return (
    <ol className="flex flex-wrap items-center gap-x-4 gap-y-1 font-sans text-sm" aria-live="polite">
      {STEPS.map((s, i) => {
        const state = i < current ? "done" : i === current ? "active" : "todo";
        return (
          <li key={s.stage} className={cn("flex items-center gap-1.5", state === "todo" ? "text-ink-faint" : "text-ink-soft")}>
            <span
              className={cn(
                "flex h-4 w-4 items-center justify-center rounded-full border",
                state === "done" && "border-registry bg-registry text-white",
                state === "active" && "border-registry",
                state === "todo" && "border-rule",
              )}
            >
              {state === "done" ? <Check size={10} strokeWidth={3.5} /> : state === "active" ? <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-registry" /> : null}
            </span>
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}
