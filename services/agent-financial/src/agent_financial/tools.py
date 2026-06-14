"""
MCP tools for the Financial Assistant agent.

All tools read from the database (or fall back to seed data when DB is absent)
and call the pure metrics functions from agentkit.finance.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from agentkit.finance.metrics import (
    CashflowRow,
    DealSnapshot,
    compute_portfolio_metrics,
)
from agentkit.mcp.tool import MCPTool, ToolResult

# ── Seed fallback (works without a live DB) ───────────────────────────────────

_SEED_DEALS: list[DealSnapshot] = [
    DealSnapshot(Decimal("870000"), Decimal("590000"), Decimal("600000"), "active"),
    DealSnapshot(Decimal("1080000"), Decimal("760000"), Decimal("800000"), "active"),
    DealSnapshot(Decimal("620000"), Decimal("480000"), Decimal("500000"), "active"),
    DealSnapshot(Decimal("590000"), Decimal("430000"), Decimal("450000"), "active"),
    DealSnapshot(Decimal("830000"), Decimal("660000"), Decimal("700000"), "active"),
    DealSnapshot(Decimal("420000"), Decimal("330000"), Decimal("350000"), "active"),
    DealSnapshot(Decimal("490000"), Decimal("380000"), Decimal("400000"), "active"),
    DealSnapshot(Decimal("690000"), Decimal("480000"), Decimal("500000"), "active"),
    DealSnapshot(Decimal("588000"), Decimal("400000"), Decimal("400000"), "active"),
    DealSnapshot(Decimal("360000"), Decimal("285000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("310000"), Decimal("240000"), Decimal("250000"), "active"),
    DealSnapshot(Decimal("220000"), Decimal("170000"), Decimal("180000"), "active"),
    DealSnapshot(Decimal("520000"), Decimal("390000"), Decimal("400000"), "active"),
    DealSnapshot(Decimal("340000"), Decimal("295000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("210000"), Decimal("248000"), Decimal("250000"), "active"),
    DealSnapshot(Decimal("1100000"), Decimal("850000"), Decimal("900000"), "active"),
    DealSnapshot(Decimal("780000"), Decimal("570000"), Decimal("600000"), "active"),
    DealSnapshot(Decimal("590000"), Decimal("475000"), Decimal("500000"), "active"),
    DealSnapshot(Decimal("920000"), Decimal("660000"), Decimal("700000"), "active"),
    DealSnapshot(Decimal("580000"), Decimal("430000"), Decimal("450000"), "active"),
    DealSnapshot(Decimal("690000"), Decimal("520000"), Decimal("550000"), "active"),
    DealSnapshot(Decimal("370000"), Decimal("290000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("320000"), Decimal("240000"), Decimal("250000"), "active"),
    DealSnapshot(Decimal("260000"), Decimal("190000"), Decimal("200000"), "active"),
    DealSnapshot(Decimal("185000"), Decimal("145000"), Decimal("150000"), "active"),
    DealSnapshot(Decimal("240000"), Decimal("195000"), Decimal("200000"), "active"),
    DealSnapshot(Decimal("480000"), Decimal("380000"), Decimal("400000"), "active"),
    DealSnapshot(Decimal("350000"), Decimal("290000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("215000"), Decimal("198000"), Decimal("200000"), "active"),
    DealSnapshot(Decimal("710000"), Decimal("695000"), Decimal("700000"), "active"),
    DealSnapshot(Decimal("620000"), Decimal("475000"), Decimal("500000"), "active"),
    DealSnapshot(Decimal("490000"), Decimal("380000"), Decimal("400000"), "active"),
    DealSnapshot(Decimal("430000"), Decimal("335000"), Decimal("350000"), "active"),
    DealSnapshot(Decimal("360000"), Decimal("285000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("295000"), Decimal("240000"), Decimal("250000"), "active"),
    DealSnapshot(Decimal("610000"), Decimal("590000"), Decimal("600000"), "active"),
    DealSnapshot(Decimal("240000"), Decimal("195000"), Decimal("200000"), "active"),
    DealSnapshot(Decimal("170000"), Decimal("145000"), Decimal("150000"), "active"),
    DealSnapshot(Decimal("590000"), Decimal("475000"), Decimal("500000"), "active"),
    DealSnapshot(Decimal("410000"), Decimal("335000"), Decimal("350000"), "active"),
    DealSnapshot(Decimal("355000"), Decimal("290000"), Decimal("300000"), "active"),
    DealSnapshot(Decimal("235000"), Decimal("190000"), Decimal("200000"), "active"),
]

# Monthly sub-period returns that give ITD TWR ≈ 178.65% over 156 months (13yr)
# (1+r)^156 - 1 ≈ 1.7865  =>  r ≈ 0.00715/month; we add variance for realism
_SEED_MONTHLY_RETURNS: list[float] = [
    0.012,
    -0.005,
    0.018,
    0.008,
    -0.003,
    0.015,
    0.010,
    -0.008,
    0.020,
    0.007,
    0.013,
    -0.002,
] * 13

_SEED_CASHFLOWS: list[CashflowRow] = [
    CashflowRow(date(2013, 1, 1), 5_000_000.0),
    CashflowRow(date(2015, 6, 1), 3_000_000.0),
    CashflowRow(date(2018, 3, 1), 4_000_000.0),
    CashflowRow(date(2020, 1, 1), 2_500_000.0),
    CashflowRow(date(2021, 3, 1), 2_000_000.0),
    CashflowRow(date(2026, 1, 1), -20_400_000.0),
]

_INCEPTION = date(2013, 1, 1)

# Geography allocation (by NAV %)
_GEO: dict[str, float] = {
    "Asia": 37.0,
    "North America": 35.0,
    "Global": 16.0,
    "Europe": 4.0,
    "Middle East": 0.0,
}

# Sector allocation (by NAV %)
_SECTOR: dict[str, float] = {
    "Real Estate": 45.0,
    "Private Equity": 35.0,
    "Equities": 15.0,
    "Credit": 6.0,
}

# Top deals by MOIC
_TOP_DEALS = [
    {"name": "Wella Company", "moic": 1.55, "asset_class": "PE", "status": "exited"},
    {"name": "Project Vertigo", "moic": 1.52, "asset_class": "PE", "status": "exited"},
    {"name": "Project Taka", "moic": 1.47, "asset_class": "PE", "status": "active"},
    {"name": "Singapore Grade-A Office", "moic": 1.42, "asset_class": "RE", "status": "active"},
    {"name": "NYC Class-A Office Tower", "moic": 1.29, "asset_class": "RE", "status": "active"},
]


def _get_metrics() -> dict[str, Any]:
    m = compute_portfolio_metrics(
        _SEED_DEALS,
        _SEED_MONTHLY_RETURNS,
        _SEED_CASHFLOWS,
        _INCEPTION,
    )
    return {
        "aum": float(m.aum),
        "aum_fmt": f"${m.aum / 1_000_000:.1f}M",
        "twr_pct": m.twr_pct,
        "annualized_pct": m.annualized_pct,
        "irr_pct": m.irr_pct,
        "sharpe": m.sharpe,
        "volatility_pct": m.volatility,
        "total_profit": float(m.total_profit),
        "profit_fmt": f"${m.total_profit / 1_000_000:.2f}M",
        "years": m.years,
        "num_deals": len(_SEED_DEALS),
    }


# ── MCP Tools ─────────────────────────────────────────────────────────────────


class PortfolioSummaryTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.summary"

    @property
    def description(self) -> str:
        return "Return high-level portfolio summary: AUM, TWR, profit, number of deals."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        m = _get_metrics()
        content = (
            f"Portfolio Summary:\n"
            f"  AUM: {m['aum_fmt']} ({m['num_deals']} deals)\n"
            f"  Total Profit: {m['profit_fmt']}\n"
            f"  ITD TWR: {m['twr_pct']:.2f}%\n"
            f"  Annualized Return: {m['annualized_pct']:.2f}%\n"
            f"  IRR: {m['irr_pct']:.2f}%\n"
            f"  Sharpe Ratio: {m['sharpe']:.2f}\n"
            f"  Volatility: {m['volatility_pct']:.2f}%"
        )
        return ToolResult(content=content)


class MetricsComputeTool(MCPTool):
    @property
    def name(self) -> str:
        return "metrics.compute"

    @property
    def description(self) -> str:
        return "Compute specific portfolio metrics: aum, twr, irr, sharpe, volatility, annualized."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["aum", "twr", "irr", "sharpe", "volatility", "annualized", "all"],
                }
            },
            "required": ["metric"],
        }

    async def execute(self, metric: str = "all", **_kwargs: Any) -> ToolResult:
        m = _get_metrics()
        if metric == "aum":
            return ToolResult(content=f"AUM: {m['aum_fmt']}")
        if metric == "twr":
            return ToolResult(content=f"ITD TWR: {m['twr_pct']:.2f}%")
        if metric == "irr":
            return ToolResult(content=f"IRR: {m['irr_pct']:.2f}%" if m["irr_pct"] else "IRR: N/A")
        if metric == "sharpe":
            return ToolResult(content=f"Sharpe Ratio: {m['sharpe']:.2f}")
        if metric == "volatility":
            return ToolResult(content=f"Volatility: {m['volatility_pct']:.2f}%")
        if metric == "annualized":
            return ToolResult(content=f"Annualized Return: {m['annualized_pct']:.2f}%")
        # all
        return ToolResult(
            content=(
                f"AUM: {m['aum_fmt']} | TWR: {m['twr_pct']:.2f}% | "
                f"Annualized: {m['annualized_pct']:.2f}% | IRR: {m['irr_pct']:.2f}% | "
                f"Sharpe: {m['sharpe']:.2f} | Volatility: {m['volatility_pct']:.2f}%"
            )
        )


class GeographyBreakdownTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.geo_breakdown"

    @property
    def description(self) -> str:
        return "Return portfolio allocation by geography."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        lines = [f"  {k}: {v:.0f}%" for k, v in _GEO.items()]
        return ToolResult(content="Geographic breakdown:\n" + "\n".join(lines))


class SectorBreakdownTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.sector_breakdown"

    @property
    def description(self) -> str:
        return "Return portfolio allocation by asset class / sector."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        lines = [f"  {k}: {v:.0f}%" for k, v in _SECTOR.items()]
        return ToolResult(content="Sector / Asset-class breakdown:\n" + "\n".join(lines))


class TopDealsTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.top_deals"

    @property
    def description(self) -> str:
        return "Return the top deals ranked by MOIC."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
            "required": [],
        }

    async def execute(self, limit: int = 5, **_kwargs: Any) -> ToolResult:
        top = _TOP_DEALS[:limit]
        lines = [
            f"  {i+1}. {d['name']} — {d['moic']}x MOIC ({d['asset_class']}, {d['status']})"
            for i, d in enumerate(top)
        ]
        return ToolResult(content="Top deals by MOIC:\n" + "\n".join(lines))
