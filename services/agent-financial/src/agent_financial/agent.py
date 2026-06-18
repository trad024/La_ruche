"""
Financial Assistant — A2A task handler.

Receives a user message, selects the right MCP tool(s), calls them,
then uses the LLM to compose a grounded answer.
"""

from __future__ import annotations

from typing import Any

from agentkit.a2a.models import A2ATask
from agentkit.llm.client import LLMClient, ModelRole
from agentkit.mcp.registry import MCPRegistry
from agentkit.tracing import trace_span

from agent_financial.tools import (
    GeographyBreakdownTool,
    MetricsComputeTool,
    PortfolioSummaryTool,
    SectorBreakdownTool,
    TopDealsTool,
)

# ── Registry ──────────────────────────────────────────────────────────────────

registry = MCPRegistry()
registry.register(PortfolioSummaryTool())
registry.register(MetricsComputeTool())
registry.register(GeographyBreakdownTool())
registry.register(SectorBreakdownTool())
registry.register(TopDealsTool())

# ── Keyword → tool mapping ────────────────────────────────────────────────────

_TOOL_MAP: list[tuple[list[str], str, dict[str, Any]]] = [
    (
        [
            "geography",
            "geographic",
            "geographical",
            "region",
            "allocation",
            "asia",
            "europe",
            "america",
            "middle east",
            "global",
        ],
        "portfolio.geo_breakdown",
        {},
    ),
    (
        [
            "sector",
            "asset class",
            "allocation",
            "real estate",
            "private equity",
            "equities",
            "credit",
        ],
        "portfolio.sector_breakdown",
        {},
    ),
    (
        ["top deal", "best deal", "mover", "wella", "vertigo", "taka", "moic"],
        "portfolio.top_deals",
        {"limit": 5},
    ),
    (["aum", "assets under management", "total assets"], "metrics.compute", {"metric": "aum"}),
    (
        ["twr", "time-weighted", "itd return", "since inception"],
        "metrics.compute",
        {"metric": "twr"},
    ),
    (["irr", "internal rate", "internal return"], "metrics.compute", {"metric": "irr"}),
    (["sharpe", "risk-adjusted"], "metrics.compute", {"metric": "sharpe"}),
    (["volatility", "standard deviation", "risk"], "metrics.compute", {"metric": "volatility"}),
    (["annualized", "per year", "yearly return"], "metrics.compute", {"metric": "annualized"}),
    (["summary", "overview", "how is", "performance", "portfolio"], "portfolio.summary", {}),
]


def _pick_tools(message: str) -> list[tuple[str, dict[str, Any]]]:
    lower = message.lower()
    intent_text = lower.split("attached file context:", 1)[0]
    intent_text = intent_text.split("response format:", 1)[0]
    if "portiflio" in intent_text:
        intent_text = intent_text.replace("portiflio", "portfolio")

    if "portfolio" in intent_text and not any(
        keyword in intent_text
        for keyword in (
            "volatility",
            "risk",
            "sharpe",
            "irr",
            "twr",
            "annualized",
            "aum",
            "allocation",
            "sector",
            "geography",
            "deal",
        )
    ):
        return [("portfolio.summary", {})]

    picked: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for keywords, tool_name, kwargs in _TOOL_MAP:
        # Dedup by tool *and* args so multiple metrics.compute calls (aum, twr,
        # irr, …) are all kept for a multi-metric question.
        sig = f"{tool_name}:{sorted(kwargs.items())}"
        if any(kw in intent_text for kw in keywords) and sig not in seen:
            picked.append((tool_name, kwargs))
            seen.add(sig)
    return picked or [("portfolio.summary", {})]


# ── Main handler ──────────────────────────────────────────────────────────────

_llm = LLMClient(role=ModelRole.CONVERSATIONAL)

_SYSTEM_PROMPT = """You are a wealth-management financial assistant.
You have access to real portfolio data from the tools below.
Answer the client's question using ONLY the data provided by the tools.
Be precise with numbers. Do not hallucinate figures.
Format monetary values with $ and M/K suffixes where appropriate.
Never sign the answer, never include "Best regards", and never use placeholders such as [Your Name].
Use "inception-to-date TWR" when explaining ITD TWR."""


async def handle_task(task: A2ATask) -> A2ATask:
    user_msg = task.messages[-1].content if task.messages else ""

    with trace_span("financial_agent", task_id=task.task_id):
        # 1. Select and call tools
        tool_calls = _pick_tools(user_msg)
        tool_outputs: list[str] = []
        for tool_name, kwargs in tool_calls:
            result = await registry.call(tool_name, **kwargs)
            if result.ok:
                tool_outputs.append(f"[{tool_name}]\n{result.content}")

        tool_context = "\n\n".join(tool_outputs)

        # 2. Compose grounded answer with LLM
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Client question: {user_msg}\n\n"
                    f"Tool data:\n{tool_context}\n\n"
                    "Answer the client question using only the tool data above."
                ),
            },
        ]
        try:
            answer = await _llm.chat(messages)
        except Exception:
            # Fallback: return tool output directly without LLM
            answer = tool_context or "Unable to retrieve portfolio data."

    return task.succeed(answer, {"tools_called": [t for t, _ in tool_calls]})
