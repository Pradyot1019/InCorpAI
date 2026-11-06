"""Pydantic v2 data contracts shared by the API, retrieval and generation layers.

These are the API's public contract — the frontend (Lovable or the bundled reference UI)
mirrors them in `frontend/src/lib/types.ts`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Chunk metadata (stored as JSONB)
# ---------------------------------------------------------------------------


class ChunkMetadata(BaseModel):
    jurisdiction: str = Field(..., examples=["IN", "US-DE", "EU"])
    entity_type: str = Field(..., description="Display value, e.g. 'Pvt Ltd' or 'Pvt Ltd, LLP'")
    entity_types: list[str] = Field(..., description="Normalised list used for filtering")
    regulatory_body: str = Field(..., examples=["MCA", "SEC", "DPDPA", "IRS", "DPIIT"])
    compliance_phase: str = Field(..., examples=["Pre-Incorporation", "Incorporation"])
    source_document: str
    document_title: str
    source_url: str | None = None
    clause_id: str | None = Field(None, examples=["SPICe+ Part B Section 3"])
    section_path: list[str] = Field(default_factory=list)
    chunk_index: int = 0
    has_table: bool = False
    last_reviewed: str | None = None


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20_000)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000,
                       description="The user's compliance or incorporation question")
    jurisdiction: str = Field(..., description="Jurisdiction code e.g. IN, US-DE, EU")
    entity_type: str = Field(..., description="Entity type e.g. Pvt Ltd, C-Corp, LLP")
    sector: str | None = Field("Tech", description="Industry sector for targeted context")
    compliance_phase: str | None = Field(None, description="Optional phase filter")
    history: list[ChatTurn] = Field(default_factory=list, max_length=40)
    auto_detect_filters: bool = Field(
        True, description="Let explicit mentions in the query (e.g. 'Delaware') override UI filters"
    )

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        return v.strip()


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=4000)
    jurisdiction: str
    entity_type: str
    compliance_phase: str | None = None
    top_k: int = Field(5, ge=1, le=20)
    rerank: bool = True


# ---------------------------------------------------------------------------
# Retrieval results
# ---------------------------------------------------------------------------


class RetrievedChunk(BaseModel):
    id: str
    content: str
    metadata: ChunkMetadata
    dense_score: float = 0.0
    sparse_score: float = 0.0
    hybrid_score: float = 0.0
    rerank_score: float | None = None

    @property
    def final_score(self) -> float:
        return self.rerank_score if self.rerank_score is not None else self.hybrid_score


class Source(BaseModel):
    """What the frontend renders as a citation card. `index` matches [n] markers in the answer."""

    index: int
    chunk_id: str
    document_title: str
    source_document: str
    source_url: str | None
    clause_id: str | None
    section_path: list[str]
    jurisdiction: str
    entity_type: str
    regulatory_body: str
    compliance_phase: str
    snippet: str
    content: str
    score: float


class AppliedFilters(BaseModel):
    jurisdiction: str
    entity_type: str
    compliance_phase: str | None = None
    overridden: bool = False
    note: str | None = None


# ---------------------------------------------------------------------------
# Checklist widget payload
# ---------------------------------------------------------------------------


class ChecklistItem(BaseModel):
    id: str
    label: str
    sublines: list[str] = Field(default_factory=list)
    category: str
    checked: bool = False
    source_refs: list[int] = Field(default_factory=list,
                                   description="Citation indices backing this step")


class ChecklistPayload(BaseModel):
    header_title: str
    categories: list[str]
    items: list[ChecklistItem]

    @field_validator("categories")
    @classmethod
    def non_empty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("categories must not be empty")
        return v

    def normalised(self) -> ChecklistPayload:
        """Ensure every item category is listed and ids are unique."""
        cats = list(dict.fromkeys(self.categories + [i.category for i in self.items]))
        seen: set[str] = set()
        items = []
        for n, item in enumerate(self.items):
            iid = item.id if item.id and item.id not in seen else f"step-{n + 1}"
            seen.add(iid)
            items.append(item.model_copy(update={"id": iid}))
        return ChecklistPayload(header_title=self.header_title, categories=cats, items=items)


# ---------------------------------------------------------------------------
# Misc responses
# ---------------------------------------------------------------------------


class DocumentInfo(BaseModel):
    id: str
    title: str
    source_document: str
    source_url: str | None
    jurisdiction: str | None
    entity_type: str | None
    regulatory_body: str | None
    compliance_phase: str | None
    chunk_count: int
    updated_at: str


class IngestResult(BaseModel):
    source_document: str
    status: Literal["ingested", "unchanged", "replaced"]
    chunks: int
