"""Typed data models shared across the testing pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, Field

Channel = Literal["api", "web", "mobile"]
CaseType = Literal["nominal", "limit", "adversarial"]
Verdict = Literal["PASS", "FAIL"]


class TestCase(BaseModel):
    """A single scenario to run against the agent under test."""

    __test__: ClassVar[bool] = False  # not a pytest test class

    id: str
    intent: str  # e.g. "portfolio_aum", "empty_input"
    type: CaseType = "nominal"
    input: str  # the user message sent to the agent
    expected: str = ""  # reference answer / expectation (free text)
    channels: list[Channel] = Field(default_factory=lambda: ["api"])


class ChannelResult(BaseModel):
    """Raw result of executing one test case on one channel."""

    channel: Channel
    actual: str = ""  # the agent's reply text
    status_code: int | None = None  # HTTP status (api) or synthetic code
    latency_ms: float = 0.0  # total round-trip
    ttft_ms: float | None = None  # time-to-first-token (api SSE)
    timed_out: bool = False
    crashed: bool = False  # UI crash / spinner-forever / 5xx
    screenshot: str = ""  # path, for web/mobile
    error: str = ""


class Score(BaseModel):
    """Evaluator output for one channel result (deck slide 19 JSON shape)."""

    pertinence: float = 0.0  # 1-5 relevance to intent
    exactitude: float = 0.0  # 1-5 factual correctness
    coherence: float = 0.0  # 1-5 context coherence
    format_ok: bool = True
    hallucination: bool = False
    verdict: Verdict = "FAIL"
    reason: str = ""

    @property
    def mean(self) -> float:
        return round((self.pertinence + self.exactitude + self.coherence) / 3, 2)


class ScenarioResult(BaseModel):
    """A test case + its per-channel results + per-channel scores."""

    test_case: TestCase
    results: dict[Channel, ChannelResult] = Field(default_factory=dict)
    scores: dict[Channel, Score] = Field(default_factory=dict)
    divergence: float | None = None  # web<->mobile text divergence (0..1)


class RunReport(BaseModel):
    """A full pipeline run — the unit that gets diffed for regressions."""

    run_id: str
    sut_version: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    channels: list[Channel] = Field(default_factory=list)
    scenarios: list[ScenarioResult] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(len(s.scores) for s in self.scenarios)

    @property
    def passed(self) -> int:
        return sum(1 for s in self.scenarios for v in s.scores.values() if v.verdict == "PASS")

    @property
    def pass_rate(self) -> float:
        return round(100 * self.passed / self.total, 1) if self.total else 0.0
