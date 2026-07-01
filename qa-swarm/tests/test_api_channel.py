"""API channel — SSE parsing, latency, and crash/timeout flags (mocked SUT)."""

from __future__ import annotations

import httpx
import respx
from swarm_qa.channels.api_channel import run_api_test
from swarm_qa.config import settings

_SSE = b'data: {"token": "Your AUM is "}\n\n' b'data: {"token": "$20.4M."}\n\n' b"data: [DONE]\n\n"


@respx.mock
def test_api_channel_parses_sse():
    respx.post(settings.sut_chat_url).mock(
        return_value=httpx.Response(
            200, content=_SSE, headers={"content-type": "text/event-stream"}
        )
    )
    res = run_api_test("What is my AUM?")
    assert res.status_code == 200
    assert res.actual == "Your AUM is $20.4M."
    assert res.timed_out is False
    assert res.crashed is False
    assert res.ttft_ms is not None
    assert res.latency_ms >= 0


@respx.mock
def test_api_channel_5xx_is_crash():
    respx.post(settings.sut_chat_url).mock(
        return_value=httpx.Response(500, json={"detail": "boom"})
    )
    res = run_api_test("x")
    assert res.crashed is True
    assert res.status_code == 500


@respx.mock
def test_api_channel_4xx_is_not_crash():
    respx.post(settings.sut_chat_url).mock(
        return_value=httpx.Response(400, json={"detail": "blocked by guardrail"})
    )
    res = run_api_test("")
    assert res.crashed is False
    assert res.status_code == 400
    assert "guardrail" in res.actual


@respx.mock
def test_api_channel_timeout():
    respx.post(settings.sut_chat_url).mock(side_effect=httpx.TimeoutException("slow"))
    res = run_api_test("x")
    assert res.timed_out is True
