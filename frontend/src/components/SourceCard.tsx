import { ChevronDown, ExternalLink } from "lucide-react";
import { forwardRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "@/lib/types";
import { cn } from "@/lib/utils";

export const SourceCard = forwardRef<HTMLElement, { source: Source; highlighted: boolean }>(function SourceCard(
  { source, highlighted },
  ref,
) {
  const [open, setOpen] = useState(false);
  const isOpen = open || highlighted;
  const crumb = source.section_path.join(" › ");

  return (
    <article
      ref={ref}
      className={cn(
        "rounded-panel border bg-sheet transition-[box-shadow,border-color] duration-300",
        highlighted ? "border-stamp shadow-[0_0_0_3px_rgb(var(--stamp)/0.14)]" : "border-rule",
      )}
    >
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={isOpen}
        className="flex w-full items-start gap-3 p-3.5 text-left"
      >
        <span className="mt-0.5 flex h-5 min-w-5 items-center justify-center rounded-[4px] bg-stamp-wash px-1 text-xs font-bold text-stamp">
          {source.index}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold leading-snug text-ink">{source.clause_id || crumb}</span>
          <span className="mt-0.5 block truncate text-xs text-ink-soft">{source.document_title}</span>
          <span className="mt-1.5 flex flex-wrap gap-1.5 text-xs text-ink-soft">
            <span className="rounded-[4px] bg-paper px-1.5 py-0.5">{source.regulatory_body}</span>
            <span className="rounded-[4px] bg-paper px-1.5 py-0.5">{source.compliance_phase}</span>
          </span>
        </span>
        <ChevronDown size={16} className={cn("mt-0.5 shrink-0 text-ink-faint transition-transform", isOpen && "rotate-180")} />
      </button>
      {isOpen && (
        <div className="border-t border-rule px-3.5 pb-3.5 pt-3">
          {crumb && crumb !== source.clause_id && <p className="mb-2 text-xs text-ink-faint">{crumb}</p>}
          <div className="answer max-h-80 overflow-y-auto pr-1 text-[0.9rem] leading-relaxed scroll-quiet [&>*:first-child]:mt-0">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{source.content}</ReactMarkdown>
          </div>
          {source.source_url && (
            <a
              href={source.source_url}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-registry hover:underline"
            >
              Open official source <ExternalLink size={13} />
            </a>
          )}
        </div>
      )}
    </article>
  );
});
