"""Ingestion pipeline: load -> chunk -> embed -> upsert (idempotent by checksum)."""

from __future__ import annotations

import hashlib
import logging

import asyncpg

from app.core.config import get_settings
from app.core.embeddings import get_embedder
from app.core.models import ChunkMetadata, IngestResult
from app.ingestion.chunker import chunk_markdown

log = logging.getLogger(__name__)

DOC_META_KEYS = (
    "jurisdiction", "entity_type", "entity_types", "regulatory_body",
    "compliance_phase", "last_reviewed", "sector",
)


def build_chunk_records(source_document: str, body: str, doc_meta: dict) -> list[dict]:
    s = get_settings()
    chunks = chunk_markdown(body, s.chunk_max_tokens, s.chunk_overlap_tokens)
    records = []
    for c in chunks:
        # Heading attributes override document-level metadata for their subtree
        phase = c.attrs.get("phase", doc_meta["compliance_phase"])
        body_ = c.attrs.get("body", doc_meta["regulatory_body"])
        clause = c.attrs.get("clause") or (c.path[-1] if c.path else None)
        meta = ChunkMetadata(
            jurisdiction=doc_meta["jurisdiction"],
            entity_type=doc_meta["entity_type"],
            entity_types=doc_meta["entity_types"],
            regulatory_body=body_,
            compliance_phase=phase,
            source_document=source_document,
            document_title=doc_meta["title"],
            source_url=doc_meta.get("source_url"),
            clause_id=clause,
            section_path=c.path,
            chunk_index=c.index,
            has_table=c.has_table,
            last_reviewed=str(doc_meta["last_reviewed"]) if doc_meta.get("last_reviewed") else None,
        )
        text = c.embedded_text(doc_meta["title"])
        records.append(
            {
                "content": text,
                "header_path": c.path,
                "content_hash": hashlib.sha256(text.encode()).hexdigest(),
                "metadata": meta.model_dump(),
                "chunk_index": c.index,
            }
        )
    return records


async def ingest_document(
    pool: asyncpg.Pool,
    source_document: str,
    body: str,
    doc_meta: dict,
    raw: bytes,
    force: bool = False,
) -> IngestResult:
    checksum = hashlib.sha256(raw).hexdigest()
    embedder = get_embedder()

    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id, checksum FROM documents WHERE source_document = $1", source_document
        )
        if existing and existing["checksum"] == checksum and not force:
            # also re-embed if the embedding model changed
            model = await conn.fetchval(
                "SELECT embedding_model FROM compliance_chunks WHERE document_id = $1 LIMIT 1",
                existing["id"],
            )
            if model == embedder.name:
                n = await conn.fetchval(
                    "SELECT count(*) FROM compliance_chunks WHERE document_id = $1", existing["id"]
                )
                return IngestResult(source_document=source_document, status="unchanged", chunks=n)

    records = build_chunk_records(source_document, body, doc_meta)
    vectors = await embedder.embed([r["content"] for r in records])

    doc_level = {k: doc_meta[k] for k in DOC_META_KEYS if k in doc_meta}
    async with pool.acquire() as conn, conn.transaction():
        doc_id = await conn.fetchval(
            """
            INSERT INTO documents (source_document, title, source_url, checksum, metadata, chunk_count)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (source_document) DO UPDATE
               SET title = EXCLUDED.title, source_url = EXCLUDED.source_url,
                   checksum = EXCLUDED.checksum, metadata = EXCLUDED.metadata,
                   chunk_count = EXCLUDED.chunk_count, updated_at = NOW()
            RETURNING id
            """,
            source_document, doc_meta["title"], doc_meta.get("source_url"), checksum,
            doc_level, len(records),
        )
        await conn.execute("DELETE FROM compliance_chunks WHERE document_id = $1", doc_id)
        await conn.executemany(
            """
            INSERT INTO compliance_chunks
                (document_id, chunk_index, content, header_path, header_text, content_hash,
                 embedding, embedding_model, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            [
                (doc_id, r["chunk_index"], r["content"], r["header_path"],
                 " > ".join(r["header_path"]), r["content_hash"],
                 vec, embedder.name, r["metadata"])
                for r, vec in zip(records, vectors, strict=False)
            ],
        )
    from app.retrieval.hybrid import idf_cache

    idf_cache.invalidate()
    status = "replaced" if existing else "ingested"
    log.info("%s %s (%d chunks)", status, source_document, len(records))
    return IngestResult(source_document=source_document, status=status, chunks=len(records))
