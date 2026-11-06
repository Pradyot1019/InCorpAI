"""End-to-end API tests against a real Postgres + pgvector. Skipped if the DB is unreachable.

Requires the seed corpus to be ingested (python ingest.py ../corpus).
"""

import asyncio
import json

import asyncpg
import pytest

from app.core.config import get_settings


def _db_ready() -> bool:
    async def probe():
        conn = await asyncpg.connect(get_settings().database_url, timeout=2)
        n = await conn.fetchval("SELECT count(*) FROM compliance_chunks")
        await conn.close()
        return n > 0
    try:
        return asyncio.run(probe())
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _db_ready(), reason="Postgres with ingested corpus not available")


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from main import app

    with TestClient(app) as c:
        yield c


def sse(text: str) -> list[tuple[str, dict]]:
    out = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        ev, data = None, None
        for line in frame.splitlines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = json.loads(line[5:].strip())
        if ev:
            out.append((ev, data))
    return out


def chat(client, **body):
    r = client.post("/api/chat", json=body)
    assert r.status_code == 200
    return sse(r.text)


def test_taxonomy(client):
    t = client.get("/api/taxonomy").json()
    codes = {j["code"] for j in t["jurisdictions"]}
    assert {"IN", "US-DE", "EU"} <= codes
    assert all(j["suggested_prompts"] for j in t["jurisdictions"])


def test_chat_event_order_and_widget(client):
    events = chat(client, query="What are the steps to incorporate with SPICe+?",
                  jurisdiction="IN", entity_type="Pvt Ltd")
    names = [e for e, _ in events]
    assert names[0] == "filters" and names[-1] == "done"
    assert names.index("sources") < names.index("token")
    sources = next(d for e, d in events if e == "sources")["sources"]
    assert sources and all(s["jurisdiction"] == "IN" for s in sources)
    widget = next(d for e, d in events if e == "widget")
    assert widget["template"] == "checklist" and widget["payload"]["items"]
    text = "".join(d["text"] for e, d in events if e == "token")
    assert "<TemplateWidget" not in text and "[1]" in text


def test_no_cross_jurisdiction_pollution(client):
    for j, e in [("EU", "Any"), ("US-DE", "C-Corp"), ("IN", "LLP")]:
        res = client.post("/api/search", json={"query": "annual filing deadline penalty",
                                               "jurisdiction": j, "entity_type": e}).json()
        assert res and all(s["jurisdiction"] == j for s in res)


def test_strict_rejection(client):
    events = chat(client, query="What's a good pizza recipe with mozzarella?",
                  jurisdiction="IN", entity_type="Pvt Ltd")
    done = events[-1][1]
    assert done["rejected"] is True and done["model"] is None
    assert next(d for e, d in events if e == "sources")["sources"] == []


def test_filter_override_note(client):
    events = chat(client, query="When is the Delaware franchise tax due?",
                  jurisdiction="IN", entity_type="Pvt Ltd")
    f = events[0][1]
    assert f["jurisdiction"] == "US-DE" and f["overridden"] and f["note"]


def test_upload_and_delete_document(client):
    md = b"---\ntitle: Test Doc\njurisdiction: EU\nentity_type: Any\nregulatory_body: EDPB\n" \
         b"compliance_phase: Data Privacy\n---\n# Test Doc\n\n## Zebra clause\n\nZebras must be registered quarterly.\n"
    r = client.post("/api/documents", files={"file": ("zz_test.md", md, "text/markdown")})
    assert r.status_code == 200 and r.json()["chunks"] == 1
    hits = client.post("/api/search", json={"query": "zebra registration", "jurisdiction": "EU",
                                            "entity_type": "Any"}).json()
    assert hits[0]["source_document"] == "zz_test.md"
    doc = next(d for d in client.get("/api/documents").json() if d["source_document"] == "zz_test.md")
    assert client.delete(f"/api/documents/{doc['id']}").status_code == 204


def test_upload_rejects_missing_metadata(client):
    r = client.post("/api/documents", files={"file": ("x.md", b"# hi\n\ntext", "text/markdown")})
    assert r.status_code == 422 and "missing required metadata" in r.json()["detail"]
