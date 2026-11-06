"""CLI: ingest a folder (or individual files) of regulatory documents.

    python ingest.py ../corpus              # ingest everything, skipping unchanged files
    python ingest.py ../corpus --force      # re-embed everything
    python ingest.py path/to/file.pdf       # needs path/to/file.pdf.meta.json sidecar
    python ingest.py ../corpus --prune      # also delete DB docs whose file no longer exists
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from app.core.db import close_pool, get_pool
from app.ingestion.loaders import MetadataError, load_path
from app.ingestion.pipeline import ingest_document

SUPPORTED = {".md", ".markdown", ".pdf", ".txt"}


def collect(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            files.extend(f for f in sorted(p.rglob("*")) if f.suffix.lower() in SUPPORTED
                         and not f.name.lower().startswith("readme"))
        elif p.suffix.lower() in SUPPORTED:
            files.append(p)
    return files


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--force", action="store_true", help="re-embed even if unchanged")
    ap.add_argument("--prune", action="store_true", help="remove documents not found on disk")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    pool = await get_pool()
    files = collect(args.paths)
    if not files:
        print("No supported files found.", file=sys.stderr)
        return 1

    failures = 0
    for f in files:
        try:
            body, meta, raw = load_path(f)
            res = await ingest_document(pool, f.name, body, meta, raw, force=args.force)
            print(f"  {res.status:<9} {res.chunks:>3} chunks  {f.name}")
        except MetadataError as e:
            failures += 1
            print(f"  SKIPPED  {e}", file=sys.stderr)

    if args.prune:
        names = [f.name for f in files]
        async with pool.acquire() as conn:
            deleted = await conn.fetch(
                "DELETE FROM documents WHERE NOT (source_document = ANY($1)) RETURNING source_document",
                names,
            )
        for row in deleted:
            print(f"  pruned   {row['source_document']}")

    await close_pool()
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
