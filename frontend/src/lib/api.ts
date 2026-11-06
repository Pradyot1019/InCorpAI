import type { ChatEvent, ChatRequest, Health, Taxonomy } from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ?? "";

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json() as Promise<T>;
}

export const getTaxonomy = () => getJSON<Taxonomy>("/api/taxonomy");
export const getHealth = () => getJSON<Health>("/api/health");

/**
 * POST /api/chat and parse the Server-Sent Events stream.
 *
 * EventSource only supports GET, so we read the fetch body and parse SSE frames
 * ourselves. Frames are separated by a blank line; each has `event:` and `data:` lines.
 * Handles frames split across network chunks and CRLF line endings.
 */
export async function streamChat(
  body: ChatRequest,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = `The server returned ${res.status}.`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (frame: string) => {
    let event = "message";
    const data: string[] = [];
    for (const line of frame.split(/\r?\n/)) {
      if (line.startsWith(":")) continue; // comment / ping
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (!data.length) return;
    try {
      onEvent({ event, data: JSON.parse(data.join("\n")) } as ChatEvent);
    } catch {
      /* ignore malformed frame */
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: RegExpExecArray | null;
    const re = /\r?\n\r?\n/g;
    let last = 0;
    while ((sep = re.exec(buffer))) {
      dispatch(buffer.slice(last, sep.index));
      last = sep.index + sep[0].length;
    }
    buffer = buffer.slice(last);
  }
  if (buffer.trim()) dispatch(buffer);
}
