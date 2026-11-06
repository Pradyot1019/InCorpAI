"""RAG orchestration: filters -> hybrid search -> rerank -> reject-or-generate -> events.

`run_chat` yields plain dicts {"event": str, "data": dict}. The API layer serialises them
as Server-Sent Events. Keeping the pipeline transport-agnostic makes it easy to test and to
reuse (e.g. from a websocket or a batch eval script).
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator

import asyncpg

from app.core.config import get_settings
from app.core.models import AppliedFilters, QueryRequest, RetrievedChunk, Source
from app.core.taxonomy import (
    JURISDICTIONS,
    detect_entity_type,
    detect_jurisdiction,
    entity_valid_for,
)
from app.generation.llm import Usage, get_llm
from app.generation.prompts import REJECTION_MESSAGE, SYSTEM_PROMPT, build_user_turn
from app.generation.widgets import TextPart, WidgetStreamParser
from app.retrieval.hybrid import hybrid_search
from app.retrieval.rerank import safe_rerank

log = logging.getLogger(__name__)

# keep references so fire-and-forget logging tasks aren't garbage-collected mid-flight
_background: set[asyncio.Task] = set()


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


def resolve_filters(req: QueryRequest) -> AppliedFilters:
    jurisdiction, entity = req.jurisdiction, req.entity_type
    notes = []
    if req.auto_detect_filters:
        dj = detect_jurisdiction(req.query)
        de = detect_entity_type(req.query)
        if dj and dj != jurisdiction:
            notes.append(f"Your question mentions {dj}, so I searched {dj} sources.")
            jurisdiction = dj
        if de and de != entity and entity_valid_for(jurisdiction, de):
            notes.append(f"Searching {de} guidance as mentioned in your question.")
            entity = de
    if not entity_valid_for(jurisdiction, entity) and entity != "Any":
        fallback = next(j["entity_types"][0] for j in JURISDICTIONS if j["code"] == jurisdiction) \
            if any(j["code"] == jurisdiction for j in JURISDICTIONS) else entity
        if fallback != entity:
            notes.append(f"{entity} isn't an entity type in {jurisdiction}; using {fallback}.")
            entity = fallback
    return AppliedFilters(
        jurisdiction=jurisdiction,
        entity_type=entity,
        compliance_phase=req.compliance_phase,
        overridden=bool(notes),
        note=" ".join(notes) or None,
    )


def to_sources(chunks: list[RetrievedChunk]) -> list[Source]:
    out = []
    for i, c in enumerate(chunks, start=1):
        m = c.metadata
        body = c.content.split("\n\n", 1)[-1]
        out.append(
            Source(
                index=i, chunk_id=c.id, document_title=m.document_title,
                source_document=m.source_document, source_url=m.source_url,
                clause_id=m.clause_id, section_path=m.section_path,
                jurisdiction=m.jurisdiction, entity_type=m.entity_type,
                regulatory_body=m.regulatory_body, compliance_phase=m.compliance_phase,
                snippet=(body[:280] + "…") if len(body) > 280 else body,
                content=body, score=round(c.final_score, 4),
            )
        )
    return out


def build_messages(req: QueryRequest, user_turn: str) -> list[dict]:
    """Last N turns, coerced to strict user/assistant alternation starting with user."""
    turns = req.history[-get_settings().history_turns :]
    msgs: list[dict] = []
    for t in turns:
        if not msgs and t.role != "user":
            continue
        if msgs and msgs[-1]["role"] == t.role:
            msgs[-1]["content"] += "\n\n" + t.content
        else:
            msgs.append({"role": t.role, "content": t.content})
    if msgs and msgs[-1]["role"] == "user":
        msgs.pop()  # the new user turn replaces a dangling one
    msgs.append({"role": "user", "content": user_turn})
    return msgs


async def _log_query(pool, req, filters, chunks, top, rejected, latency, model) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO query_log (query, filters, retrieved_ids, top_score, rejected,
                                          latency_ms, llm_model)
                   VALUES ($1, $2, $3::uuid[], $4, $5, $6, $7)""",
                req.query, filters.model_dump(), [c.id for c in chunks], top, rejected,
                latency, model,
            )
    except Exception as e:
        log.warning("query_log insert failed: %s", e)


async def run_chat(pool: asyncpg.Pool, req: QueryRequest) -> AsyncIterator[dict]:
    s = get_settings()
    t0 = time.perf_counter()
    filters = resolve_filters(req)
    yield {"event": "filters", "data": filters.model_dump()}

    yield {"event": "status", "data": {"stage": "retrieving", "label": "Searching regulations"}}
    candidates = await hybrid_search(
        pool, req.query, filters.jurisdiction, filters.entity_type, filters.compliance_phase
    )
    best = candidates[0].hybrid_score if candidates else 0.0
    llm = get_llm()

    if best < s.min_relevance:
        scope = f"{filters.jurisdiction}, {filters.entity_type}"
        msg = REJECTION_MESSAGE.format(scope=scope)
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "token", "data": {"text": msg}}
        latency = int((time.perf_counter() - t0) * 1000)
        yield {"event": "done", "data": {
            "rejected": True, "reason": "below_relevance_threshold", "top_score": best,
            "latency_ms": latency, "model": None, "reranker": None,
            "candidates": len(candidates), "usage": None,
        }}
        _spawn(_log_query(pool, req, filters, [], best, True, latency, None))
        return

    yield {"event": "status", "data": {"stage": "reranking", "label": "Ranking the most relevant clauses"}}
    top, reranker_name = await safe_rerank(req.query, candidates, s.final_top_k)
    sources = to_sources(top)
    yield {"event": "sources", "data": {"sources": [x.model_dump() for x in sources]}}

    yield {"event": "status", "data": {"stage": "generating", "label": "Drafting the answer"}}
    usage = Usage()
    parser = WidgetStreamParser()
    messages = build_messages(req, build_user_turn(req.query, filters, req.sector, top))
    try:
        async for delta in llm.stream(system=SYSTEM_PROMPT, messages=messages, chunks=top,
                                      query=req.query, usage=usage):
            for part in parser.feed(delta):
                yield _part_event(part)
        for part in parser.flush():
            yield _part_event(part)
    except Exception as e:
        log.exception("LLM stream failed")
        yield {"event": "error", "data": {"message": f"The language model request failed: {e}"}}
        return

    latency = int((time.perf_counter() - t0) * 1000)
    yield {"event": "done", "data": {
        "rejected": False, "top_score": best, "latency_ms": latency, "model": llm.name,
        "reranker": reranker_name, "candidates": len(candidates),
        "usage": {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
                  "cache_read_tokens": usage.cache_read_tokens},
    }}
    _spawn(_log_query(pool, req, filters, top, best, False, latency, llm.name))


def _part_event(part) -> dict:
    if isinstance(part, TextPart):
        return {"event": "token", "data": {"text": part.text}}
    return {"event": "widget", "data": {"template": part.template, "payload": part.payload}}
