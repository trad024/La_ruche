"""
Executor Agent — runs a test case on a given channel (deck slides 8, 14, 16).

The deck's "code-based" philosophy: for Web/Mobile the SLM generates a whole Playwright/
Appium script per scenario (added in Phases C/D). The API channel is direct httpx. This
module is the dispatcher; channel runners live under ``swarm_qa.channels`` and are imported
lazily so an API-only run needs neither Playwright nor Appium installed.
"""

from __future__ import annotations

from swarm import Agent

from swarm_qa.channels.api_channel import run_api_test
from swarm_qa.config import settings
from swarm_qa.models import Channel, ChannelResult, TestCase

EXECUTOR_INSTRUCTIONS = (
    "You are a test executor. You receive JSON test cases and run each one on its target "
    "channel (api/web/mobile), capturing the agent's reply, latency and status. For web and "
    "mobile you write a Playwright/Appium script for the scenario. When all results are "
    "collected, hand off to the Evaluator."
)


def build_executor_agent(handoff=None) -> Agent:
    funcs = [handoff] if handoff else []
    return Agent(
        name="Executor",
        model=settings.model_executor,
        instructions=EXECUTOR_INSTRUCTIONS,
        functions=funcs,
    )


def execute(test_case: TestCase, channel: Channel) -> ChannelResult:
    """Run one test case on one channel and return the raw result."""
    if channel == "api":
        return run_api_test(test_case.input)
    if channel == "web":
        from swarm_qa.channels.web_channel import run_web_test  # lazy: needs playwright

        return run_web_test(test_case)
    if channel == "mobile":
        from swarm_qa.channels.mobile_channel import run_mobile_test  # lazy: needs appium

        return run_mobile_test(test_case)
    raise ValueError(f"unknown channel: {channel}")
