"""Tests for the regression detection module."""

from swarm_qa.models import ChannelResult, RunReport, ScenarioResult, Score, TestCase
from swarm_qa.regression import compare_runs


def _case(intent: str = "portfolio_aum") -> TestCase:
    return TestCase(id="T01", intent=intent, type="nominal", input="What is my AUM?")


def _scenario(
    intent: str = "portfolio_aum",
    channel: str = "api",
    verdict: str = "PASS",
    score: float = 4.0,
    latency: float = 500.0,
) -> ScenarioResult:
    return ScenarioResult(
        test_case=_case(intent),
        results={channel: ChannelResult(channel=channel, actual="reply", latency_ms=latency)},
        scores={
            channel: Score(
                pertinence=score,
                exactitude=score,
                coherence=score,
                verdict=verdict,
            )
        },
    )


def _run(run_id: str, version: str, scenarios: list[ScenarioResult]) -> RunReport:
    return RunReport(run_id=run_id, sut_version=version, channels=["api"], scenarios=scenarios)


def test_no_regression_identical_runs():
    base = _run("base", "v1", [_scenario()])
    cand = _run("cand", "v2", [_scenario()])
    reg = compare_runs(base, cand)
    assert not reg.has_regressions
    assert reg.flips == []


def test_pass_to_fail_flip():
    base = _run("base", "v1", [_scenario(verdict="PASS", score=4.0)])
    cand = _run("cand", "v2", [_scenario(verdict="FAIL", score=1.0)])
    reg = compare_runs(base, cand)
    assert reg.has_regressions
    assert len(reg.flips) == 1
    assert reg.flips[0].intent == "portfolio_aum"
    assert reg.flips[0].is_flip


def test_score_drop_no_flip():
    base = _run("base", "v1", [_scenario(verdict="PASS", score=4.5)])
    cand = _run("cand", "v2", [_scenario(verdict="PASS", score=3.5)])
    reg = compare_runs(base, cand, score_drop_threshold=0.5)
    assert reg.has_regressions
    assert len(reg.score_drops) == 1
    assert reg.score_drops[0].score_delta == -1.0


def test_latency_spike():
    base = _run("base", "v1", [_scenario(latency=1000.0)])
    cand = _run("cand", "v2", [_scenario(latency=2000.0)])
    reg = compare_runs(base, cand, latency_spike_pct=50.0)
    assert reg.has_regressions
    assert len(reg.latency_spikes) == 1
    assert reg.latency_spikes[0].latency_delta_ms == 1000.0


def test_unmatched_scenarios_ignored():
    base = _run("base", "v1", [_scenario(intent="greeting")])
    cand = _run("cand", "v2", [_scenario(intent="doc_lookup")])
    reg = compare_runs(base, cand)
    assert not reg.has_regressions
    assert reg.diffs == []
