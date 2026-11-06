"""File loaders: Markdown (with YAML front-matter), plain text, and PDF.

Every loader returns (markdown_text, document_metadata). PDFs are converted to
pseudo-markdown so they go through the same structure-aware chunker.

PDF / TXT metadata comes from a sidecar file `<name>.meta.json` (or is passed explicitly).
"""

from __future__ import annotations

import io
import json
import re
from pathlib import Path

import frontmatter

REQUIRED_KEYS = ("jurisdiction", "entity_type", "regulatory_body", "compliance_phase")

_NUMBERED_HEADING = re.compile(r"^(\d+(\.\d+){0,3})\.?\s+([A-Z][^.]{2,90})$")
_PART_HEADING = re.compile(r"^(PART|CHAPTER|SCHEDULE|SECTION|ARTICLE|RULE)\b.{0,90}$", re.IGNORECASE)


class MetadataError(ValueError):
    pass


def validate_doc_meta(meta: dict, source: str) -> dict:
    missing = [k for k in REQUIRED_KEYS if not meta.get(k)]
    if missing:
        raise MetadataError(f"{source}: missing required metadata keys {missing}")
    for k, v in list(meta.items()):  # YAML gives date objects; JSONB needs strings
        if hasattr(v, "isoformat"):
            meta[k] = v.isoformat()
    entity = meta["entity_type"]
    entity_types = entity if isinstance(entity, list) else [e.strip() for e in str(entity).split(",")]
    meta["entity_types"] = entity_types
    meta["entity_type"] = ", ".join(entity_types)
    return meta


def pdf_to_markdown(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    out: list[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        para: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                if para:
                    out.append(" ".join(para))
                    para = []
                continue
            numbered = _NUMBERED_HEADING.match(line)
            if numbered or _PART_HEADING.match(line) or (line.isupper() and 3 < len(line) < 80):
                if para:
                    out.append(" ".join(para))
                    para = []
                depth = 2 if not numbered else min(2 + numbered.group(1).count("."), 5)
                out.append("#" * depth + " " + line.title() if line.isupper() else "#" * depth + " " + line)
                continue
            para.append(line)
        if para:
            out.append(" ".join(para))
    return "\n\n".join(out)


def load_bytes(filename: str, data: bytes, meta: dict | None = None) -> tuple[str, dict]:
    suffix = Path(filename).suffix.lower()
    meta = dict(meta or {})
    if suffix in (".md", ".markdown"):
        post = frontmatter.loads(data.decode("utf-8"))
        meta = {**post.metadata, **meta}
        body = post.content
    elif suffix == ".pdf":
        body = pdf_to_markdown(data)
    elif suffix == ".txt":
        body = data.decode("utf-8", errors="replace")
    else:
        raise MetadataError(f"Unsupported file type: {suffix} (use .md, .pdf or .txt)")

    title = meta.get("title")
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        title = m.group(1).strip() if m else Path(filename).stem.replace("_", " ")
    meta["title"] = title
    return body, validate_doc_meta(meta, filename)


def load_path(path: Path) -> tuple[str, dict, bytes]:
    data = path.read_bytes()
    sidecar = path.with_name(path.name + ".meta.json")
    meta = json.loads(sidecar.read_text()) if sidecar.exists() else {}
    body, doc_meta = load_bytes(path.name, data, meta)
    return body, doc_meta, data
