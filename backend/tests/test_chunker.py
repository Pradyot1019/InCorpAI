from app.ingestion.chunker import chunk_markdown, extract_blocks

DOC = """# Title

## Pre-Incorporation {phase="Pre-Incorporation"}

Intro paragraph about the phase.

### SPICe+ Part A Name Reservation {clause="SPICe+ Part A"}

Names are reserved for 20 days.

| Form | Purpose |
|---|---|
| INC-33 | e-MoA |
| INC-34 | e-AoA |

## Incorporation

Part B text.
"""


def test_breadcrumbs_and_attrs():
    chunks = chunk_markdown(DOC, max_tokens=400)
    by_path = {tuple(c.path): c for c in chunks}
    deep = by_path[("Pre-Incorporation", "SPICe+ Part A Name Reservation")]
    assert deep.attrs["clause"] == "SPICe+ Part A"
    assert deep.attrs["phase"] == "Pre-Incorporation"  # inherited from parent heading
    assert deep.has_table
    assert "| INC-34 | e-AoA |" in deep.body
    assert by_path[("Incorporation",)].attrs == {}


def test_chunks_never_cross_sections():
    chunks = chunk_markdown(DOC, max_tokens=400)
    assert all("Part B text" not in c.body for c in chunks if c.path != ["Incorporation"])


def test_large_table_split_by_rows_with_header_repeated():
    rows = "\n".join(f"| Item {i} | " + "word " * 30 + "|" for i in range(30))
    md = f"## Fees\n\n| Item | Detail |\n|---|---|\n{rows}\n"
    chunks = chunk_markdown(md, max_tokens=200)
    assert len(chunks) > 1
    for c in chunks:
        lines = c.body.splitlines()
        assert lines[0] == "| Item | Detail |" and lines[1] == "|---|---|"
        assert all(ln.startswith("| Item ") and ln.endswith("|") for ln in lines[2:])
    total_rows = sum(len(c.body.splitlines()) - 2 for c in chunks)
    assert total_rows == 30  # no row lost or duplicated


def test_h1_not_in_breadcrumb():
    blocks = extract_blocks(DOC)
    assert all("Title" not in b.path for b in blocks)


def test_embedded_text_has_prefix():
    c = chunk_markdown(DOC)[0]
    assert c.embedded_text("My Doc").startswith("[My Doc] Pre-Incorporation")
