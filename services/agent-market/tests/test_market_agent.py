"""Market-Data agent tests."""

from __future__ import annotations

from agent_market.main import app
from agent_market.tools import EconIndicatorTool, MarketOverviewTool, MarketQuoteTool
from fastapi.testclient import TestClient

client = TestClient(app)


async def test_quote_spx():
    t = MarketQuoteTool()
    r = await t.execute(symbol="SPX")
    assert r.ok
    assert "S&P 500" in r.content


async def test_quote_unknown():
    t = MarketQuoteTool()
    r = await t.execute(symbol="UNKNOWN123")
    assert not r.ok
    assert r.error is not None


async def test_econ_inflation():
    t = EconIndicatorTool()
    r = await t.execute(indicator="us_inflation")
    assert r.ok
    assert "%" in r.content


async def test_market_overview():
    t = MarketOverviewTool()
    r = await t.execute()
    assert r.ok
    assert "S&P 500" in r.content
    assert "Fed Rate" in r.content


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_agent_card():
    r = client.get("/agent/card")
    assert r.status_code == 200
    assert r.json()["id"] == "agent-market"
