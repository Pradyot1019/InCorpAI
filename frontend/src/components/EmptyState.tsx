import type { Jurisdiction } from "@/lib/types";

/** First screen: the question, framed by the scope the user has chosen. */
export function EmptyState({ jurisdiction, entityLabel, onPick }: { jurisdiction?: Jurisdiction; entityLabel: string; onPick: (q: string) => void }) {
  return (
    <div className="mx-auto flex w-full max-w-[46rem] flex-1 flex-col justify-center px-5 py-12 sm:px-8">
      <h1 className="max-w-[18ch] text-3xl font-bold leading-[1.08] tracking-[-0.02em] text-ink sm:text-[2.9rem] sm:leading-[1.04]">
        What are you filing{jurisdiction ? ` in ${shortName(jurisdiction)}` : ""}?
      </h1>
      <p className="mt-4 max-w-[58ch] font-serif text-lg leading-relaxed text-ink-soft">
        Ask about forming and running a {entityLabel}. Every answer is drawn only from the{" "}
        {jurisdiction?.document_count ?? 0} indexed {jurisdiction?.name ?? ""} regulatory documents, with the exact clause cited.
      </p>

      {jurisdiction && jurisdiction.suggested_prompts.length > 0 && (
        <div className="mt-10">
          <h2 className="mb-3 text-sm font-semibold text-ink">Start with a common question</h2>
          <ul className="divide-y divide-rule border-y border-rule">
            {jurisdiction.suggested_prompts.map((q) => (
              <li key={q}>
                <button
                  onClick={() => onPick(q)}
                  className="group flex w-full items-baseline justify-between gap-4 py-3.5 text-left text-base text-ink hover:text-registry"
                >
                  <span>{q}</span>
                  <span className="shrink-0 text-sm text-ink-faint opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                    Ask
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function shortName(j: Jurisdiction) {
  return j.code === "US-DE" ? "Delaware" : j.code === "EU" ? "the EU" : j.name;
}
