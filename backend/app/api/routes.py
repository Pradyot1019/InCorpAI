"""HTTP API. All routes are mounted under /api."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from app.core.config import get_settings
from app.core.db import get_pool
from app.core.embeddings import get_embedder
from app.core.models import (
    DocumentInfo,
    IngestResult,
    QueryRequest,
    SearchRequest,
    Source,
)
from app.core.taxonomy import (
    COMPLIANCE_PHASES,
    ENTITY_TYPE_LABELS,
    JURISDICTIONS,
    SUGGESTED_PROMPTS,
)
from app.generation.llm import get_llm
from app.ingestion.loaders import MetadataError, load_bytes
from app.ingestion.pipeline import ingest_document
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import get_reranker, safe_rerank
from app.service import run_chat, to_sources

router = APIRouter(prefix="/api")


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    token = get_settings().admin_token
    if token and x_admin_token != token:
        raise HTTPException(status_code=401, detail="A valid X-Admin-Token header is required.")


@router.get("/health")
async def health():
    pool = await get_pool()
    async with pool.acquire() as conn:
        docs = await conn.fetchval("SELECT count(*) FROM documents")
        chunks = await conn.fetchval("SELECT count(*) FROM compliance_chunks")
    return {
        "status": "ok",
        "documents": docs,
        "chunks": chunks,
        "llm": get_llm().name,
        "embedder": get_embedder().name,
        "reranker": get_reranker().name,
        "offline": get_llm().name == "offline-extractive",
    }


@router.get("/taxonomy")
async def taxonomy():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT metadata->>'jurisdiction' AS j, count(*) AS n FROM documents GROUP BY 1"
        )
    counts = {r["j"]: r["n"] for r in rows}
    return {
        "jurisdictions": [
            {
                **j,
                "entity_types": [{"value": e, "label": ENTITY_TYPE_LABELS.get(e, e)}
                                 for e in j["entity_types"]],
                "document_count": counts.get(j["code"], 0),
                "suggested_prompts": SUGGESTED_PROMPTS.get(j["code"], []),
            }
            for j in JURISDICTIONS
        ],
        "compliance_phases": COMPLIANCE_PHASES,
    }


@router.post("/chat")
async def chat(req: QueryRequest):
    """Server-Sent Events stream. Events: filters, status, sources, token, widget, done, error."""
    pool = await get_pool()

    async def events():
        async for ev in run_chat(pool, req):
            yield {"event": ev["event"], "data": json.dumps(ev["data"], ensure_ascii=False)}

    return EventSourceResponse(events(), ping=15, headers={"X-Accel-Buffering": "no"})


@router.post("/search", response_model=list[Source])
async def search(req: SearchRequest):
    """Retrieval only (no LLM). Useful for debugging relevance and building evals."""
    pool = await get_pool()
    candidates = await hybrid_search(pool, req.query, req.jurisdiction, req.entity_type,
                                     req.compliance_phase)
    if req.rerank:
        top, _ = await safe_rerank(req.query, candidates, req.top_k)
    else:
        top = candidates[: req.top_k]
    return to_sources(top)


@router.get("/documents", response_model=list[DocumentInfo])
async def list_documents(jurisdiction: str | None = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id::text, title, source_document, source_url, metadata, chunk_count, updated_at
               FROM documents
               WHERE ($1::text IS NULL OR metadata->>'jurisdiction' = $1)
               ORDER BY metadata->>'jurisdiction', title""",
            jurisdiction,
        )
    return [
        DocumentInfo(
            id=r["id"], title=r["title"], source_document=r["source_document"],
            source_url=r["source_url"], jurisdiction=r["metadata"].get("jurisdiction"),
            entity_type=r["metadata"].get("entity_type"),
            regulatory_body=r["metadata"].get("regulatory_body"),
            compliance_phase=r["metadata"].get("compliance_phase"),
            chunk_count=r["chunk_count"], updated_at=r["updated_at"].isoformat(),
        )
        for r in rows
    ]


@router.post("/documents", response_model=IngestResult, dependencies=[Depends(require_admin)])
async def upload_document(
    file: UploadFile = File(...),
    metadata: str = Form("{}", description="JSON: jurisdiction, entity_type, regulatory_body, "
                                           "compliance_phase, title?, source_url?"),
    force: bool = Form(False),
):
    try:
        meta = json.loads(metadata)
        raw = await file.read()
        if len(raw) > 25 * 1024 * 1024:
            raise HTTPException(413, "File exceeds the 25 MB limit.")
        body, doc_meta = load_bytes(file.filename or "upload.md", raw, meta)
    except (json.JSONDecodeError, MetadataError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    pool = await get_pool()
    return await ingest_document(pool, file.filename or "upload.md", body, doc_meta, raw, force)


@router.delete("/documents/{doc_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_document(doc_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.fetchval("DELETE FROM documents WHERE id = $1::uuid RETURNING id", doc_id)
    if not deleted:
        raise HTTPException(404, "Document not found.")


@router.get("/chunks/{chunk_id}")
async def get_chunk(chunk_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id::text, content, metadata FROM compliance_chunks WHERE id = $1::uuid", chunk_id
        )
    if not row:
        raise HTTPException(404, "Chunk not found.")
    return {"id": row["id"], "content": row["content"].split("\n\n", 1)[-1], "metadata": row["metadata"]}
