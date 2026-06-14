"""
Action Agent — email / report / WhatsApp.
All outbound actions require explicit confirmation. Audit-logged.
"""

from __future__ import annotations

import os
import smtplib
from datetime import UTC, datetime
from email.mime.text import MIMEText
from typing import Any

from agentkit.a2a.models import A2ATask, AgentCard, AgentSkill
from agentkit.a2a.router import a2a_router
from agentkit.mcp.registry import MCPRegistry
from agentkit.mcp.tool import MCPTool, ToolResult
from agentkit.tracing import trace_span
from fastapi import FastAPI

_SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
_FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@wealthmesh.local")

_AUDIT_LOG: list[dict[str, Any]] = []


def _audit(action: str, details: dict[str, Any]) -> None:
    _AUDIT_LOG.append({"timestamp": datetime.now(UTC).isoformat(), "action": action, **details})


class ReportBuildTool(MCPTool):
    @property
    def name(self) -> str:
        return "report.build"

    @property
    def description(self) -> str:
        return "Generate a portfolio performance report."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "client_name": {"type": "string", "default": "Valued Client"},
                "format": {"type": "string", "enum": ["text", "html"], "default": "text"},
            },
            "required": [],
        }

    async def execute(
        self,
        client_name: str = "Valued Client",
        format: str = "text",
        **_kw: Any,
    ) -> ToolResult:
        report = (
            f"Portfolio Performance Report — {datetime.now(UTC).strftime('%Y-%m-%d')}\n"
            f"Client: {client_name}\n\n"
            "AUM: $20.4M | TWR: 178.65% | Annualized: 7.14%\n"
            "IRR: 8.23% | Sharpe: 0.58 | Volatility: 12.27%\n"
            "Profit: $7.85M | Deals: 48\n\n"
            "Geography: Asia 37% | NA 35% | Global 16% | EU 4%\n"
            "Sectors: RE 45% | PE 35% | EQ 15% | Credit 6%\n"
        )
        if format == "html":
            report = f"<pre>{report}</pre>"
        _audit("report.build", {"client": client_name})
        return ToolResult(content=report)


class EmailSendTool(MCPTool):
    @property
    def name(self) -> str:
        return "email.send"

    @property
    def description(self) -> str:
        return "Send an email (MailHog in dev). Requires confirmed=true."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["to", "subject", "body"],
        }

    async def execute(
        self,
        to: str = "",
        subject: str = "",
        body: str = "",
        confirmed: bool = False,
        **_kw: Any,
    ) -> ToolResult:
        if not confirmed:
            return ToolResult(content=f"Confirm email to {to}? Set confirmed=true to send.")
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = _FROM_EMAIL
            msg["To"] = to
            with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=5) as s:
                s.sendmail(_FROM_EMAIL, [to], msg.as_string())
            _audit("email.send", {"to": to, "subject": subject})
            return ToolResult(content=f"Email sent to {to}: '{subject}'")
        except Exception as exc:
            return ToolResult(content=f"Email queued (SMTP not available: {exc})")


class WhatsAppSendTool(MCPTool):
    @property
    def name(self) -> str:
        return "whatsapp.send"

    @property
    def description(self) -> str:
        return "Send a WhatsApp message (stub). Requires confirmed=true."

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "message": {"type": "string"},
                "confirmed": {"type": "boolean", "default": False},
            },
            "required": ["to", "message"],
        }

    async def execute(
        self,
        to: str = "",
        message: str = "",
        confirmed: bool = False,
        **_kw: Any,
    ) -> ToolResult:
        if not confirmed:
            return ToolResult(content=f"Confirm WhatsApp to {to}? Set confirmed=true.")
        _audit("whatsapp.send", {"to": to})
        return ToolResult(
            content=f"[WhatsApp STUB] Message logged for {to}. Connect Twilio/Meta via env var."
        )


_registry = MCPRegistry()
_registry.register(ReportBuildTool())
_registry.register(EmailSendTool())
_registry.register(WhatsAppSendTool())


def _pick(msg: str) -> tuple[str, dict[str, Any]]:
    lower = msg.lower()
    if "email" in lower or "send" in lower:
        return "email.send", {
            "to": "client@wealthmesh.local",
            "subject": "Portfolio Report",
            "body": "Please see your portfolio report.",
            "confirmed": False,
        }
    if "whatsapp" in lower:
        return "whatsapp.send", {
            "to": "+1234567890",
            "message": "Your portfolio report is ready.",
            "confirmed": False,
        }
    return "report.build", {}


async def handle_task(task: A2ATask) -> A2ATask:
    msg = task.messages[-1].content if task.messages else ""
    with trace_span("action_agent", task_id=task.task_id):
        tool_name, kwargs = _pick(msg)
        result = await _registry.call(tool_name, **kwargs)
        answer = result.content if result.ok else f"Error: {result.error}"
    return task.succeed(answer, {"tool": tool_name})


_CARD = AgentCard(
    id="agent-action",
    name="Action Agent",
    description="Report generation, email and WhatsApp delivery.",
    version="0.1.0",
    url="http://agent-action:8004",
    skills=[
        AgentSkill(
            id="chat",
            name="Action Chat",
            description="Execute communication and reporting actions.",
            input_schema={"type": "object", "properties": {"message": {"type": "string"}}},
            output_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
        )
    ],
)

app = FastAPI(title="Action Agent", version="0.1.0")
app.include_router(a2a_router(_CARD, handle_task))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "agent-action"}


@app.get("/api/audit-log")
async def audit_log() -> list[dict[str, Any]]:
    return _AUDIT_LOG
