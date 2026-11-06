import { memo, useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Source } from "@/lib/types";

/**
 * Renders the streamed markdown answer. Citation markers like [2] become buttons that
 * open the matching source in the dossier. Markers outside the source range stay text.
 */
export const Answer = memo(function Answer({
  text,
  sources,
  onCite,
  streaming,
}: {
  text: string;
  sources: Source[];
  onCite: (index: number) => void;
  streaming: boolean;
}) {
  const md = useMemo(() => {
    const max = sources.length;
    // don't touch [n] inside inline code; good enough for prose answers
    return text.replace(/(`[^`]*`)|\[(\d{1,2})\](?!\()/g, (m, code, n) => {
      if (code) return code;
      const i = Number(n);
      return i >= 1 && i <= max ? `[${i}](#cite-${i})` : m;
    });
  }, [text, sources.length]);

  return (
    <div className="answer">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ href, children }) {
            if (href?.startsWith("#cite-")) {
              const i = Number(href.slice(6));
              const s = sources[i - 1];
              return (
                <button
                  type="button"
                  onClick={() => onCite(i)}
                  className="cite mx-[1px] inline-flex h-[1.15rem] min-w-[1.15rem] -translate-y-[0.35em] items-center justify-center rounded-[4px] bg-stamp-wash px-1 align-baseline font-sans text-[0.66rem] font-bold leading-none text-stamp transition-colors hover:bg-stamp hover:text-white"
                  title={s ? `${s.document_title} — ${s.clause_id ?? ""}` : undefined}
                  aria-label={`Source ${i}${s ? `: ${s.document_title}` : ""}`}
                >
                  {i}
                </button>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {md}
      </ReactMarkdown>
      {streaming && <span className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[0.15em] animate-caret bg-registry" aria-hidden />}
    </div>
  );
});
