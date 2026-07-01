"""
Regression detection — compare two RunReport JSONs (deck slide 21 success criterion).

Finds PASS→FAIL flips, score drops, and latency regressions between a baseline and a
candidate run. Emits a structured diff that the backoffice and CLI can render.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from swarm_qa.models import Channel, RunReport, Score


@dataclass
class ScenarioDiff:
    intent: str
    channel: Channel
    baseline_verdict: str
    candidate_verdict: str
    score_delta: float
    latency_delta_ms: float
    is_flip: bool = False
    is_score_drop: bool = False
    is_latency_spike: bool = False


@dataclass
class RegressionReport:
    baseline_id: str
    candidate_id: str
    baseline_version: str
    candidate_version: str
    diffs: list[ScenarioDiff] = field(default_factory=list)

    @property
    def flips(self) -> list[ScenarioDiff]:
        return [d for d in self.diffs if d.is_flip]

    @property
    def score_drops(self) -> list[ScenarioDiff]:
        return [d for d in self.diffs if d.is_score_drop]

    @property
    def latency_spikes(self) -> list[ScenarioDiff]:
        return [d for d in self.diffs if d.is_latency_spike]

    @property
    def has_regressions(self) -> bool:
        return bool(self.flips or self.score_drops or self.latency_spikes)


def compare_runs(
    baseline: RunReport,
    candidate: RunReport,
    score_drop_threshold: float = 0.5,
    latency_spike_pct: float = 50.0,
) -> RegressionReport:
    """Diff two runs — flag flips, score drops, and latency spikes."""
    reg = RegressionReport(
        baseline_id=baseline.run_id,
        candidate_id=candidate.run_id,
        baseline_version=baseline.sut_version,
        candidate_version=candidate.sut_version,
    )

    base_map: dict[tuple[str, Channel], tuple[Score, float]] = {}
    for sc in baseline.scenarios:
        for ch, score in sc.scores.items():
            res = sc.results.get(ch)
            latency = res.latency_ms if res else 0.0
            base_map[(sc.test_case.intent, ch)] = (score, latency)

    for sc in candidate.scenarios:
        for ch, score in sc.scores.items():
            key = (sc.test_case.intent, ch)
            if key not in base_map:
                continue
            base_score, base_latency = base_map[key]
            res = sc.results.get(ch)
            cand_latency = res.latency_ms if res else 0.0

            score_delta = round(score.mean - base_score.mean, 2)
            latency_delta = round(cand_latency - base_latency, 1)
            is_flip = base_score.verdict == "PASS" and score.verdict == "FAIL"
            is_score_drop = score_delta <= -score_drop_threshold
            is_latency_spike = (
                base_latency > 0
                and latency_delta > 0
                and (latency_delta / base_latency) * 100 >= latency_spike_pct
            )

            if is_flip or is_score_drop or is_latency_spike:
                reg.diffs.append(
                    ScenarioDiff(
                        intent=sc.test_case.intent,
                        channel=ch,
                        baseline_verdict=base_score.verdict,
                        candidate_verdict=score.verdict,
                        score_delta=score_delta,
                        latency_delta_ms=latency_delta,
                        is_flip=is_flip,
                        is_score_drop=is_score_drop,
                        is_latency_spike=is_latency_spike,
                    )
                )

    return reg


def render_regression_md(reg: RegressionReport) -> str:
    lines = [
        "# Regression Report",
        "",
        f"- **Baseline:** `{reg.baseline_id}` (v{reg.baseline_version})",
        f"- **Candidate:** `{reg.candidate_id}` (v{reg.candidate_version})",
        f"- **Regressions found:** {'Yes' if reg.has_regressions else 'No'}",
        "",
    ]

    if reg.flips:
        lines += ["## PASS → FAIL flips", ""]
        for d in reg.flips:
            lines.append(f"- **{d.intent}** [{d.channel}] — score Δ {d.score_delta:+.2f}")

    if reg.score_drops:
        non_flip_drops = [d for d in reg.score_drops if not d.is_flip]
        if non_flip_drops:
            lines += ["", "## Score drops (still passing)", ""]
            for d in non_flip_drops:
                lines.append(f"- **{d.intent}** [{d.channel}] — score Δ {d.score_delta:+.2f}")

    if reg.latency_spikes:
        lines += ["", "## Latency spikes", ""]
        for d in reg.latency_spikes:
            lines.append(f"- **{d.intent}** [{d.channel}] — +{d.latency_delta_ms:.0f}ms")

    if not reg.has_regressions:
        lines += ["", "No regressions detected between the two runs."]

    return "\n".join(lines) + "\n"


def load_run(path: Path) -> RunReport:
    return RunReport.model_validate_json(path.read_text(encoding="utf-8"))


def compare_from_files(baseline_path: Path, candidate_path: Path) -> RegressionReport:
    return compare_runs(load_run(baseline_path), load_run(candidate_path))
