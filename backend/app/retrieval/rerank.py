"""Cross-encoder reranking: Cohere Rerank API, local BGE cross-encoder, or passthrough."""

from __future__ import annotations

import asyncio
import logging
import math
from typing import Protocol

from app.core.config import get_settings
from app.core.models import RetrievedChunk

log = logging.getLogger(__name__)


def _strip_prefix(text: str) -> str:
    # keep the breadcrumb prefix (it helps rerankers); just bound the length
    return text[:4000]


class Reranker(Protocol):
    name: str

    async def rerank(self, query: str, chunks: list[RetrievedChunk], top_n: int) -> list[RetrievedChunk]: ...


class PassthroughReranker:
    name = "none"

    async def rerank(self, query, chunks, top_n):
        return sorted(chunks, key=lambda c: c.hybrid_score, reverse=True)[:top_n]


class CohereReranker:
    def __init__(self, api_key: str, model: str):
        import cohere

        self._client = cohere.AsyncClientV2(api_key=api_key)
        self.name = f"cohere:{model}"
        self._model = model

    async def rerank(self, query, chunks, top_n):
        if not chunks:
            return []
        resp = await self._client.rerank(
            model=self._model,
            query=query,
            documents=[_strip_prefix(c.content) for c in chunks],
            top_n=min(top_n, len(chunks)),
        )
        return [
            chunks[r.index].model_copy(update={"rerank_score": round(r.relevance_score, 4)})
            for r in resp.results
        ]


class BGEReranker:
    def __init__(self, model: str):
        from sentence_transformers import CrossEncoder  # optional dependency

        self._model = CrossEncoder(model, max_length=512)
        self.name = f"bge:{model}"

    async def rerank(self, query, chunks, top_n):
        if not chunks:
            return []
        pairs = [(query, _strip_prefix(c.content)) for c in chunks]
        logits = await asyncio.to_thread(self._model.predict, pairs)
        scored = [
            c.model_copy(update={"rerank_score": round(1 / (1 + math.exp(-float(s))), 4)})
            for c, s in zip(chunks, logits, strict=False)
        ]
        scored.sort(key=lambda c: c.rerank_score, reverse=True)
        return scored[:top_n]


_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    global _reranker
    if _reranker is not None:
        return _reranker
    s = get_settings()
    provider = s.reranker_provider
    if provider in ("auto", "cohere") and s.cohere_api_key:
        _reranker = CohereReranker(s.cohere_api_key, s.cohere_rerank_model)
    elif provider in ("auto", "bge"):
        try:
            _reranker = BGEReranker(s.bge_rerank_model)
        except ImportError as e:
            if provider == "bge":
                raise RuntimeError("RERANKER_PROVIDER=bge needs: pip install '.[local-rerank]'") from e
            _reranker = PassthroughReranker()
    else:
        _reranker = PassthroughReranker()
    log.info("Reranker: %s", _reranker.name)
    return _reranker


async def safe_rerank(query: str, chunks: list[RetrievedChunk], top_n: int) -> tuple[list[RetrievedChunk], str]:
    """Rerank, degrading to hybrid order if the reranker errors (e.g. API outage)."""
    reranker = get_reranker()
    try:
        return await reranker.rerank(query, chunks, top_n), reranker.name
    except Exception as e:
        log.warning("Reranker %s failed (%s); falling back to hybrid order", reranker.name, e)
        return await PassthroughReranker().rerank(query, chunks, top_n), "none (fallback)"
