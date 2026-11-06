"""asyncpg connection pool with pgvector codec registration."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import asyncpg
from pgvector.asyncpg import register_vector

from app.core.config import get_settings

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schema.sql"

_pool: asyncpg.Pool | None = None


async def _init_conn(conn: asyncpg.Connection) -> None:
    await register_vector(conn)
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.execute(f"SET hnsw.ef_search = {int(get_settings().hnsw_ef_search)}")


async def apply_schema(dsn: str | None = None) -> None:
    """Run schema.sql (idempotent). Uses a plain connection: the vector type may not exist yet."""
    conn = await asyncpg.connect(dsn or get_settings().database_url)
    try:
        await conn.execute(SCHEMA_PATH.read_text())
    finally:
        await conn.close()


async def init_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        await apply_schema()
        _pool = await asyncpg.create_pool(
            get_settings().database_url, min_size=1, max_size=10, init=_init_conn
        )
        log.info("Database pool ready")
    return _pool


async def get_pool() -> asyncpg.Pool:
    return _pool or await init_pool()


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
