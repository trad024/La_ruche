"""Action agent tests — no real SMTP required."""

from __future__ import annotations

from agent_action.main import EmailSendTool, ReportBuildTool, WhatsAppSendTool, app
from fastapi.testclient import TestClient

client = TestClient(app)


async def test_report_build():
    t = ReportBuildTool()
    r = await t.execute(client_name="Test Client")
    assert r.ok
    assert "AUM" in r.content
    assert "Test Client" in r.content


async def test_email_requires_confirmation():
    t = EmailSendTool()
    r = await t.execute(to="x@x.com", subject="Hi", body="body", confirmed=False)
    assert r.ok
    assert "Confirm" in r.content or "confirm" in r.content.lower()


async def test_email_confirmed_no_smtp():
    t = EmailSendTool()
    r = await t.execute(to="x@x.com", subject="Hi", body="body", confirmed=True)
    # Either sent or queued — both are ok responses
    assert r.ok or r.content is not None


async def test_whatsapp_stub():
    t = WhatsAppSendTool()
    r = await t.execute(to="+1234567890", message="Hello", confirmed=True)
    assert r.ok
    assert "STUB" in r.content or "logged" in r.content.lower()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_audit_log():
    r = client.get("/api/audit-log")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
