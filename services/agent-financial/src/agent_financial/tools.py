"""
MCP tools for the Financial Assistant agent.

All numbers come from the single canonical portfolio in agentkit.portfolio,
which the metrics library computes from calibrated inputs — so the figures the
agent reports match the orchestrator API, the dashboards, and the demo exactly.
"""

from __future__ import annotations

from typing import Any

from agentkit.mcp.tool import MCPTool, ToolResult
from agentkit.portfolio import DEALS as _DEALS
from agentkit.portfolio import GEO as _GEO
from agentkit.portfolio import SECTOR as _SECTOR
from agentkit.portfolio import TOP_DEALS as _TOP_DEALS
from agentkit.portfolio import _SEED_MONTHLY_RETURNS
from agentkit.portfolio import get_metrics as _get_metrics

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
            f"  {i + 1}. {d['name']} — {d['moic']}x MOIC ({d['asset_class']}, {d['status']})"
            for i, d in enumerate(top)
        ]
        return ToolResult(content="Top deals by MOIC:\n" + "\n".join(lines))


class BottomDealsTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.bottom_deals"

    @property
    def description(self) -> str:
        return "Return the worst performing deals ranked by TWR."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 5}},
            "required": [],
        }

    async def execute(self, limit: int = 5, **_kwargs: Any) -> ToolResult:
        sorted_deals = sorted(_DEALS, key=lambda d: d.get("twr", 0))
        bottom = sorted_deals[:limit]
        lines = [
            f"  {i + 1}. {d['name']} — {d['twr']}% TWR ({d['sector']}, {d['geo']}, {d['status']})"
            for i, d in enumerate(bottom)
        ]
        return ToolResult(content="Worst performing deals by TWR:\n" + "\n".join(lines))


class DealDetailTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.deal_detail"

    @property
    def description(self) -> str:
        return "Look up details for a specific deal by name."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

    async def execute(self, query: str = "", **_kwargs: Any) -> ToolResult:
        lower_query = query.lower().strip()
        for deal in _DEALS:
            if deal["name"].lower() in lower_query:
                parts = [f"{k}: {v}" for k, v in deal.items()]
                return ToolResult(content="Deal details:\n" + "\n".join(parts))
        return ToolResult(content=f"I could not find a deal matching '{query}' in the portfolio.")


class SectorComparisonTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.sector_comparison"

    @property
    def description(self) -> str:
        return "Compare two sectors by allocation %, deal count, and average TWR."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        sector_data: dict[str, dict[str, Any]] = {}
        for deal in _DEALS:
            sec = deal["sector"]
            if sec not in sector_data:
                sector_data[sec] = {"count": 0, "twr_sum": 0.0}
            sector_data[sec]["count"] += 1
            sector_data[sec]["twr_sum"] += deal.get("twr", 0)
        lines = []
        for sec, pct in _SECTOR.items():
            d = sector_data.get(sec, {"count": 0, "twr_sum": 0})
            avg_twr = d["twr_sum"] / d["count"] if d["count"] else 0
            lines.append(f"  {sec}: {pct:.0f}% allocation, {d['count']} deals, avg TWR {avg_twr:.1f}%")
        return ToolResult(content="Sector comparison:\n" + "\n".join(lines))


class MaxDrawdownTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.max_drawdown"

    @property
    def description(self) -> str:
        return "Compute the maximum drawdown from the portfolio return series."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        returns = _SEED_MONTHLY_RETURNS
        cum = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in returns:
            cum *= 1.0 + r
            peak = max(peak, cum)
            dd = (peak - cum) / peak
            max_dd = max(max_dd, dd)
        # Express as a positive percentage of peak loss
        return ToolResult(content=f"Maximum drawdown: {max_dd * 100:.2f}%")


class CurrencyExposureTool(MCPTool):
    @property
    def name(self) -> str:
        return "portfolio.currency_exposure"

    @property
    def description(self) -> str:
        return "Return an estimated portfolio currency exposure based on geographic allocation."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        # Synthetic currency split derived from geography allocation
        weights = {
            "USD": _GEO["North America"] + _GEO["Middle East"] * 0.8 + _GEO["Global"] * 0.5,
            "EUR": _GEO["Europe"] + _GEO["Global"] * 0.25,
            "GBP": _GEO["Europe"] * 0.15,
            "JPY": _GEO["Asia"] * 0.25,
            "CNY": _GEO["Asia"] * 0.25,
            "Other": _GEO["Asia"] * 0.15 + _GEO["Global"] * 0.15 + _GEO["Middle East"] * 0.2,
        }
        lines = [f"  {ccy}: {pct:.0f}%" for ccy, pct in weights.items() if pct >= 1.0]
        return ToolResult(content="Estimated currency exposure:\n" + "\n".join(lines))
