"""Embedding providers.

- OpenAIEmbedder: text-embedding-3-small (1536-d), batched, async.
- HashEmbedder: deterministic feature-hashing embedder for offline dev / CI. It needs no
  network or model download, so the full pipeline runs with zero API keys. Quality is
  lexical-only, so use OpenAI (or another real model) in production.

Switching providers requires re-ingesting: the model name is stored per chunk and the
retriever refuses to mix models.
"""

from __future__ import annotations

import hashlib
import itertools
import math
import re
from collections import Counter
from typing import Protocol

import numpy as np

from app.core.config import get_settings


class Embedder(Protocol):
    name: str
    dim: int

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


# ---------------------------------------------------------------------------
# Offline hash embedder
# ---------------------------------------------------------------------------

_TOKEN = re.compile(r"[a-z0-9][a-z0-9+\-]*")
_STOP = frozenset(
    ["a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "to", "was", "were", "will", "with", "this", "these", "those", "i", "we", "you", "our", "your", "my", "me", "what", "which", "how", "do", "does", "can", "should", "must", "may", "also", "any", "all", "not", "if", "then", "than", "into", "about"]
)
_SUFFIXES = ("ations", "ation", "ments", "ment", "ings", "ing", "ies", "ed", "es", "s")


def _stem(tok: str) -> str:
    for suf in _SUFFIXES:
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            return tok[: -len(suf)]
    return tok


def _features(text: str) -> Counter:
    toks = [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in _STOP]
    feats: Counter = Counter(toks)
    feats.update(f"{a}_{b}" for a, b in itertools.pairwise(toks))
    # character trigrams of each token help with form codes like inc-20a / spice+
    for t in set(toks):
        if len(t) >= 5:
            padded = f"#{t}#"
            feats.update(f"c:{padded[i:i + 3]}" for i in range(len(padded) - 2))
    return feats


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim
        self.name = f"hash-v1-{dim}"

    def _one(self, text: str) -> list[float]:
        vec = np.zeros(self.dim, dtype=np.float32)
        for feat, count in _features(text).items():
            h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            weight = (0.35 if feat.startswith("c:") else 1.0) * (1 + math.log(count))
            vec[idx] += sign * weight
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec /= norm
        return vec.tolist()

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]


# ---------------------------------------------------------------------------
# OpenAI
# ---------------------------------------------------------------------------


class OpenAIEmbedder:
    BATCH = 96

    def __init__(self, api_key: str, model: str, dim: int):
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self.name = model
        self.dim = dim

    async def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.BATCH):
            batch = [t.replace("\n", " ")[:24_000] for t in texts[i : i + self.BATCH]]
            resp = await self._client.embeddings.create(
                input=batch, model=self.name, dimensions=self.dim
            )
            out.extend(d.embedding for d in sorted(resp.data, key=lambda d: d.index))
        return out


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        s = get_settings()
        provider = s.embedding_provider
        if provider == "auto":
            provider = "openai" if s.openai_api_key else "hash"
        if provider == "openai":
            if not s.openai_api_key:
                raise RuntimeError("EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set")
            _embedder = OpenAIEmbedder(s.openai_api_key, s.embedding_model, s.embedding_dim)
        else:
            _embedder = HashEmbedder(s.embedding_dim)
    return _embedder
