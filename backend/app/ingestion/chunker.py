"""Structure-aware Markdown chunker.

Walks the markdown-it AST (CommonMark + GFM tables) and produces chunks that:

1. Carry their full parent-header breadcrumb ("Incorporation > SPICe+ Part B > Section 3"),
   both in metadata and as a prefix inside the embedded text.
2. Never cross a section boundary.
3. Keep tables intact. A table larger than the budget is split *by rows* and every piece
   repeats the header row, so no row is ever broken across chunks.
4. Keep list items and code fences whole where possible.

Headings may carry attributes that override metadata for their subtree:

    ## SPICe+ Part B {clause="SPICe+ Part B" phase="Incorporation"}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from markdown_it import MarkdownIt

_ATTR_BLOCK = re.compile(r"\s*\{([^{}]*)\}\s*$")
_ATTR_PAIR = re.compile(r'(\w+)="([^"]*)"')
_SENTENCE = re.compile(r"(?<=[.!?;:])\s+(?=[A-Z0-9(\"'])")


def estimate_tokens(text: str) -> int:
    """Cheap, dependency-free token estimate (~1.33 tokens/word for English legal text)."""
    return max(1, int(len(text.split()) * 1.33))


@dataclass
class Block:
    kind: str  # paragraph | table | list | code | quote | html | hr
    text: str
    path: list[str]
    attrs: dict[str, str]


@dataclass
class Chunk:
    body: str
    path: list[str]
    attrs: dict[str, str]
    has_table: bool = False
    index: int = 0

    def embedded_text(self, doc_title: str) -> str:
        crumb = " > ".join(self.path) if self.path else doc_title
        return f"[{doc_title}] {crumb}\n\n{self.body}"


@dataclass
class _Heading:
    level: int
    text: str
    attrs: dict[str, str] = field(default_factory=dict)


def _parse_heading(raw: str) -> tuple[str, dict[str, str]]:
    attrs: dict[str, str] = {}
    m = _ATTR_BLOCK.search(raw)
    if m:
        attrs = dict(_ATTR_PAIR.findall(m.group(1)))
        raw = raw[: m.start()]
    return raw.strip(), attrs


def extract_blocks(markdown: str) -> list[Block]:
    md = MarkdownIt("commonmark").enable("table")
    tokens = md.parse(markdown)
    lines = markdown.splitlines()
    stack: list[_Heading] = []
    blocks: list[Block] = []

    def current() -> tuple[list[str], dict[str, str]]:
        merged: dict[str, str] = {}
        for h in stack:
            merged.update(h.attrs)
        return [h.text for h in stack], merged

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "heading_open":
            level = int(tok.tag[1])
            text, attrs = _parse_heading(tokens[i + 1].content)
            while stack and stack[-1].level >= level:
                stack.pop()
            # H1 is the document title: don't repeat it in every breadcrumb
            if level > 1:
                stack.append(_Heading(level, text, attrs))
            i += 3
            continue

        if tok.level == 0 and tok.map and tok.nesting in (1, 0):
            kind = {
                "paragraph_open": "paragraph",
                "table_open": "table",
                "bullet_list_open": "list",
                "ordered_list_open": "list",
                "fence": "code",
                "code_block": "code",
                "blockquote_open": "quote",
                "html_block": "html",
                "hr": "hr",
            }.get(tok.type)
            if kind and kind != "hr":
                start, end = tok.map
                text = "\n".join(lines[start:end]).strip()
                if text:
                    path, attrs = current()
                    blocks.append(Block(kind, text, path, attrs))
            # skip to the matching close token
            if tok.nesting == 1:
                depth = 1
                i += 1
                while i < len(tokens) and depth:
                    depth += tokens[i].nesting
                    i += 1
                continue
        i += 1
    return blocks


# ---------------------------------------------------------------------------
# Splitting oversized blocks
# ---------------------------------------------------------------------------


def _split_table(text: str, budget: int) -> list[str]:
    rows = text.splitlines()
    if len(rows) < 3:
        return [text]
    header, sep, body = rows[0], rows[1], rows[2:]
    pieces, cur = [], []
    base = estimate_tokens(header + " " + sep)
    size = base
    for row in body:
        t = estimate_tokens(row)
        if cur and size + t > budget:
            pieces.append("\n".join([header, sep, *cur]))
            cur, size = [], base
        cur.append(row)
        size += t
    if cur:
        pieces.append("\n".join([header, sep, *cur]))
    return pieces


def _split_list(text: str, budget: int) -> list[str]:
    items = re.split(r"\n(?=(?:[-*+]|\d+[.)])\s)", text)
    return _pack(items, budget, "\n")


def _split_prose(text: str, budget: int) -> list[str]:
    return _pack(_SENTENCE.split(text), budget, " ")


def _pack(parts: list[str], budget: int, joiner: str) -> list[str]:
    out, cur, size = [], [], 0
    for p in parts:
        t = estimate_tokens(p)
        if cur and size + t > budget:
            out.append(joiner.join(cur))
            cur, size = [], 0
        cur.append(p)
        size += t
    if cur:
        out.append(joiner.join(cur))
    return out


def _explode(block: Block, budget: int) -> list[Block]:
    if estimate_tokens(block.text) <= budget:
        return [block]
    splitter = {"table": _split_table, "list": _split_list}.get(block.kind, _split_prose)
    if block.kind == "code":
        return [block]  # never split code fences
    return [Block(block.kind, t, block.path, block.attrs) for t in splitter(block.text, budget)]


# ---------------------------------------------------------------------------
# Packing blocks into chunks
# ---------------------------------------------------------------------------


def chunk_markdown(markdown: str, max_tokens: int = 450, overlap_tokens: int = 60) -> list[Chunk]:
    blocks: list[Block] = []
    for b in extract_blocks(markdown):
        blocks.extend(_explode(b, max_tokens))

    chunks: list[Chunk] = []
    cur: list[Block] = []
    size = 0

    def flush() -> None:
        nonlocal cur, size
        if not cur:
            return
        body = "\n\n".join(b.text for b in cur)
        chunks.append(
            Chunk(
                body=body,
                path=cur[0].path,
                attrs=cur[0].attrs,
                has_table=any(b.kind == "table" for b in cur),
            )
        )
        # overlap: carry the last prose block forward if it is small (never tables)
        tail = cur[-1]
        if tail.kind == "paragraph" and estimate_tokens(tail.text) <= overlap_tokens:
            cur, size = [tail], estimate_tokens(tail.text)
            cur[0] = Block("overlap", tail.text, tail.path, tail.attrs)
        else:
            cur, size = [], 0

    for block in blocks:
        t = estimate_tokens(block.text)
        section_changed = bool(cur) and cur[0].path != block.path
        if section_changed:
            flush()
            cur, size = [], 0  # overlap never crosses sections
        elif cur and size + t > max_tokens:
            flush()
        cur.append(block)
        size += t
    # final flush: drop a chunk that is only an overlap carry-over
    if cur and not all(b.kind == "overlap" for b in cur):
        flush()

    for n, c in enumerate(chunks):
        c.index = n
    return chunks
