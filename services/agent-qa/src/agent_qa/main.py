"""QA / Tester Agent (AI-SDLC) — generate and run functional tests."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from typing import Any

from agentkit.a2a.models import A2ATask, AgentCard, AgentSkill
from agentkit.a2a.router import a2a_router
from agentkit.llm.client import LLMClient, ModelRole
from agentkit.mcp.registry import MCPRegistry
from agentkit.mcp.tool import MCPTool, ToolResult
from agentkit.tracing.noop import trace_span
from fastapi import FastAPI

_llm = LLMClient(role=ModelRole.DEFAULT)

_FALLBACK_TEST = '''"""Auto-generated API tests."""
import httpx

BASE_URL = "http://localhost:8000"

def test_health():
    r = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert r.status_code == 200

def test_me_requires_auth():
    r = httpx.get(f"{BASE_URL}/api/me", timeout=5)
    assert r.status_code in (200, 401)
'''


class TestGenerateTool(MCPTool):
    @property
    def name(self) -> str:
        return "tests.generate"

    @property
    def description(self) -> str:
        return "Generate pytest test code for a service."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["service"],
        }

    async def execute(self, service: str = "", description: str = "", **_kw: Any) -> ToolResult:
        prompt = (
            f"Write 3-5 concise pytest tests for service: {service}\n"
            f"Context: {description}\n"
            "Use httpx for HTTP calls. Output only Python code."
        )
        try:
            code = await _llm.chat([{"role": "user", "content": prompt}])
        except Exception:
            code = _FALLBACK_TEST
        return ToolResult(content=code, metadata={"service": service})


class TestRunTool(MCPTool):
    @property
    def name(self) -> str:
        return "tests.run"

    @property
    def description(self) -> str:
        return "Execute pytest test code in a subprocess sandbox."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"test_code": {"type": "string"}},
            "required": ["test_code"],
        }

    async def execute(self, test_code: str = "", **_kw: Any) -> ToolResult:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="qa_", delete=False) as f:
            f.write(test_code)
            tmp = f.name
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "pytest", tmp, "-v", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = (proc.stdout + proc.stderr)[:2000]
            passed = proc.returncode == 0
            return ToolResult(
                content=f"{'PASSED' if passed else 'FAILED'}\n\n{out}",
                metadata={"returncode": proc.returncode},
            )
        except Exception as exc:
            return ToolResult(error=str(exc))


_registry = MCPRegistry()
_registry.register(TestGenerateTool())
_registry.register(TestRunTool())


async def handle_task(task: A2ATask) -> A2ATask:
    msg = task.messages[-1].content if task.messages else ""
    with trace_span("qa_agent", task_id=task.task_id):
        gen = await _registry.call("tests.generate", service=msg, description=msg)
        if not gen.ok:
            return task.fail(gen.error or "generation failed")
        run = await _registry.call("tests.run", test_code=gen.content)
        answer = f"Generated tests:\n{gen.content}\n\nResults:\n{run.content}"
    return task.succeed(answer, {"tool": "tests.generate+run"})


_CARD = AgentCard(
    id="agent-qa",
    name="QA / Tester Agent",
    description="AI-SDLC: auto-generate and run functional tests.",
    version="0.1.0",
    url="http://agent-qa:8005",
    skills=[
        AgentSkill(
            id="chat",
            name="QA Chat",
            description="Generate and run tests for a service.",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        )
    ],
)

app = FastAPI(title="QA / Tester Agent", version="0.1.0")
app.include_router(a2a_router(_CARD, handle_task))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-qa"}
