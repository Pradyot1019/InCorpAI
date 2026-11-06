"""Metadata-filtered hybrid search: dense (pgvector cosine) + sparse (Postgres full-text).

Score = dense_weight * cosine_similarity + sparse_weight * normalised_keyword_score

Both retrievers run against the *same* metadata pre-filter, so a chunk from another
jurisdiction can never enter the candidate pool ("cross-jurisdictional pollution").

Notes
-----
* Postgres `ts_rank_cd` is not true BM25, but with normalisation flag 32 (rank/(rank+1))
  plus header weighting ('A') it behaves as a bounded, length-aware keyword score. It is
  further max-normalised within the candidate pool so the 0.7 / 0.3 weights are meaningful.
* ts_rank_cd saturates quickly ("pizza company" ranks almost as high as a real match),
  so the final keyword score is multiplied by *IDF-weighted query-term coverage*: the share
  of the query's information content (sum of BM25 IDF of matched lexemes / all lexemes)
  that the chunk actually contains. Rare, unmatched words ("pizza") drag the score down,
  which is what makes strict negative rejection reliable.
* The keyword query is an OR of the user's terms (`to_tsquery('a | b | c')`) — the default
  `websearch_to_tsquery` ANDs terms and misses most natural-language questions.
"""

from __future__ import annotations

import math
import re
import time

import asyncpg
import numpy as np

from app.core.config import get_settings
from app.core.embeddings import get_embedder
from app.core.models import ChunkMetadata, RetrievedChunk

_WORD = re.compile(r"[A-Za-z0-9]+")


def build_or_tsquery(query: str) -> str:
    """'What is SPICe+ Part-B?' -> 'what | is | spice | part | b'  (stopwords dropped by PG)."""
    terms = list(dict.fromkeys(w.lower() for w in _WORD.findall(query) if len(w) > 1))
    return " | ".join(terms[:32])


class _IdfCache:
    """Document frequencies per lexeme (via ts_stat), refreshed on a TTL or after ingest."""

    TTL = 300.0

    def __init__(self) -> None:
        self.df: dict[str, int] = {}
        self.n_docs = 0
        self.loaded_at = 0.0

    def invalidate(self) -> None:
        self.loaded_at = 0.0

    async def ensure(self, conn: asyncpg.Connection) -> None:
        if time.monotonic() - self.loaded_at < self.TTL:
            return
        rows = await conn.fetch("SELECT word, ndoc FROM ts_stat('SELECT tsv_content FROM compliance_chunks')")
        self.df = {r["word"]: r["ndoc"] for r in rows}
        self.n_docs = await conn.fetchval("SELECT count(*) FROM compliance_chunks")
        self.loaded_at = time.monotonic()

    def idf(self, lexeme: str) -> float:
        df = self.df.get(lexeme, 0)
        n = max(self.n_docs, 1)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))


idf_cache = _IdfCache()


def idf_coverage(query_lexemes: list[str], matched: list[str]) -> float:
    total = sum(idf_cache.idf(l) for l in query_lexemes)
    if total <= 0:
        return 0.0
    return sum(idf_cache.idf(l) for l in set(matched)) / total


def filter_params(jurisdiction: str, entity_type: str, phase: str | None) -> tuple:
    return jurisdiction, [entity_type, "Any"], phase


_FILTER_SQL = """
    c.metadata->>'jurisdiction' = $2
    AND c.metadata->'entity_types' ?| $3::text[]
    AND ($4::text IS NULL OR c.metadata->>'compliance_phase' = $4)
    AND c.embedding_model = $5
"""

HYBRID_SQL = f"""
WITH dense AS (
    SELECT c.id, 1 - (c.embedding <=> $1) AS dense_score
    FROM compliance_chunks c
    WHERE {_FILTER_SQL}
    ORDER BY c.embedding <=> $1
    LIMIT $6
),
sparse AS (
    SELECT c.id, ts_rank_cd(c.tsv_content, q, 32) AS sparse_score
    FROM compliance_chunks c, to_tsquery('english', $7) q
    WHERE {_FILTER_SQL} AND $7 <> '' AND c.tsv_content @@ q
    ORDER BY sparse_score DESC
    LIMIT $6
),
pool AS (SELECT id FROM dense UNION SELECT id FROM sparse)
SELECT c.id::text AS id, c.content, c.metadata,
       COALESCE(d.dense_score, 1 - (c.embedding <=> $1)) AS dense_score,
       COALESCE(s.sparse_score, 0) AS sparse_score,
       ARRAY(SELECT l FROM unnest($8::text[]) l
             WHERE c.tsv_content @@ quote_literal(l)::tsquery) AS matched
FROM pool p
JOIN compliance_chunks c ON c.id = p.id
LEFT JOIN dense d ON d.id = p.id
LEFT JOIN sparse s ON s.id = p.id
"""


async def hybrid_search(
    pool: asyncpg.Pool,
    query: str,
    jurisdiction: str,
    entity_type: str,
    phase: str | None = None,
    limit: int | None = None,
) -> list[RetrievedChunk]:
    s = get_settings()
    embedder = get_embedder()
    [qvec] = await embedder.embed([query])
    j, entities, ph = filter_params(jurisdiction, entity_type, phase)

    async with pool.acquire() as conn:
        await idf_cache.ensure(conn)
        lexemes = await conn.fetchval(
            "SELECT coalesce(array_agg(lexeme), '{}') FROM unnest(to_tsvector('english', $1))", query
        )
        rows = await conn.fetch(
            HYBRID_SQL,
            np.asarray(qvec, dtype=np.float32),
            j, entities, ph, embedder.name,
            s.candidate_pool,
            build_or_tsquery(query),
            list(lexemes),
        )

    if not rows:
        return []

    max_sparse = max(r["sparse_score"] for r in rows) or 1.0
    results = []
    for r in rows:
        dense = max(0.0, float(r["dense_score"]))
        coverage = idf_coverage(list(lexemes), list(r["matched"]))
        sparse = (float(r["sparse_score"]) / max_sparse) * coverage
        results.append(
            RetrievedChunk(
                id=r["id"],
                content=r["content"],
                metadata=ChunkMetadata(**r["metadata"]),
                dense_score=round(dense, 4),
                sparse_score=round(sparse, 4),
                hybrid_score=round(s.dense_weight * dense + s.sparse_weight * sparse, 4),
            )
        )
    results.sort(key=lambda c: c.hybrid_score, reverse=True)
    return results[: (limit or s.rerank_candidates)]
