from __future__ import annotations

from typing import Any

from agentkit.a2a.models import A2ATask, AgentCard, AgentSkill
from agentkit.a2a.router import a2a_router
from agentkit.mcp.registry import MCPRegistry
from agentkit.tracing import trace_span
from fastapi import FastAPI

from agent_market.tools import EconIndicatorTool, MarketOverviewTool, MarketQuoteTool

# ── Registry ──────────────────────────────────────────────────────────────────

_registry = MCPRegistry()
_registry.register(MarketQuoteTool())
_registry.register(EconIndicatorTool())
_registry.register(MarketOverviewTool())

_TOOL_MAP: list[tuple[list[str], str, dict[str, Any]]] = [
    (["s&p", "spx", "nasdaq", "stock", "index"], "market.quote", {"symbol": "SPX"}),
    (["bitcoin", "btc", "crypto"], "market.quote", {"symbol": "BTC"}),
    (["gold", "gld"], "market.quote", {"symbol": "GLD"}),
    (["inflation", "cpi"], "econ.indicator", {"indicator": "us_inflation"}),
    (["fed", "interest rate", "federal reserve"], "econ.indicator", {"indicator": "us_fed_rate"}),
    (["gdp", "growth"], "econ.indicator", {"indicator": "us_gdp_growth"}),
    (["yield", "treasury", "10y"], "econ.indicator", {"indicator": "us_10y_yield"}),
    (["vix", "volatility index"], "econ.indicator", {"indicator": "vix"}),
    (["market", "overview", "conditions"], "market.overview", {}),
]


def _pick(message: str) -> tuple[str, dict[str, Any]]:
    lower = message.lower()
    for keywords, tool, kwargs in _TOOL_MAP:
        if any(kw in lower for kw in keywords):
            return tool, kwargs
    return "market.overview", {}


async def handle_task(task: A2ATask) -> A2ATask:
    msg = task.messages[-1].content if task.messages else ""
    with trace_span("market_agent", task_id=task.task_id):
        tool_name, kwargs = _pick(msg)
        result = await _registry.call(tool_name, **kwargs)
        answer = result.content if result.ok else f"Error: {result.error}"
    return task.succeed(answer, {"tool": tool_name})


_CARD = AgentCard(
    id="agent-market",
    name="Market-Data Agent",
    description="Economic indicators and market quotes.",
    version="0.1.0",
    url="http://agent-market:8002",
    skills=[
        AgentSkill(
            id="chat",
            name="Market Chat",
            description="Answer market data questions.",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        )
    ],
)

app = FastAPI(title="Market-Data Agent", version="0.1.0")
app.include_router(a2a_router(_CARD, handle_task))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-market"}
