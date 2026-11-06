"""Filter resolution, message building and the offline responder (no DB needed)."""

import asyncio

from app.core.embeddings import HashEmbedder
from app.core.models import ChunkMetadata, QueryRequest, RetrievedChunk
from app.generation.llm import OfflineLLM, Usage
from app.generation.widgets import WidgetPart, WidgetStreamParser
from app.retrieval.hybrid import build_or_tsquery
from app.service import build_messages, resolve_filters


def req(q, j="IN", e="Pvt Ltd", **kw):
    return QueryRequest(query=q, jurisdiction=j, entity_type=e, **kw)


def test_filter_override_from_query():
    f = resolve_filters(req("When is the Delaware franchise tax due?"))
    assert f.jurisdiction == "US-DE" and f.entity_type == "C-Corp" and f.overridden


def test_filter_kept_when_no_mention():
    f = resolve_filters(req("What forms do I file after incorporation?"))
    assert (f.jurisdiction, f.entity_type, f.overridden) == ("IN", "Pvt Ltd", False)


def test_filter_autodetect_can_be_disabled():
    f = resolve_filters(req("Delaware question", auto_detect_filters=False))
    assert f.jurisdiction == "IN"


def test_entity_detected_within_jurisdiction():
    f = resolve_filters(req("How do I register an LLP?"))
    assert f.entity_type == "LLP"


def test_or_tsquery_sanitises():
    assert build_or_tsquery("What's SPICe+ Part-B?!") == "what | spice | part"


def test_messages_alternate_and_end_with_user():
    r = req("next", history=[
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "a"},
        {"role": "user", "content": "b"},
        {"role": "assistant", "content": "c"},
    ])
    msgs = build_messages(r, "CTX")
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "a\n\nb" and msgs[-1]["content"] == "CTX"


def test_hash_embedder_similarity_ordering():
    e = HashEmbedder(1536)
    a, b, c = asyncio.run(e.embed(["name reservation SPICe+ Part A",
                                   "reserve a company name in SPICe+",
                                   "Delaware franchise tax"]))
    def dot(x, y):
        return sum(i * j for i, j in zip(x, y, strict=False))
    assert dot(a, b) > dot(a, c)


def _chunk(i, path, text):
    return RetrievedChunk(
        id=str(i), content=f"[Doc] {path}\n\n{text}", hybrid_score=0.5,
        metadata=ChunkMetadata(jurisdiction="IN", entity_type="Pvt Ltd", entity_types=["Pvt Ltd"],
                               regulatory_body="MCA", compliance_phase="Incorporation",
                               source_document="d.md", document_title="Doc", section_path=[path],
                               chunk_index=i),
    )


def test_offline_llm_emits_valid_checklist_for_workflows():
    chunks = [_chunk(0, "Step 1 — Get DSC", "Every director must obtain a Class 3 DSC before filing."),
              _chunk(1, "Step 2 — Reserve name", "Part A reserves the proposed name for 20 days.")]

    async def collect():
        p, parts = WidgetStreamParser(), []
        async for d in OfflineLLM().stream(system="", messages=[], chunks=chunks,
                                           query="What are the steps to incorporate?", usage=Usage()):
            parts += p.feed(d)
        return parts + p.flush()

    widgets = [x for x in asyncio.run(collect()) if isinstance(x, WidgetPart)]
    assert widgets and [i["label"] for i in widgets[0].payload["items"]] == ["Get DSC", "Reserve name"]
