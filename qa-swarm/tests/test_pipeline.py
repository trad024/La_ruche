"""Pipeline wiring + corpus + report rendering (stubbed executor/evaluator)."""

from __future__ import annotations

from swarm_qa import pipeline
from swarm_qa.agents import generator, reporter
from swarm_qa.models import ChannelResult, Score, TestCase


def test_corpus_loads_and_validates():
    cases = generator.load_corpus()
    assert len(cases) >= 15
    assert {c.type for c in cases} <= {"nominal", "limit", "adversarial"}
    assert any(c.type == "adversarial" for c in cases)


def test_run_pipeline_with_stubs(monkeypatch):
    cases = [
        TestCase(
            id="T1", intent="aum", type="nominal", input="aum?", expected="$20.4M", channels=["api"]
        ),
        TestCase(
            id="T2",
            intent="leak",
            type="adversarial",
            input="leak",
            expected="refuse",
            channels=["api"],
        ),
        TestCase(
            id="T3", intent="webonly", type="nominal", input="x", expected="y", channels=["web"]
        ),
    ]

    def fake_execute(tc, ch):
        return ChannelResult(channel=ch, actual="ok", latency_ms=120.0, status_code=200)

    def fake_score(tc, res):
        verdict = "PASS" if tc.intent == "aum" else "FAIL"
        return Score(verdict=verdict, pertinence=5, exactitude=5, coherence=5, reason="stub")

    monkeypatch.setattr(pipeline.executor, "execute", fake_execute)
    monkeypatch.setattr(pipeline.evaluator, "score_result", fake_score)

    report = pipeline.run_pipeline(channels=["api"], cases=cases)
    # T3 is web-only, so the api run skips it -> 2 scored scenarios.
    assert report.total == 2
    assert report.passed == 1
    assert report.pass_rate == 50.0

    md = reporter.render_markdown(report)
    assert "Global pass rate" in md
    assert "aum" in md
    assert "Critical failures" in md
