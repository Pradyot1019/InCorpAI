"""IncCorpAI API entrypoint.  Run:  uvicorn main:app --reload --port 8000"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.db import close_pool, init_pool
from app.core.embeddings import get_embedder
from app.generation.llm import get_llm
from app.retrieval.rerank import get_reranker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("inccorpai")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_pool()
    log.info("LLM=%s  embedder=%s  reranker=%s", get_llm().name, get_embedder().name,
             get_reranker().name)
    yield
    await close_pool()


app = FastAPI(
    title="IncCorpAI API",
    version="1.0.0",
    description="Metadata-filtered hybrid RAG for startup incorporation and compliance.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # credentials can't be combined with a wildcard origin
    allow_credentials="*" not in settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
