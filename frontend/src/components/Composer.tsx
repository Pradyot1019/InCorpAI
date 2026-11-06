import { ArrowUp, Square } from "lucide-react";
import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export interface ComposerHandle {
  fill: (text: string) => void;
}

interface Props {
  onSend: (text: string) => void;
  onStop: () => void;
  streaming: boolean;
  scopeLabel: string;
}

export const Composer = forwardRef<ComposerHandle, Props>(function Composer({ onSend, onStop, streaming, scopeLabel }, ref) {
  const [text, setText] = useState("");
  const ta = useRef<HTMLTextAreaElement>(null);

  useImperativeHandle(ref, () => ({
    fill: (t) => {
      setText(t);
      requestAnimationFrame(() => ta.current?.focus());
    },
  }));

  useEffect(() => {
    const el = ta.current;
    if (!el) return;
    el.style.height = "0px";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, [text]);

  const submit = () => {
    if (!text.trim() || streaming) return;
    onSend(text.trim());
    setText("");
  };

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="mx-auto w-full max-w-[46rem] px-5 pb-5 sm:px-8"
    >
      <div className="rounded-panel border border-rule bg-sheet shadow-[0_1px_0_rgb(var(--rule)),0_8px_24px_-12px_rgb(var(--ink)/0.18)] focus-within:border-registry">
        <label htmlFor="q" className="sr-only">
          Ask a compliance question
        </label>
        <textarea
          id="q"
          ref={ta}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              submit();
            }
          }}
          placeholder="Ask about a filing, deadline or obligation"
          className="block w-full resize-none bg-transparent px-4 pb-1 pt-3.5 text-base text-ink placeholder:text-ink-faint focus:outline-none"
        />
        <div className="flex items-center justify-between gap-3 px-3 pb-2.5 pl-4">
          <span className="truncate text-xs text-ink-soft">Answers use {scopeLabel} sources only</span>
          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              className="flex h-8 items-center gap-1.5 rounded-field border border-rule px-3 text-sm font-medium text-ink hover:border-ink-faint"
            >
              <Square size={12} fill="currentColor" /> Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!text.trim()}
              className={cn(
                "flex h-8 items-center gap-1.5 rounded-field px-3 text-sm font-semibold transition-colors",
                text.trim() ? "bg-registry text-white hover:bg-registry-deep" : "bg-paper text-ink-faint",
              )}
            >
              Ask <ArrowUp size={14} strokeWidth={2.5} />
            </button>
          )}
        </div>
      </div>
      <p className="mt-2 text-center text-xs text-ink-faint">
        Grounded in indexed regulations, not legal advice. Confirm fees and deadlines on the official portal.
      </p>
    </form>
  );
});
