// Mirrors backend/app/core/models.py. Keep in sync with docs/API.md.

export interface EntityTypeOption {
  value: string;
  label: string;
}

export interface Jurisdiction {
  code: string;
  name: string;
  regulators: string[];
  entity_types: EntityTypeOption[];
  summary: string;
  document_count: number;
  suggested_prompts: string[];
}

export interface Taxonomy {
  jurisdictions: Jurisdiction[];
  compliance_phases: string[];
}

export interface Health {
  status: "ok";
  documents: number;
  chunks: number;
  llm: string;
  embedder: string;
  reranker: string;
  offline: boolean;
}

export interface Source {
  index: number;
  chunk_id: string;
  document_title: string;
  source_document: string;
  source_url: string | null;
  clause_id: string | null;
  section_path: string[];
  jurisdiction: string;
  entity_type: string;
  regulatory_body: string;
  compliance_phase: string;
  snippet: string;
  content: string;
  score: number;
}

export interface AppliedFilters {
  jurisdiction: string;
  entity_type: string;
  compliance_phase: string | null;
  overridden: boolean;
  note: string | null;
}

export interface ChecklistItem {
  id: string;
  label: string;
  sublines: string[];
  category: string;
  checked: boolean;
  source_refs: number[];
}

export interface ChecklistPayload {
  header_title: string;
  categories: string[];
  items: ChecklistItem[];
}

export interface Widget {
  template: "checklist" | string;
  payload: ChecklistPayload;
}

export type Stage = "retrieving" | "reranking" | "generating";

export interface DoneInfo {
  rejected: boolean;
  reason?: string;
  top_score: number;
  latency_ms: number;
  model: string | null;
  reranker: string | null;
  candidates: number;
  usage: { input_tokens: number; output_tokens: number; cache_read_tokens: number } | null;
}

/** Discriminated union of every SSE event emitted by POST /api/chat. */
export type ChatEvent =
  | { event: "filters"; data: AppliedFilters }
  | { event: "status"; data: { stage: Stage; label: string } }
  | { event: "sources"; data: { sources: Source[] } }
  | { event: "token"; data: { text: string } }
  | { event: "widget"; data: Widget }
  | { event: "done"; data: DoneInfo }
  | { event: "error"; data: { message: string } };

export interface ChatRequest {
  query: string;
  jurisdiction: string;
  entity_type: string;
  sector?: string | null;
  compliance_phase?: string | null;
  history?: { role: "user" | "assistant"; content: string }[];
  auto_detect_filters?: boolean;
}

// ---- Client-side conversation model -------------------------------------------------

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  content: string;
  stage: Stage | "done" | "error";
  sources: Source[];
  widgets: Widget[];
  filters?: AppliedFilters;
  done?: DoneInfo;
  error?: string;
}

export type Message = UserMessage | AssistantMessage;

export interface Conversation {
  id: string;
  title: string;
  jurisdiction: string;
  entity_type: string;
  messages: Message[];
  updated_at: number;
}
