"""
API channel — the fastest test surface (deck slide 8, "Canal 1 — API REST").

Sends the scenario's user message to the agent under test at `POST /api/chat`, parses
the Server-Sent-Events stream, and records latency, time-to-first-token, HTTP status,
timeout and crash flags. No UI, no LLM — pure httpx, milliseconds.
"""

from __future__ import annotations

import json
import time

import httpx

from swarm_qa.config import settings
from swarm_qa.models import ChannelResult


def run_api_test(input_text: str, conversation_id: str = "") -> ChannelResult:
    """Run one scenario over the API channel and return a raw ChannelResult."""
    payload = {
        "message": input_text,
        "display_message": input_text,
        "conversation_id": conversation_id,
        "mode": "instant",
    }
    headers = {"Authorization": f"Bearer {settings.sut_dev_token}"}

    start = time.perf_counter()
    tokens: list[str] = []
    ttft_ms: float | None = None
    status_code: int | None = None
    timed_out = False
    crashed = False
    error = ""

    try:
        with (
            httpx.Client(timeout=settings.timeout_seconds) as client,
            client.stream("POST", settings.sut_chat_url, json=payload, headers=headers) as r,
        ):
            status_code = r.status_code
            if r.status_code != 200:
                # 4xx (e.g. guardrail rejection) is a real, judgeable reply;
                # only 5xx counts as a crash.
                body = r.read().decode("utf-8", errors="replace")
                crashed = r.status_code >= 500
                try:
                    error = json.loads(body).get("detail", "")[:500]
                except (json.JSONDecodeError, AttributeError):
                    error = body[:500]
            else:
                for line in r.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        obj = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    token = obj.get("token") or obj.get("reasoning") or ""
                    if token:
                        if ttft_ms is None:
                            ttft_ms = round((time.perf_counter() - start) * 1000, 1)
                        tokens.append(token)
    except httpx.TimeoutException:
        timed_out = True
        error = f"timeout after {settings.timeout_seconds}s"
    except httpx.HTTPError as exc:
        crashed = True
        error = f"{type(exc).__name__}: {exc}"

    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    return ChannelResult(
        channel="api",
        actual="".join(tokens).strip() or error,
        status_code=status_code,
        latency_ms=latency_ms,
        ttft_ms=ttft_ms,
        timed_out=timed_out,
        crashed=crashed,
        error=error,
    )
