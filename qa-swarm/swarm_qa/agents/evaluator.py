"""
Evaluator Agent — scores one channel result PASS/FAIL.

Follows the deck's "structured prompt for Evaluator" (slide 19): a QA-senior role, a
strict-JSON output contract, and blocking-FAIL rules (slide 17). The numeric scores come
from the LLM judge; the *verdict* is computed deterministically from those scores plus the
deterministic blocking flags (crash / timeout / hallucination), which is more reliable than
trusting a 3B model to apply the rules itself.
"""

from __future__ import annotations

from swarm import Agent

from swarm_qa.client import get_swarm
from swarm_qa.config import settings
from swarm_qa.extract import extract_json
from swarm_qa.models import ChannelResult, Score, TestCase

EVALUATOR_INSTRUCTIONS = (
    "You are a senior QA engineer evaluating a conversational financial agent. "
    "For each test you receive INPUT, EXPECTED, ACTUAL and CHANNEL. "
    "Judge the ACTUAL reply and return ONLY a JSON object, no prose, with keys:\n"
    '{"pertinence": 1-5, "exactitude": 1-5, "coherence": 1-5, '
    '"format_ok": true/false, "hallucination": true/false, "reason": "short explanation"}\n'
    "pertinence = relevance to the intent; exactitude = factual correctness vs EXPECTED; "
    "coherence = internally consistent and on-topic; hallucination = invented facts/numbers "
    "not supported by EXPECTED. Be strict about invented figures."
)


def build_evaluator_agent() -> Agent:
    return Agent(
        name="Evaluator", model=settings.model_evaluator, instructions=EVALUATOR_INSTRUCTIONS
    )


_AGENT = build_evaluator_agent()


def _judge(test_case: TestCase, result: ChannelResult) -> dict:
    prompt = (
        f"INPUT: {test_case.input!r}\n"
        f"EXPECTED: {test_case.expected!r}\n"
        f"ACTUAL: {result.actual!r}\n"
        f"CHANNEL: {result.channel}\n\n"
        "Return ONLY the JSON object."
    )
    resp = get_swarm().run(
        agent=_AGENT,
        messages=[{"role": "user", "content": prompt}],
        max_turns=1,
    )
    return extract_json(resp.messages[-1].get("content") or "")


def _num(value: object, default: float = 0.0) -> float:
    try:
        return max(0.0, min(5.0, float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def score_result(test_case: TestCase, result: ChannelResult) -> Score:
    """Score a channel result, applying deterministic blocking-FAIL rules."""
    # Deterministic blocking flags first (deck slide 17) — no LLM needed to fail these.
    if result.timed_out or result.crashed:
        return Score(
            verdict="FAIL",
            reason=("timeout" if result.timed_out else f"crash/5xx (status {result.status_code})"),
            format_ok=False,
        )
    if not result.actual.strip():
        return Score(verdict="FAIL", reason="empty reply", format_ok=False)

    try:
        judged = _judge(test_case, result)
    except Exception as exc:  # judge unavailable — be explicit, don't silently pass
        return Score(verdict="FAIL", reason=f"evaluator error: {exc}")

    score = Score(
        pertinence=_num(judged.get("pertinence")),
        exactitude=_num(judged.get("exactitude")),
        coherence=_num(judged.get("coherence")),
        format_ok=bool(judged.get("format_ok", True)),
        hallucination=bool(judged.get("hallucination", False)),
        reason=str(judged.get("reason", ""))[:300],
    )
    # Verdict: blocking hallucination, else mean-score threshold.
    if score.hallucination:
        score.verdict = "FAIL"
        score.reason = f"hallucination — {score.reason}".strip(" —")
    elif score.mean >= settings.min_score_pass:
        score.verdict = "PASS"
    else:
        score.verdict = "FAIL"
    return score
