"""MCP tools for the Market-Data agent — mock/static data, pluggable."""

from __future__ import annotations

from typing import Any

from agentkit.mcp.tool import MCPTool, ToolResult

# ── Static mock data (replace with free API calls in production) ───────────────

_QUOTES: dict[str, dict[str, Any]] = {
    "SPX": {"name": "S&P 500", "price": 5247.49, "change_pct": 0.42, "currency": "USD"},
    "AAPL": {"name": "Apple Inc.", "price": 189.30, "change_pct": -0.18, "currency": "USD"},
    "TSLA": {"name": "Tesla Inc.", "price": 175.22, "change_pct": 1.05, "currency": "USD"},
    "BTC": {"name": "Bitcoin", "price": 67_450.00, "change_pct": 2.33, "currency": "USD"},
    "GLD": {"name": "Gold (oz)", "price": 2328.60, "change_pct": 0.15, "currency": "USD"},
    "USDEUR": {"name": "USD/EUR", "price": 0.9285, "change_pct": -0.05, "currency": "EUR"},
}

_INDICATORS: dict[str, dict[str, Any]] = {
    "us_gdp_growth": {"name": "US GDP Growth (YoY)", "value": 2.8, "unit": "%", "date": "2024-Q4"},
    "us_inflation": {
        "name": "US CPI Inflation (YoY)",
        "value": 3.1,
        "unit": "%",
        "date": "2024-12",
    },
    "us_fed_rate": {"name": "US Fed Funds Rate", "value": 5.25, "unit": "%", "date": "2024-12"},
    "us_10y_yield": {
        "name": "US 10-Year Treasury Yield",
        "value": 4.55,
        "unit": "%",
        "date": "2024-12",
    },
    "global_growth": {
        "name": "IMF Global Growth Forecast",
        "value": 3.2,
        "unit": "%",
        "date": "2025",
    },
    "vix": {"name": "VIX Volatility Index", "value": 14.8, "unit": "points", "date": "2024-12"},
}


class MarketQuoteTool(MCPTool):
    @property
    def name(self) -> str:
        return "market.quote"

    @property
    def description(self) -> str:
        return "Get current market price and daily change for a symbol."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"symbol": {"type": "string", "description": "e.g. SPX, AAPL, BTC"}},
            "required": ["symbol"],
        }

    async def execute(self, symbol: str = "SPX", **_kwargs: Any) -> ToolResult:
        key = symbol.upper()
        q = _QUOTES.get(key)
        if not q:
            return ToolResult(error=f"Symbol '{symbol}' not found")
        sign = "+" if q["change_pct"] >= 0 else ""
        content = (
            f"{q['name']} ({key}): {q['currency']} {q['price']:,.2f}  "
            f"({sign}{q['change_pct']:.2f}% today)"
        )
        return ToolResult(content=content)


class EconIndicatorTool(MCPTool):
    @property
    def name(self) -> str:
        return "econ.indicator"

    @property
    def description(self) -> str:
        return "Get an economic indicator value."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "indicator": {
                    "type": "string",
                    "enum": list(_INDICATORS.keys()),
                    "description": "Economic indicator key",
                }
            },
            "required": ["indicator"],
        }

    async def execute(self, indicator: str = "us_gdp_growth", **_kwargs: Any) -> ToolResult:
        ind = _INDICATORS.get(indicator)
        if not ind:
            return ToolResult(error=f"Indicator '{indicator}' not found")
        content = f"{ind['name']}: {ind['value']}{ind['unit']}  (as of {ind['date']})"
        return ToolResult(content=content)


class MarketOverviewTool(MCPTool):
    @property
    def name(self) -> str:
        return "market.overview"

    @property
    def description(self) -> str:
        return "Return a summary of key market indices and economic conditions."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def execute(self, **_kwargs: Any) -> ToolResult:
        lines = [
            f"  S&P 500: {_QUOTES['SPX']['price']:,.2f}  ({_QUOTES['SPX']['change_pct']:+.2f}%)",
            f"  Gold: ${_QUOTES['GLD']['price']:,.2f}/oz",
            f"  BTC: ${_QUOTES['BTC']['price']:,.0f}",
            f"  Fed Rate: {_INDICATORS['us_fed_rate']['value']}%",
            f"  10Y Yield: {_INDICATORS['us_10y_yield']['value']}%",
            f"  US Inflation: {_INDICATORS['us_inflation']['value']}%",
            f"  VIX: {_INDICATORS['vix']['value']}",
        ]
        return ToolResult(content="Market Overview:\n" + "\n".join(lines))
