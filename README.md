# IncCorpAI

Production-grade RAG engine for multi-jurisdictional startup incorporation and regulatory compliance.

Founders ask questions like *"walk me through SPICe+"* or *"when is the 83(b) due?"* and get
answers grounded only in indexed regulations for **their** jurisdiction and entity type, with
every sentence cited to a clause. Process questions also return an interactive checklist that
persists as they file each step.

```
             ┌──────────── metadata pre-filter (jurisdiction, entity type, phase) ───────────┐
query ─▶ filter │  dense: pgvector cosine (HNSW)   ┐                                          │
  │   resolution│                                  ├─▶ 0.7·dense + 0.3·keyword ─▶ top 20 ─▶ rerank ─▶ top 5
  │             │  sparse: Postgres FTS × IDF cov. ┘                                          │
  │             └───────────────────────────────────────────────────────────────────────────┘
  │                                   best score < threshold? ─▶ strict rejection (no LLM call)
  └────────────────────────────────────────────▶ Claude (streamed) ─▶ widget parser ─▶ SSE
                                                                     filters · status · sources · token · widget · done
```

## What's in the box

| Path | What |
|---|---|
| `backend/schema.sql` | PostgreSQL + pgvector schema: `documents`, `compliance_chunks` (HNSW, GIN on JSONB, weighted tsvector, trigram on clause ids), `query_log` |
| `backend/ingest.py` | CLI ingestion: Markdown (front-matter), PDF, TXT → structure-aware chunks → embeddings → upsert. Idempotent by checksum. |
| `backend/main.py` | FastAPI app: `/api/chat` (SSE), `/api/search`, `/api/taxonomy`, `/api/documents`, `/api/health` |
| `backend/app/` | `ingestion/` chunker + loaders, `retrieval/` hybrid search + rerankers, `generation/` prompt, Claude/offline LLMs, widget stream parser |
| `corpus/` | Seed regulatory corpus: India (SPICe+, post-incorporation, LLP, DPIIT, DPDP), Delaware C-Corp, EU GDPR |
| `frontend/` | Reference UI in Lovable's stack (Vite, React, TS, Tailwind) |
| `docs/API.md` | API and SSE event contract |
| `docs/LOVABLE_PROMPT.md` | How to take the frontend into Lovable, plus a full build prompt |

## Quick start

**Docker (everything):**

```bash
cp backend/.env.example backend/.env     # add API keys if you have them (all optional)
docker compose up --build -d db api web
docker compose run --rm ingest           # index ./corpus
open http://localhost:8080
```

**Local dev:**

```bash
# Postgres 16 with pgvector on localhost:5432 (e.g. `docker compose up -d db`)
cd backend
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"
cp .env.example .env
python ingest.py ../corpus
uvicorn main:app --reload --port 8000

cd ../frontend
npm install && npm run dev               # http://localhost:5173, /api is proxied to :8000
```

### Runs with zero API keys

Every external provider has a local fallback, so the full product works offline for
development and demos, and switches to the real provider as soon as a key is set:

| Stage | With key | Without key |
|---|---|---|
| Embeddings | OpenAI `text-embedding-3-small` (1536-d) | Deterministic feature-hashing embedder (lexical) |
| Rerank | Cohere `rerank-v3.5` | Local `bge-reranker-large` if `.[local-rerank]` installed, else hybrid order |
| Generation | Claude (`ANTHROPIC_MODEL`, default `claude-sonnet-5-5`) | Extractive responder that quotes cited sentences and builds checklists |

Changing the embedder requires re-running `python ingest.py ../corpus --force`. The model
name is stored per chunk, and retrieval only searches chunks from the active embedder.

## Design decisions (changes from the initial plan)

- **Widgets travel as their own SSE event.** The plan had the frontend parse
  `<TemplateWidget templateName="checklist">` out of the token stream. Here the backend's
  `WidgetStreamParser` strips the block from the stream (safe across partial frames),
  validates it with Pydantic, de-duplicates ids, and emits a typed `widget` event. Any
  frontend just renders JSON, and broken model JSON never reaches the UI.
- **Named SSE events instead of `data: {text}` + `[DONE]`.** `filters`, `status`, `sources`,
  `token`, `widget`, `done`, `error`. Sources arrive before the first token, so citations are
  clickable while the answer is still streaming.
- **Strict negative rejection happens before the LLM.** If the best hybrid score is under
  `MIN_RELEVANCE`, the API refuses immediately, without spending tokens or risking a guess.
  The system prompt enforces the same rule for partial matches.
- **A keyword score that behaves like BM25.** Postgres `ts_rank_cd` saturates ("pizza
  company" ranks about as high as a real match). The keyword score is multiplied by
  IDF-weighted query-term coverage, which separates relevant from off-topic queries cleanly
  (seed corpus: relevant ≥ 0.28, off-topic ≤ 0.16).
- **Filters resolved from the question too.** Asking about Delaware while India is selected
  searches US-DE and tells the user why (`filters.note`). Entity types are validated per
  jurisdiction. Entity-agnostic documents (`entity_type: Any`, such as GDPR and DPDP) match
  every entity.
- **Structure-aware chunking without tree-sitter.** `markdown-it-py` gives a proper
  CommonMark + GFM AST. Chunks never cross sections, carry the full header breadcrumb
  (embedded and in metadata), keep tables whole, and split oversized tables by row with the
  header repeated. Headings can override metadata: `## Part A {clause="SPICe+ Part A" phase="Pre-Incorporation"}`.
- **Normalised schema.** A `documents` table with checksums makes re-ingestion idempotent
  and deletion cascade. `query_log` records every query, score and rejection for offline evaluation.
- **Prompt caching** on the system prompt, plus conversation history coerced to strict
  user/assistant alternation.

## Configuration

See `backend/.env.example`. The most important knob is `MIN_RELEVANCE`: tune it against
`POST /api/search` whenever you change embedders or the corpus.

## Testing

```bash
cd backend && pytest -q        # chunker, widget stream parser, filters, offline LLM
cd frontend && npm run typecheck
```

## Content disclaimer

The seed corpus summarises public statutes and official guidance as of its `last_reviewed`
dates. It is development data, not legal advice. Replace it with the official documents
(MCA, DPIIT, Delaware Division of Corporations, IRS, EUR-Lex) before production use; each
file links its primary source.
