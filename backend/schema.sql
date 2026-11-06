-- ============================================================================
-- IncCorpAI — PostgreSQL + pgvector schema
-- Idempotent: safe to run on every boot.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid() on PG < 13

-- ----------------------------------------------------------------------------
-- Source documents (one row per ingested file)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_document TEXT NOT NULL UNIQUE,          -- file name, e.g. SPICe_Plus_MCA_Guidelines.md
    title           TEXT NOT NULL,
    source_url      TEXT,
    checksum        TEXT NOT NULL,                 -- sha256 of raw file, skip re-ingest if unchanged
    metadata        JSONB NOT NULL DEFAULT '{}',   -- document-level metadata (jurisdiction, entity_type, ...)
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Chunks: the retrieval unit
-- ----------------------------------------------------------------------------
-- NOTE: the embedding dimension must match EMBEDDING_DIM in settings.
-- text-embedding-3-small = 1536. The bundled offline "hash" embedder also emits 1536.
CREATE TABLE IF NOT EXISTS compliance_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    content         TEXT NOT NULL,                 -- text WITH breadcrumb prefix (what gets embedded)
    header_path     TEXT[] NOT NULL DEFAULT '{}',  -- e.g. {Incorporation, SPICe+ Part B, Section 3}
    header_text     TEXT NOT NULL DEFAULT '',      -- breadcrumb joined with ' > ' (weighted 'A' in tsv)
    content_hash    TEXT NOT NULL,
    embedding       VECTOR(1536) NOT NULL,
    embedding_model TEXT NOT NULL,
    tsv_content     TSVECTOR GENERATED ALWAYS AS (
                        setweight(to_tsvector('english', header_text), 'A') ||
                        setweight(to_tsvector('english', content), 'B')
                    ) STORED,
    metadata        JSONB NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

-- Metadata pre-filtering (jsonb @> containment) — jsonb_path_ops is smaller/faster for @>
CREATE INDEX IF NOT EXISTS idx_chunks_metadata
    ON compliance_chunks USING gin (metadata jsonb_path_ops);

-- Hot filter keys as expression indexes (planner can use these for equality)
CREATE INDEX IF NOT EXISTS idx_chunks_jurisdiction
    ON compliance_chunks ((metadata->>'jurisdiction'));
CREATE INDEX IF NOT EXISTS idx_chunks_entity_type
    ON compliance_chunks ((metadata->>'entity_type'));

-- Dense ANN index (cosine)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON compliance_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Sparse / keyword index
CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON compliance_chunks USING gin (tsv_content);

-- Fuzzy match on clause ids ("SPICe+ Part B", "Form INC-20A")
CREATE INDEX IF NOT EXISTS idx_chunks_clause_trgm
    ON compliance_chunks USING gin ((metadata->>'clause_id') gin_trgm_ops);

-- ----------------------------------------------------------------------------
-- Query log (observability / offline eval)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query           TEXT NOT NULL,
    filters         JSONB NOT NULL,
    retrieved_ids   UUID[] NOT NULL DEFAULT '{}',
    top_score       REAL,
    rejected        BOOLEAN NOT NULL DEFAULT FALSE,
    latency_ms      INTEGER,
    llm_model       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
