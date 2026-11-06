"""Application settings, loaded from environment / .env."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Infra -----------------------------------------------------------------
    database_url: str = "postgresql://inccorp:inccorp@localhost:5432/inccorp"
    cors_origins: list[str] = Field(default_factory=lambda: ["*"])
    admin_token: str | None = None  # if set, required as X-Admin-Token for ingest/delete

    # --- Embeddings ------------------------------------------------------------
    # "auto" -> openai if OPENAI_API_KEY is set, otherwise the offline hash embedder.
    embedding_provider: Literal["auto", "openai", "hash"] = "auto"
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    openai_api_key: str | None = None

    # --- Reranking -------------------------------------------------------------
    # "auto" -> cohere if COHERE_API_KEY, else local bge if installed, else score passthrough.
    reranker_provider: Literal["auto", "cohere", "bge", "none"] = "auto"
    cohere_api_key: str | None = None
    cohere_rerank_model: str = "rerank-v3.5"
    bge_rerank_model: str = "BAAI/bge-reranker-large"

    # --- LLM -------------------------------------------------------------------
    # "auto" -> anthropic if ANTHROPIC_API_KEY, otherwise the extractive offline responder.
    llm_provider: Literal["auto", "anthropic", "offline"] = "auto"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5-5"
    llm_max_tokens: int = 2048
    history_turns: int = 6  # previous user/assistant messages forwarded to the LLM

    # --- Retrieval -------------------------------------------------------------
    dense_weight: float = 0.7
    sparse_weight: float = 0.3
    candidate_pool: int = 50     # per-retriever pool before fusion
    rerank_candidates: int = 20  # fused top-N passed to reranker
    final_top_k: int = 5         # chunks passed to the LLM
    # Strict negative rejection: if the best fused score is below this, refuse without calling LLM.
    min_relevance: float = 0.18
    hnsw_ef_search: int = 80

    # --- Ingestion -------------------------------------------------------------
    chunk_max_tokens: int = 450
    chunk_overlap_tokens: int = 60


@lru_cache
def get_settings() -> Settings:
    return Settings()
