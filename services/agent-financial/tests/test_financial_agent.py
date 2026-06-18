"""Financial Assistant — tool selection + response tests."""

from __future__ import annotations

from agent_financial.agent import _pick_tools
from agent_financial.main import app
from agent_financial.tools import (
    GeographyBreakdownTool,
    MetricsComputeTool,
    PortfolioSummaryTool,
    SectorBreakdownTool,
    TopDealsTool,
)
from fastapi.testclient import TestClient

client = TestClient(app)


# ── Tool routing ───────────────────────────────────────────────────────────────


def test_route_aum():
    assert any(t == "metrics.compute" for t, _ in _pick_tools("What is the AUM?"))


def test_route_geo():
    assert any(t == "portfolio.geo_breakdown" for t, _ in _pick_tools("geography breakdown"))


def test_route_sector():
    assert any(t == "portfolio.sector_breakdown" for t, _ in _pick_tools("sector allocation"))


def test_route_top_deals():
    assert any(t == "portfolio.top_deals" for t, _ in _pick_tools("top deals by moic"))


def test_route_default():
    tools = _pick_tools("hello how are you")
    assert tools[0][0] == "portfolio.summary"


def test_route_misspelled_portfolio_uses_summary():
    tools = _pick_tools("what is my portiflio ?\n\nResponse format: include risks")
    assert tools == [("portfolio.summary", {})]


# ── Tool execution ─────────────────────────────────────────────────────────────


async def test_portfolio_summary_tool():
    t = PortfolioSummaryTool()
    r = await t.execute()
    assert r.ok
    assert "AUM" in r.content
    assert "TWR" in r.content
    assert "Sharpe" in r.content


async def test_metrics_aum():
    t = MetricsComputeTool()
    r = await t.execute(metric="aum")
    assert r.ok
    assert "$" in r.content


async def test_metrics_sharpe():
    t = MetricsComputeTool()
    r = await t.execute(metric="sharpe")
    assert r.ok
    assert "Sharpe" in r.content


async def test_geo_breakdown():
    t = GeographyBreakdownTool()
    r = await t.execute()
    assert r.ok
    assert "Asia" in r.content
    assert "37%" in r.content


async def test_sector_breakdown():
    t = SectorBreakdownTool()
    r = await t.execute()
    assert r.ok
    assert "Real Estate" in r.content


async def test_top_deals():
    t = TopDealsTool()
    r = await t.execute(limit=3)
    assert r.ok
    assert "Aurora" in r.content
    assert "1.55x" in r.content


# ── HTTP endpoints ─────────────────────────────────────────────────────────────


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_agent_card():
    r = client.get("/agent/card")
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == "agent-financial"
    assert len(data["skills"]) > 0
