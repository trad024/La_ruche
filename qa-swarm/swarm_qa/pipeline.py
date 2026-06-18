"""
Pipeline driver — Generator -> Executor -> Evaluator -> Reporter.

A deterministic driver loops the versioned corpus across the requested channels, executes
each case, scores it, and persists a RunReport (the unit that gets diffed for regressions).
This is the reliable path for a full 50+ scenario run; ``agentic_demo`` (added alongside)
shows the pure-Swarm handoff flow for the live demo.

Usage:
    uv run python -m swarm_qa.pipeline --channel api
    uv run python -m swarm_qa.pipeline --channel api web --limit 5 --version baseline
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from swarm_qa.agents import evaluator, executor, generator, reporter
from swarm_qa.config import settings
from swarm_qa.models import Channel, RunReport, ScenarioResult, TestCase
from swarm_qa.scoring.metrics import compute_divergence


def run_pipeline(
    channels: list[Channel],
    cases: list[TestCase] | None = None,
    limit: int | None = None,
    sut_version: str | None = None,
) -> RunReport:
    cases = cases if cases is not None else generator.load_corpus()
    if limit:
        cases = cases[:limit]

    run_id = f"run_{datetime.now(UTC):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}"
    report = RunReport(
        run_id=run_id,
        sut_version=sut_version or settings.sut_version,
        channels=channels,
    )

    for case in cases:
        targets = [c for c in channels if c in case.channels]
        if not targets:
            continue
        sr = ScenarioResult(test_case=case)
        for ch in targets:
            result = executor.execute(case, ch)
            score = evaluator.score_result(case, result)
            sr.results[ch] = result
            sr.scores[ch] = score
            print(
                f"  [{ch:6}] {case.intent:24} {score.verdict:4} "
                f"score={score.mean:.1f} {result.latency_ms/1000:5.1f}s  {score.reason[:50]}"
            )
        sr.divergence = compute_divergence(sr)
        if sr.divergence is not None and sr.divergence > settings.divergence_threshold:
            print(
                f"  [web<->mobile] {case.intent:24} DIVERGENCE {sr.divergence:.0%} > "
                f"{settings.divergence_threshold:.0%} (FAIL flag)"
            )
        report.scenarios.append(sr)

    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the autonomous testing pipeline.")
    parser.add_argument("--channel", nargs="+", default=["api"], choices=["api", "web", "mobile"])
    parser.add_argument("--limit", type=int, default=None, help="only run the first N cases")
    parser.add_argument("--version", default=None, help="SUT version label for this run")
    args = parser.parse_args()

    print(f"Running pipeline on channels={args.channel} against {settings.sut_api_url}")
    report = run_pipeline(channels=args.channel, limit=args.limit, sut_version=args.version)
    run_dir = reporter.save_report(report)
    print(f"\nPass rate: {report.pass_rate}% ({report.passed}/{report.total})")
    print(f"Report:    {run_dir / 'report.md'}")


if __name__ == "__main__":
    main()
