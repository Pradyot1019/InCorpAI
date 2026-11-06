"""LLM providers that stream text deltas.

- AnthropicLLM: Claude via the native `anthropic` SDK (async streaming, prompt caching on
  the system prompt).
- OfflineLLM: an extractive responder used when no ANTHROPIC_API_KEY is configured. It
  quotes the most query-relevant sentences from the retrieved chunks with citations and
  builds a checklist for workflow questions, so the whole product (including the widget)
  can be developed and demoed with zero API keys.
"""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import get_settings
from app.core.models import RetrievedChunk


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    extra: dict = field(default_factory=dict)


class LLM(Protocol):
    name: str

    def stream(self, *, system: str, messages: list[dict], chunks: list[RetrievedChunk],
               query: str, usage: Usage) -> AsyncIterator[str]:
        """Yield text deltas; fill the per-request `usage` object when finished."""
        ...


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class AnthropicLLM:
    def __init__(self, api_key: str, model: str, max_tokens: int):
        import anthropic

        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self.name = model
        self._max_tokens = max_tokens

    async def stream(self, *, system, messages, chunks, query, usage):
        async with self._client.messages.stream(
            model=self.name,
            max_tokens=self._max_tokens,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text
            final = await stream.get_final_message()
        u = final.usage
        usage.input_tokens = u.input_tokens
        usage.output_tokens = u.output_tokens
        usage.cache_read_tokens = getattr(u, "cache_read_input_tokens", 0) or 0
        usage.extra["stop_reason"] = final.stop_reason


# ---------------------------------------------------------------------------
# Offline extractive responder
# ---------------------------------------------------------------------------

_WORKFLOW = re.compile(
    r"\b(how (do|can|should) i|steps?|process|procedure|workflow|checklist|register|"
    r"incorporat\w*|set ?up|form(ing)?|file|filing|apply|what do i need)\b", re.IGNORECASE
)
_SPLIT = re.compile(r"(?<=[.;])\s+(?=[A-Z])|\n+")
_WORD = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of to and or in on for is are be by with what how do i my can should "
    "when must does need".split()
)
_STEP_PREFIX = re.compile(r"^(step\s*\d+\s*[—–-]\s*)", re.IGNORECASE)


def _terms(text: str) -> set[str]:
    return {w[:6] for w in _WORD.findall(text.lower()) if w not in _STOP and len(w) > 2}


def _clean_line(line: str) -> str:
    line = line.strip().lstrip("-*0123456789.) ").strip()
    if line.startswith("|"):
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= set("-: ") for c in cells):
            return ""
        return " — ".join(c for c in cells if c)
    return re.sub(r"\*\*(.+?)\*\*", r"\1", line)


def _sentences(chunk: RetrievedChunk) -> list[str]:
    """Candidate quotes: table rows whole (header + separator dropped), prose by sentence."""
    body = chunk.content.split("\n\n", 1)[-1]  # drop breadcrumb prefix
    lines = body.splitlines()
    out: list[str] = []
    prose: list[str] = []

    def flush_prose() -> None:
        if prose:
            out.extend(_clean_line(x) for x in _SPLIT.split(" ".join(prose)))
            prose.clear()

    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith("|"):
            flush_prose()
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if re.match(r"^\|[\s:|-]+\|$", nxt):  # header row
                continue
            out.append(_clean_line(st))
        elif re.match(r"^([-*+]|\d+[.)])\s", st):
            flush_prose()
            out.append(_clean_line(st))
        elif st:
            prose.append(st)
        else:
            flush_prose()
    flush_prose()
    return [r for r in out if len(r) > 25]


def _best(chunk: RetrievedChunk, q: set[str], n: int) -> list[str]:
    sents = _sentences(chunk)
    scored = sorted(sents, key=lambda s: len(q & _terms(s)), reverse=True)
    picked = scored[:n]
    return sorted(picked, key=sents.index)  # keep document order


class OfflineLLM:
    name = "offline-extractive"

    def compose(self, query: str, chunks: list[RetrievedChunk]) -> str:
        q = _terms(query)
        m0 = chunks[0].metadata
        lines = [f"Here is what the {m0.jurisdiction} sources for **{m0.entity_type}** say:\n"]
        for i, c in enumerate(chunks[:4], start=1):
            label = _STEP_PREFIX.sub("", c.metadata.section_path[-1] if c.metadata.section_path
                                     else c.metadata.document_title)
            for s in _best(c, q, 2 if i == 1 else 1):
                lines.append(f"- **{label}:** {s} [{i}]")
        lines.append(
            "\n*Offline mode: this is an extractive summary of the retrieved sources. Set "
            "`ANTHROPIC_API_KEY` for synthesized answers. Fees and deadlines change by "
            "notification, so confirm on the official portal.*"
        )
        text = "\n".join(lines)

        if _WORKFLOW.search(query):
            ordered = sorted(enumerate(chunks, start=1),
                             key=lambda p: (p[1].metadata.source_document, p[1].metadata.chunk_index))
            items, cats = [], []
            for n, (idx, c) in enumerate(ordered, start=1):
                m = c.metadata
                cat = m.compliance_phase
                cats.append(cat)
                label = _STEP_PREFIX.sub("", m.section_path[-1] if m.section_path else m.document_title)
                items.append({
                    "id": f"step-{n}",
                    "label": label[:80],
                    "sublines": [s[:160] for s in _best(c, q, 2)],
                    "category": cat,
                    "source_refs": [idx],
                })
            payload = {
                "header_title": f"{m0.document_title.split(' via ')[0]} checklist"[:80],
                "categories": list(dict.fromkeys(cats)),
                "items": items,
            }
            text += ('\n\n<TemplateWidget templateName="checklist">\n'
                     + json.dumps(payload, ensure_ascii=False) + "\n</TemplateWidget>")
        return text

    async def stream(self, *, system, messages, chunks, query, usage):
        text = self.compose(query, chunks)
        usage.output_tokens = len(text.split())
        # stream in small slices to exercise the same SSE path as a real model
        for i in range(0, len(text), 12):
            yield text[i : i + 12]
            await asyncio.sleep(0.006)


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        s = get_settings()
        provider = s.llm_provider
        if provider == "auto":
            provider = "anthropic" if s.anthropic_api_key else "offline"
        if provider == "anthropic":
            if not s.anthropic_api_key:
                raise RuntimeError("LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set")
            _llm = AnthropicLLM(s.anthropic_api_key, s.anthropic_model, s.llm_max_tokens)
        else:
            _llm = OfflineLLM()
    return _llm
