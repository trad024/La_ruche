from __future__ import annotations

from agentkit.a2a.models import AgentCard, AgentSkill
from agentkit.a2a.router import a2a_router
from fastapi import FastAPI

from agent_financial.agent import handle_task

_CARD = AgentCard(
    id="agent-financial",
    name="Financial Assistant",
    description="Conversational portfolio analytics — AUM, TWR, IRR, Sharpe, geo/sector breakdown.",
    version="0.1.0",
    url="http://agent-financial:8001",
    skills=[
        AgentSkill(
            id="chat",
            name="Portfolio Chat",
            description="Answer wealth-management questions from portfolio data.",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        )
    ],
)

app = FastAPI(title="Financial Assistant Agent", version="0.1.0")
app.include_router(a2a_router(_CARD, handle_task))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-financial"}
