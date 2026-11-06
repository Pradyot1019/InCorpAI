# IncCorpAI API contract

Base URL: `http://localhost:8000` in development. Interactive OpenAPI docs at `/docs`.
TypeScript mirrors of every shape live in `frontend/src/lib/types.ts`; a working SSE client
is in `frontend/src/lib/api.ts`. Any frontend (including a Lovable build) can copy those two
files unchanged.

## `GET /api/taxonomy`

Everything a UI needs to build its filters and empty state. Never hard-code these options.

```json
{
  "jurisdictions": [
    {
      "code": "IN",
      "name": "India",
      "regulators": ["MCA", "DPIIT", "CBDT", "MeitY"],
      "entity_types": [{ "value": "Pvt Ltd", "label": "Private Limited Company" }, ...],
      "summary": "Companies Act 2013, SPICe+ filing, Startup India, DPDP Act 2023",
      "document_count": 5,
      "suggested_prompts": ["Walk me through incorporating a Private Limited company with SPICe+", ...]
    }
  ],
  "compliance_phases": ["Pre-Incorporation", "Incorporation", "Post-Incorporation", "Ongoing Compliance", "Data Privacy"]
}
```

## `GET /api/health`

```json
{ "status": "ok", "documents": 8, "chunks": 47, "llm": "claude-sonnet-5-5",
  "embedder": "text-embedding-3-small", "reranker": "cohere:rerank-v3.5", "offline": false }
```

`offline: true` means no Anthropic key is set and answers are extractive.

## `POST /api/chat` — Server-Sent Events

Request:

```json
{
  "query": "What are the steps to form a Delaware C-Corp?",
  "jurisdiction": "US-DE",
  "entity_type": "C-Corp",
  "compliance_phase": null,
  "sector": "Tech",
  "history": [{ "role": "user", "content": "..." }, { "role": "assistant", "content": "..." }],
  "auto_detect_filters": true
}
```

`EventSource` only supports GET, so read the `fetch` body stream and parse frames
(`event:` + `data:` lines, blank-line separated). Events arrive in this order:

| Event | When | `data` |
|---|---|---|
| `filters` | first | `{ jurisdiction, entity_type, compliance_phase, overridden, note }` — `note` is a human sentence when the query text overrode the UI filters (e.g. a Delaware question asked while India was selected). Show it. |
| `status` | 1–3 times | `{ stage: "retrieving" \| "reranking" \| "generating", label }` |
| `sources` | once, before any token | `{ sources: Source[] }` — `Source.index` matches `[n]` markers in the answer text. Empty when rejected. |
| `token` | many | `{ text }` — markdown delta. Append. Contains `[1]`-style citations. Never contains widget markup. |
| `widget` | 0–1, after the prose | `{ template: "checklist", payload: ChecklistPayload }` — already validated and de-duplicated. |
| `done` | last | `{ rejected, reason?, top_score, latency_ms, model, reranker, candidates, usage }` |
| `error` | instead of `done` | `{ message }` |

`rejected: true` means strict negative rejection fired: no indexed clause was relevant
enough, the LLM was not called, and the single `token` event holds a refusal message.

```ts
interface Source {
  index: number; chunk_id: string;
  document_title: string; source_document: string; source_url: string | null;
  clause_id: string | null; section_path: string[];
  jurisdiction: string; entity_type: string; regulatory_body: string; compliance_phase: string;
  snippet: string;   // ≤280 chars, for cards
  content: string;   // full chunk markdown (may include tables)
  score: number;
}

interface ChecklistPayload {
  header_title: string;
  categories: string[];
  items: { id: string; label: string; sublines: string[]; category: string;
           checked: boolean; source_refs: number[] }[];
}
```

## `POST /api/search`

Retrieval only, no LLM — for relevance debugging and evals.
Body: `{ query, jurisdiction, entity_type, compliance_phase?, top_k = 5, rerank = true }` → `Source[]`.

## Documents

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/documents?jurisdiction=IN` | `DocumentInfo[]` |
| `POST` | `/api/documents` | multipart: `file` (.md/.pdf/.txt), `metadata` (JSON string: `jurisdiction`, `entity_type`, `regulatory_body`, `compliance_phase`, optional `title`, `source_url`), `force`. Requires `X-Admin-Token` if `ADMIN_TOKEN` is set. Markdown front-matter is merged with `metadata`. |
| `DELETE` | `/api/documents/{id}` | Cascades to its chunks. Admin. |
| `GET` | `/api/chunks/{id}` | Full chunk content and metadata. |
