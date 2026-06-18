"""Document/RAG agent tests."""

from __future__ import annotations

import pytest
from agent_docs.main import (
    DocIngestTool,
    RAGSearchTool,
    _extract_attachment_context,
    _search_documents,
    app,
)
from agent_docs.vector_store import chunk_text
from fastapi.testclient import TestClient

client = TestClient(app)


async def test_ingest():
    t = DocIngestTool()
    r = await t.execute(doc_id="test_doc", content="This is a test document about Aurora Brands.")
    assert r.ok
    assert "test_doc" in r.content


async def test_search_hit():
    t = RAGSearchTool()
    r = await t.execute(query="Aurora investment moic", top_k=2)
    assert r.ok
    assert "Aurora" in r.content


async def test_search_miss():
    t = RAGSearchTool()
    r = await t.execute(query="zzzquuxfoo12345")
    assert r.ok
    assert "No relevant" in r.content


def test_chunk_text_preserves_all_content():
    content = " ".join(f"word-{index}" for index in range(300))
    chunks = chunk_text(content, size=200, overlap=20)
    assert len(chunks) > 1
    assert chunks[0].startswith("word-0")
    assert chunks[-1].endswith("word-299")


def test_extract_attachment_context():
    message = "Please analyze.\n\nAttached file context:\nnote.txt\nAUM is $123M"
    assert "AUM is $123M" in _extract_attachment_context(message)


async def test_qdrant_search_path(monkeypatch: pytest.MonkeyPatch):
    async def available() -> bool:
        return True

    async def seed(_documents: dict[str, str]) -> None:
        return None

    async def search(_query: str, _top_k: int):
        return [{"id": "semantic", "score": 0.91, "content": "Vector result"}]

    monkeypatch.setattr("agent_docs.main._vector_store.available", available)
    monkeypatch.setattr("agent_docs.main._vector_store.seed", seed)
    monkeypatch.setattr("agent_docs.main._vector_store.search", search)

    results, backend = await _search_documents("meaning, not keywords", 3)
    assert backend == "qdrant"
    assert results[0]["id"] == "semantic"


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_agent_card():
    r = client.get("/agent/card")
    assert r.status_code == 200
    assert r.json()["id"] == "agent-docs"
