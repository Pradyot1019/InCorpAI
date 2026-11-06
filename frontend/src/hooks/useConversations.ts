import { useCallback, useEffect, useRef, useState } from "react";
import { streamChat } from "@/lib/api";
import type { AssistantMessage, ChatEvent, Conversation, Message } from "@/lib/types";
import { storage, uid } from "@/lib/utils";

const KEY = "inccorpai.conversations.v1";
const MAX_SAVED = 30;

function newConversation(jurisdiction: string, entity_type: string): Conversation {
  return { id: uid(), title: "New question", jurisdiction, entity_type, messages: [], updated_at: Date.now() };
}

/**
 * Conversation list + the active conversation's streaming state.
 * Persisted to localStorage so a refresh keeps history and checklists.
 */
export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>(() =>
    // a reload mid-stream leaves messages in a pending stage; settle them
    storage.get<Conversation[]>(KEY, []).map((c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.role === "assistant" && m.stage !== "done" && m.stage !== "error" ? { ...m, stage: "done" as const } : m,
      ),
    })),
  );
  const [activeId, setActiveId] = useState<string | null>(() => conversations[0]?.id ?? null);
  const [streaming, setStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // don't persist half-streamed messages as "in progress" forever
    storage.set(KEY, conversations.slice(0, MAX_SAVED));
  }, [conversations]);

  const active = conversations.find((c) => c.id === activeId) ?? null;

  const patchAssistant = useCallback((convId: string, msgId: string, fn: (m: AssistantMessage) => AssistantMessage) => {
    setConversations((prev) =>
      prev.map((c) =>
        c.id !== convId
          ? c
          : {
              ...c,
              updated_at: Date.now(),
              messages: c.messages.map((m) => (m.id === msgId && m.role === "assistant" ? fn(m) : m)),
            },
      ),
    );
  }, []);

  const startNew = useCallback(() => {
    abortRef.current?.abort();
    setActiveId(null);
  }, []);

  const remove = useCallback((id: string) => {
    setConversations((prev) => prev.filter((c) => c.id !== id));
    setActiveId((cur) => (cur === id ? null : cur));
  }, []);

  const stop = useCallback(() => abortRef.current?.abort(), []);

  const send = useCallback(
    async (query: string, opts: { jurisdiction: string; entity_type: string; compliance_phase: string | null }) => {
      if (streaming || !query.trim()) return;
      let conv = active;
      if (!conv) {
        conv = newConversation(opts.jurisdiction, opts.entity_type);
        conv.title = query.length > 64 ? query.slice(0, 61) + "…" : query;
      }
      const history = conv.messages
        .filter((m) => m.content && !(m.role === "assistant" && (m.done?.rejected || m.error)))
        .map((m) => ({ role: m.role, content: m.content }));

      const userMsg: Message = { id: uid(), role: "user", content: query };
      const asst: AssistantMessage = {
        id: uid(), role: "assistant", content: "", stage: "retrieving", sources: [], widgets: [],
      };
      const convId = conv.id;
      const nextConv: Conversation = {
        ...conv,
        jurisdiction: opts.jurisdiction,
        entity_type: opts.entity_type,
        messages: [...conv.messages, userMsg, asst],
        updated_at: Date.now(),
      };
      setConversations((prev) => [nextConv, ...prev.filter((c) => c.id !== convId)]);
      setActiveId(convId);
      setStreaming(true);

      const ctrl = new AbortController();
      abortRef.current = ctrl;

      const onEvent = (e: ChatEvent) => {
        patchAssistant(convId, asst.id, (m) => {
          switch (e.event) {
            case "filters":
              return { ...m, filters: e.data };
            case "status":
              return { ...m, stage: e.data.stage };
            case "sources":
              return { ...m, sources: e.data.sources };
            case "token":
              return { ...m, content: m.content + e.data.text };
            case "widget":
              return { ...m, widgets: [...m.widgets, e.data] };
            case "done":
              return { ...m, stage: "done", done: e.data };
            case "error":
              return { ...m, stage: "error", error: e.data.message };
          }
        });
      };

      try {
        await streamChat(
          { query, history, jurisdiction: opts.jurisdiction, entity_type: opts.entity_type, compliance_phase: opts.compliance_phase },
          onEvent,
          ctrl.signal,
        );
        patchAssistant(convId, asst.id, (m) => (m.stage === "done" || m.stage === "error" ? m : { ...m, stage: "done" }));
      } catch (err) {
        const aborted = (err as Error).name === "AbortError";
        patchAssistant(convId, asst.id, (m) => ({
          ...m,
          stage: aborted ? "done" : "error",
          error: aborted
            ? undefined
            : `Couldn't reach the IncCorpAI API. ${(err as Error).message} Check that the backend is running on port 8000.`,
        }));
      } finally {
        setStreaming(false);
        abortRef.current = null;
      }
    },
    [active, streaming, patchAssistant],
  );

  return { conversations, active, activeId, setActiveId, startNew, remove, send, stop, streaming };
}
