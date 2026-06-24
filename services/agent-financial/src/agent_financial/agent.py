"""
Financial Assistant — A2A task handler.

Receives a user message, selects the right MCP tool(s), calls them,
then uses the LLM to compose a grounded answer.
"""

from __future__ import annotations

import re
from typing import Any

from agentkit.a2a.models import A2ATask
from agentkit.llm.client import LLMClient, ModelRole
from agentkit.mcp.registry import MCPRegistry
from agentkit.tracing import trace_span

from agent_financial.tools import (
    BottomDealsTool,
    CurrencyExposureTool,
    DealDetailTool,
    GeographyBreakdownTool,
    MaxDrawdownTool,
    MetricsComputeTool,
    PortfolioSummaryTool,
    SectorBreakdownTool,
    SectorComparisonTool,
    TopDealsTool,
)

# ── Registry ──────────────────────────────────────────────────────────────────

registry = MCPRegistry()
registry.register(PortfolioSummaryTool())
registry.register(MetricsComputeTool())
registry.register(GeographyBreakdownTool())
registry.register(SectorBreakdownTool())
registry.register(TopDealsTool())
registry.register(BottomDealsTool())
registry.register(MaxDrawdownTool())
registry.register(CurrencyExposureTool())
registry.register(DealDetailTool())
registry.register(SectorComparisonTool())

# ── Keyword → tool mapping ────────────────────────────────────────────────────

_TOOL_MAP: list[tuple[list[str], str, dict[str, Any]]] = [
    (
        [
            "geography",
            "geographic",
            "geographical",
            "region",
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
        ["top deal", "top deals", "best deal", "best deals", "mover", "wella", "vertigo", "taka", "moic"],
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
    (["max drawdown", "drawdown", "peak-to-trough"], "portfolio.max_drawdown", {}),
    (["currency", "fx", "forex", "exposure"], "portfolio.currency_exposure", {}),
    (["worst deal", "worst performing", "bottom deal", "bottom performing"], "portfolio.bottom_deals", {"limit": 5}),
    (["detail", "details about", "investment in", "about my", "tell me about"], "portfolio.deal_detail", {"query": "{user_msg}"}),
    (["compare", "comparison", "real estate", "private equity"], "portfolio.sector_comparison", {}),
    (["summary", "overview", "how is", "performance"], "portfolio.summary", {}),
]


def _is_followup_without_context(message: str, history: list[dict[str, str]]) -> bool:
    lower = message.lower().strip()
    followup_starts = ("what about", "how about", "and ", "also ", "in ", "for ", "about ")
    return lower.startswith(followup_starts) and not any(
        m.get("role") == "assistant" for m in history
    )


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
            "drawdown",
            "currency",
            "exposure",
            "worst",
            "bottom",
            "detail",
            "investment",
        )
    ):
        return [("portfolio.summary", {})]

    picked: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for keywords, tool_name, kwargs in _TOOL_MAP:
        # Dedup by tool *and* args so multiple metrics.compute calls (aum, twr,
        # irr, …) are all kept for a multi-metric question.
        resolved_kwargs = {
            k: (message if v == "{user_msg}" else v) for k, v in kwargs.items()
        }
        sig = f"{tool_name}:{sorted(resolved_kwargs.items())}"
        if any(kw in intent_text for kw in keywords) and sig not in seen:
            picked.append((tool_name, resolved_kwargs))
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
Use "inception-to-date TWR" when explaining ITD TWR.
If asked to compare two sectors or categories, call the relevant breakdown tool once and state the comparison clearly.
If the user's question is a follow-up with no clear subject, use the conversation history to infer the topic or ask for clarification."""


_SPECIFIC_DATE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|november|december)"
    r"\s+\d{1,2},?\s+\d{4}|\d{1,2}:\d{2}\s*(?:am|pm)?",
    re.IGNORECASE,
)


async def handle_task(task: A2ATask) -> A2ATask:
    user_msg = task.messages[-1].content if task.messages else ""
    history = [{"role": m.role, "content": m.content} for m in task.messages[:-1]]

    with trace_span("financial_agent", task_id=task.task_id):
        if _is_followup_without_context(user_msg, history):
            return task.succeed(
                "Could you clarify what you'd like to know? For example, are you asking about a "
                "portfolio metric, a deal, or a geographic allocation?",
                {"tools_called": []},
            )

        if _SPECIFIC_DATE_RE.search(user_msg) and "return" in user_msg.lower():
            return task.succeed(
                "I don't have portfolio return data at that specific date and time. "
                "I can provide overall performance metrics like TWR, IRR, annualized return, "
                "or volatility. Would you like any of those?",
                {"tools_called": []},
            )

        # 1. Select and call tools
        tool_calls = _pick_tools(user_msg)
        tool_outputs: list[str] = []
        for tool_name, kwargs in tool_calls:
            result = await registry.call(tool_name, **kwargs)
            if result.ok:
                tool_outputs.append(f"[{tool_name}]\n{result.content}")

        tool_context = "\n\n".join(tool_outputs)

        # 2. Compose grounded answer with LLM, including conversation history for follow-ups
        history = "\n".join(
            f"{m.role}: {m.content}" for m in task.messages[:-1] if m.content.strip()
        )
        history_section = f"Conversation history:\n{history}\n\n" if history else ""
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"{history_section}"
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
