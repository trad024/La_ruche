"""Document/RAG agent tests."""

from __future__ import annotations

from agent_docs.main import DocIngestTool, RAGSearchTool, app
from fastapi.testclient import TestClient

client = TestClient(app)


async def test_ingest():
    t = DocIngestTool()
    r = await t.execute(doc_id="test_doc", content="This is a test document about Wella.")
    assert r.ok
    assert "test_doc" in r.content


async def test_search_hit():
    t = RAGSearchTool()
    r = await t.execute(query="Wella investment moic", top_k=2)
    assert r.ok
    assert "Wella" in r.content


async def test_search_miss():
    t = RAGSearchTool()
    r = await t.execute(query="zzzquuxfoo12345")
    assert r.ok
    assert "No relevant" in r.content


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_agent_card():
    r = client.get("/agent/card")
    assert r.status_code == 200
    assert r.json()["id"] == "agent-docs"
