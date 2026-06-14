"""QA agent tests."""

from __future__ import annotations

from agent_qa.main import TestGenerateTool, app
from fastapi.testclient import TestClient

client = TestClient(app)


async def test_generate_fallback():
    t = TestGenerateTool()
    r = await t.execute(service="orchestrator", description="health check endpoint")
    assert r.ok
    assert "def test_" in r.content or "pytest" in r.content.lower()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_agent_card():
    r = client.get("/agent/card")
    assert r.status_code == 200
    assert r.json()["id"] == "agent-qa"
