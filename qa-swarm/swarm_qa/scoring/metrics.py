"""
Channel metrics + Web<->Mobile divergence (deck slides 15, 17).

Stdlib-only by default (difflib) so the core pipeline has no heavy NLP deps. BLEU/ROUGE
(optional `sacrebleu` / `rouge-score`) are layered on in Phase E for the NLP-quality table.
"""

from __future__ import annotations

from difflib import SequenceMatcher

from swarm_qa.models import Channel, RunReport, ScenarioResult


def text_similarity(a: str, b: str) -> float:
    """Token-aware similarity in [0, 1] (1 = identical)."""
    a, b = (a or "").lower().strip(), (b or "").lower().strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def divergence(a: str, b: str) -> float:
    """1 - similarity; how far two channel replies drift apart."""
    return round(1.0 - text_similarity(a, b), 3)


def compute_divergence(scenario: ScenarioResult) -> float | None:
    """Web<->Mobile reply divergence for a scenario, when both channels ran."""
    web = scenario.results.get("web")
    mobile = scenario.results.get("mobile")
    if web is None or mobile is None:
        return None
    return divergence(web.actual, mobile.actual)


def channel_latencies(report: RunReport) -> dict[Channel, float]:
    """Average latency (ms) per channel across the run."""
    sums: dict[Channel, float] = {}
    counts: dict[Channel, int] = {}
    for sc in report.scenarios:
        for ch, res in sc.results.items():
            sums[ch] = sums.get(ch, 0.0) + res.latency_ms
            counts[ch] = counts.get(ch, 0) + 1
    return {ch: round(sums[ch] / counts[ch], 1) for ch in sums}


def availability(report: RunReport) -> float:
    """Percentage of executions that did not crash or time out."""
    total = up = 0
    for sc in report.scenarios:
        for res in sc.results.values():
            total += 1
            if not res.crashed and not res.timed_out:
                up += 1
    return round(100 * up / total, 1) if total else 0.0


def pass_rate_by_type(report: RunReport) -> dict[str, float]:
    """Pass rate per case type (nominal / limit / adversarial)."""
    passed: dict[str, int] = {}
    total: dict[str, int] = {}
    for sc in report.scenarios:
        t = sc.test_case.type
        for score in sc.scores.values():
            total[t] = total.get(t, 0) + 1
            if score.verdict == "PASS":
                passed[t] = passed.get(t, 0) + 1
    return {t: round(100 * passed.get(t, 0) / n, 1) for t, n in total.items()}


def nlp_quality(expected: str, actual: str) -> dict[str, float]:
    """
    BLEU + ROUGE-L of *actual* vs *expected*, when `sacrebleu` / `rouge-score` are
    installed (optional `metrics` extra). Returns {} when unavailable so the core
    pipeline never hard-depends on heavy NLP packages.
    """
    out: dict[str, float] = {}
    if not expected or not actual:
        return out
    try:
        import sacrebleu

        out["bleu"] = round(sacrebleu.sentence_bleu(actual, [expected]).score, 1)
    except Exception:
        pass
    try:
        from rouge_score import rouge_scorer

        scorer = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
        out["rougeL"] = round(scorer.score(expected, actual)["rougeL"].fmeasure * 100, 1)
    except Exception:
        pass
    return out
