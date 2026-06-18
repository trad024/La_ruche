"""
Reporter Agent — consolidates results into a report (deck slides 18 & 20).

Markdown table + global pass rate (Phase B) plus an interactive Plotly HTML dashboard
(Phase E). A Reporter Swarm Agent is also defined for the pure-handoff demo path.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from swarm import Agent

from swarm_qa.config import settings
from swarm_qa.models import RunReport
from swarm_qa.scoring.metrics import availability, channel_latencies, pass_rate_by_type

REPORTER_INSTRUCTIONS = (
    "You are a QA reporter. Given structured test results, produce a concise Markdown report "
    "with a results table (Scenario, Channel, Latency, Score, Hallucination, Verdict), the "
    "global pass rate, and a short analysis of the most critical failures."
)


def build_reporter_agent() -> Agent:
    return Agent(name="Reporter", model=settings.model_reporter, instructions=REPORTER_INSTRUCTIONS)


def render_markdown(report: RunReport) -> str:
    lines: list[str] = [
        f"# Test Report — `{report.run_id}`",
        "",
        f"- **SUT version:** `{report.sut_version}`",
        f"- **Channels:** {', '.join(report.channels)}",
        f"- **Generated:** {report.created_at}",
        f"- **Global pass rate:** **{report.pass_rate}%** ({report.passed}/{report.total})",
        "",
        "| Scenario | Channel | Latency | Score | Halluc. | Verdict |",
        "|---|---|--:|--:|:--:|:--:|",
    ]
    for sc in report.scenarios:
        for ch, score in sc.scores.items():
            res = sc.results.get(ch)
            latency = f"{res.latency_ms / 1000:.1f}s" if res else "—"
            halluc = "Yes" if score.hallucination else "No"
            verdict = "✅ PASS" if score.verdict == "PASS" else "❌ FAIL"
            lines.append(
                f"| {sc.test_case.intent} ({sc.test_case.type}) | {ch} | "
                f"{latency} | {score.mean:.1f} | {halluc} | {verdict} |"
            )

    failures = [
        (sc, ch, score)
        for sc in report.scenarios
        for ch, score in sc.scores.items()
        if score.verdict == "FAIL"
    ]
    if failures:
        lines += ["", "## Critical failures", ""]
        for sc, ch, score in failures:
            lines.append(
                f"- **{sc.test_case.intent}** [{ch}] — {score.reason or 'scored below threshold'}"
            )
    return "\n".join(lines) + "\n"


def render_html(report: RunReport) -> str:
    """Interactive Plotly dashboard (PDF slide 20 deliverable). Returns standalone HTML."""
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError:
        return (
            "<html><body><p>Install the <code>report</code> extra "
            "(<code>uv pip install -e '.[report]'</code>) for the Plotly dashboard.</p></body></html>"
        )

    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Pass rate by type",
            "Avg latency by channel (ms)",
            "Score distribution",
            "Failure breakdown",
        ),
        specs=[[{"type": "bar"}, {"type": "bar"}], [{"type": "histogram"}, {"type": "pie"}]],
        vertical_spacing=0.15,
        horizontal_spacing=0.12,
    )

    pr = pass_rate_by_type(report)
    fig.add_trace(
        go.Bar(
            x=list(pr.keys()),
            y=list(pr.values()),
            marker_color=["#22c55e", "#eab308", "#ef4444"][: len(pr)],
            text=[f"{v:.0f}%" for v in pr.values()],
            textposition="outside",
        ),
        row=1,
        col=1,
    )
    fig.update_yaxes(range=[0, 105], row=1, col=1)

    lat = channel_latencies(report)
    fig.add_trace(
        go.Bar(
            x=list(lat.keys()),
            y=list(lat.values()),
            marker_color="#6366f1",
            text=[f"{v:.0f}" for v in lat.values()],
            textposition="outside",
        ),
        row=1,
        col=2,
    )

    means = [s.mean for sc in report.scenarios for s in sc.scores.values()]
    fig.add_trace(
        go.Histogram(
            x=means,
            nbinsx=10,
            marker_color="#8b5cf6",
        ),
        row=2,
        col=1,
    )
    fig.update_xaxes(title_text="Mean score (1-5)", row=2, col=1)

    reasons: Counter[str] = Counter()
    for sc in report.scenarios:
        for score in sc.scores.values():
            if score.verdict == "FAIL":
                tag = (
                    "hallucination"
                    if score.hallucination
                    else ("low score" if score.mean < settings.min_score_pass else "other")
                )
                reasons[tag] += 1
    if reasons:
        fig.add_trace(
            go.Pie(
                labels=list(reasons.keys()),
                values=list(reasons.values()),
                marker_colors=["#ef4444", "#f97316", "#64748b"][: len(reasons)],
            ),
            row=2,
            col=2,
        )
    else:
        fig.add_annotation(text="No failures", row=2, col=2, showarrow=False)

    avail = availability(report)
    fig.update_layout(
        title_text=(
            f"QA Dashboard — {report.run_id} | "
            f"Pass {report.pass_rate}% | Avail {avail}% | v{report.sut_version}"
        ),
        showlegend=False,
        template="plotly_dark",
        height=700,
        margin=dict(t=80, b=40),
    )
    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def save_report(report: RunReport, out_dir: Path | str | None = None) -> Path:
    """Persist the run JSON + Markdown + HTML report; return the run directory."""
    base = Path(out_dir) if out_dir else Path(__file__).resolve().parent.parent / "runs"
    run_dir = base / report.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "run.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    html = render_html(report)
    (run_dir / "report.html").write_text(html, encoding="utf-8")
    return run_dir
