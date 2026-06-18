"""Action agent tests — no real SMTP required."""

from __future__ import annotations

import agent_action.main as action_main
from agent_action.main import (
    EmailSendTool,
    ReportBuildTool,
    WhatsAppSendTool,
    _extract_content_to_send,
    _pick,
    app,
)
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


async def test_email_confirmed_uses_smtp(monkeypatch):
    sent: dict[str, object] = {}

    class FakeSmtp:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def sendmail(self, from_addr: str, to_addrs: list[str], message: str) -> None:
            sent["from"] = from_addr
            sent["to"] = to_addrs
            sent["message"] = message

    monkeypatch.setattr(action_main, "_smtp_hosts", lambda: ["smtp.test"])
    monkeypatch.setattr(action_main, "_smtp_connect", lambda _host: FakeSmtp())
    monkeypatch.setattr(action_main, "_is_local_capture", lambda _host: False)

    t = EmailSendTool()
    r = await t.execute(to="x@x.com", subject="Hi", body="body", confirmed=True)
    assert r.ok
    assert "Email sent to x@x.com" in r.content
    assert sent["from"] == action_main._FROM_EMAIL
    assert sent["to"] == ["x@x.com"]
    assert "Content-Type: text/html" in str(sent["message"])


async def test_whatsapp_stub():
    t = WhatsAppSendTool()
    r = await t.execute(to="+1234567890", message="Hello", confirmed=True)
    assert r.ok
    assert "STUB" in r.content or "logged" in r.content.lower()


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_pick_uses_email_from_user_message():
    tool, kwargs = _pick("send those informations to my mail, amine.manai@esprit.tn")
    assert tool == "email.send"
    assert kwargs["to"] == "amine.manai@esprit.tn"
    assert kwargs["confirmed"] is False


def test_pick_marks_email_confirmed():
    tool, kwargs = _pick("send those informations to my mail, amine.manai@esprit.tn confirmed=true")
    assert tool == "email.send"
    assert kwargs["to"] == "amine.manai@esprit.tn"
    assert kwargs["confirmed"] is True


def test_pick_uses_content_to_send_as_email_body():
    message = (
        "send this to my mail amine.manai@esprit.tn\n\n"
        "Content to send:\nPortfolio AUM is $20.4M.\n\n"
        "Response format: answer directly.\nconfirmed=true"
    )
    tool, kwargs = _pick(message)
    assert tool == "email.send"
    assert kwargs["to"] == "amine.manai@esprit.tn"
    assert kwargs["subject"] == "LaRuche portfolio summary"
    assert kwargs["body"] == "Portfolio AUM is $20.4M."
    assert kwargs["confirmed"] is True


def test_extract_content_to_send_stops_before_hidden_instructions():
    message = (
        "send it\n\nContent to send:\nVisible answer\n\n"
        "Advisor style: You are LaRuche.\nconfirmed=true"
    )
    assert _extract_content_to_send(message) == "Visible answer"


def test_pick_routes_whatsapp_before_generic_send():
    tool, kwargs = _pick("send whatsapp to +216 55 123 456 confirmed=true")
    assert tool == "whatsapp.send"
    assert kwargs["to"] == "+216 55 123 456"
    assert kwargs["confirmed"] is True


def test_audit_log():
    r = client.get("/api/audit-log")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
