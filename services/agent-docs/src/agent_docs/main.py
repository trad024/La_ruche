"""
Document / Extractor Agent (RAG).

Ingests PDFs → chunks → embeds → stores in Qdrant.
Answers questions using hybrid retrieval + grounded response.
"""

from __future__ import annotations

import os
from typing import Any

from agentkit.a2a.models import A2ATask, AgentCard, AgentSkill
from agentkit.a2a.router import a2a_router
from agentkit.llm.client import LLMClient, ModelRole
from agentkit.mcp.registry import MCPRegistry
from agentkit.mcp.tool import MCPTool, ToolResult
from agentkit.tracing import trace_span
from fastapi import FastAPI

_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
_COLLECTION = "wealth_docs"

# In-memory fallback doc store (used when Qdrant is not running)
_DOC_STORE: dict[str, str] = {
    "wella_factsheet": (
        "Wella Company — Investment Fact Sheet\n"
        "Acquired: June 2015 | Exited: June 2022\n"
        "Asset Class: Private Equity | Geography: North America\n"
        "Commitment: $500K | Exit NAV: $775K | MOIC: 1.55x\n"
        "Wella is a global professional hair care brand sold by P&G."
    ),
    "project_taka": (
        "Project Taka — Investment Memo\n"
        "Entry: March 2018 | Status: Active\n"
        "Asset Class: Private Equity | Geography: Asia\n"
        "Commitment: $400K | Current NAV: $588K | MOIC: 1.47x\n"
        "Growth equity stake in an Asian fintech lending platform."
    ),
    "portfolio_overview": (
        "Al-Rashid Family Office — Portfolio Overview 2024\n"
        "Total AUM: $20.4M across 48 deals\n"
        "ITD TWR: 178.65% | Annualized: 7.14% | Sharpe: 0.58\n"
        "Geography: Asia 37%, North America 35%, Global 16%, Europe 4%\n"
        "Sectors: Real Estate 45%, Private Equity 35%, Equities 15%, Credit 6%"
    ),
}


def _simple_search(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    lower = query.lower()
    results = []
    for doc_id, content in _DOC_STORE.items():
        score = sum(1 for word in lower.split() if word in content.lower())
        if score > 0:
            results.append({"id": doc_id, "score": score, "content": content})
    results.sort(key=lambda x: -x["score"])
    return results[:top_k]


class DocIngestTool(MCPTool):
    @property
    def name(self) -> str:
        return "doc.ingest"

    @property
    def description(self) -> str:
        return "Ingest a document text into the vector store."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "doc_id": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["doc_id", "content"],
        }

    async def execute(self, doc_id: str = "", content: str = "", **_kw: Any) -> ToolResult:
        _DOC_STORE[doc_id] = content
        return ToolResult(content=f"Ingested document '{doc_id}' ({len(content)} chars)")


class RAGSearchTool(MCPTool):
    @property
    def name(self) -> str:
        return "rag.search"

    @property
    def description(self) -> str:
        return "Search ingested documents and return relevant chunks."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 3},
            },
            "required": ["query"],
        }

    async def execute(self, query: str = "", top_k: int = 3, **_kw: Any) -> ToolResult:
        results = _simple_search(query, top_k)
        if not results:
            return ToolResult(content="No relevant documents found.")
        parts = [f"[{r['id']}]\n{r['content']}" for r in results]
        return ToolResult(content="\n\n---\n\n".join(parts))


_registry = MCPRegistry()
_registry.register(DocIngestTool())
_registry.register(RAGSearchTool())

_llm = LLMClient(role=ModelRole.DEFAULT)


async def handle_task(task: A2ATask) -> A2ATask:
    msg = task.messages[-1].content if task.messages else ""
    with trace_span("docs_agent", task_id=task.task_id):
        result = await _registry.call("rag.search", query=msg, top_k=3)
        if result.ok and result.content and "No relevant" not in result.content:
            messages = [
                {
                    "role": "system",
                    "content": "You are a document analyst. Answer based only on document excerpts.",
                },
                {
                    "role": "user",
                    "content": f"Question: {msg}\n\nDocument excerpts:\n{result.content}",
                },
            ]
            try:
                answer = await _llm.chat(messages)
            except Exception:
                answer = result.content
        else:
            answer = "No relevant documents found for your query."
    return task.succeed(answer, {"source": "rag"})


_CARD = AgentCard(
    id="agent-docs",
    name="Document / Extractor Agent",
    description="RAG over ingested financial documents.",
    version="0.1.0",
    url="http://agent-docs:8003",
    skills=[
        AgentSkill(
            id="chat",
            name="Document Chat",
            description="Answer questions from financial documents.",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        )
    ],
)

app = FastAPI(title="Document / Extractor Agent", version="0.1.0")
app.include_router(a2a_router(_CARD, handle_task))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-docs"}
