"""
Eval harness — runs golden Q/A pairs through the agentic mesh and scores them.

Usage:
    uv run python evals/eval_harness.py [--orchestrator-url http://localhost:8000]

Scoring:
  - keyword_score : fraction of expected_keywords found in the answer (0-1)
  - contains_score: 1 if expected_contains substring is present, else 0
  - llm_score     : LLM-as-judge (0/1) — only when LLM available

Results are printed as a table and logged to MLflow (when MLFLOW_TRACKING_URI set).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

_AGENT_PORTS: dict[str, str] = {
    "financial": "http://localhost:8001",
    "market": "http://localhost:8002",
    "docs": "http://localhost:8003",
    "action": "http://localhost:8004",
    "qa": "http://localhost:8005",
}

_LLM_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
_LLM_MODEL = os.getenv("EVAL_LLM_MODEL", "qwen2.5:3b")


@dataclass
class EvalResult:
    id: str
    agent: str
    question: str
    answer: str
    keyword_score: float
    contains_score: float
    llm_score: float | None
    latency_ms: float
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def composite_score(self) -> float:
        scores = [self.keyword_score, self.contains_score]
        if self.llm_score is not None:
            scores.append(self.llm_score)
        return sum(scores) / len(scores)


async def _call_agent(agent: str, message: str, timeout: float = 30.0) -> tuple[str, float]:
    """Call an agent directly via A2A and return (answer, latency_ms)."""
    base = _AGENT_PORTS.get(agent, "http://localhost:8001")
    payload = {
        "task_id": f"eval-{int(time.time() * 1000)}",
        "messages": [{"role": "user", "content": message}],
    }
    t0 = time.monotonic()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base}/a2a/tasks/send", json=payload)
        resp.raise_for_status()
    latency = (time.monotonic() - t0) * 1000
    data = resp.json()
    answer = ""
    for art in data.get("artifacts", []):
        if art.get("parts"):
            answer = " ".join(p.get("text", "") for p in art["parts"])
            break
    return answer, latency


async def _llm_judge(question: str, expected_keywords: list[str], answer: str) -> float | None:
    """Ask the LLM to score the answer 0 or 1. Returns None if LLM unavailable."""
    prompt = (
        f"You are evaluating an AI assistant answer for a private banking application.\n\n"
        f"Question: {question}\n"
        f"Expected to mention: {', '.join(expected_keywords)}\n"
        f"Answer: {answer}\n\n"
        f"Is this a correct and relevant answer? Reply with only '1' for yes or '0' for no."
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_LLM_URL}/api/generate",
                json={"model": _LLM_MODEL, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            text = resp.json().get("response", "").strip()
            return 1.0 if "1" in text[:5] else 0.0
    except Exception:
        return None


def _keyword_score(answer: str, keywords: list[str]) -> float:
    if not keywords:
        return 1.0
    lower = answer.lower()
    hits = sum(1 for kw in keywords if kw.lower() in lower)
    return hits / len(keywords)


def _contains_score(answer: str, substring: str) -> float:
    return 1.0 if substring.lower() in answer.lower() else 0.0


async def run_eval(use_llm_judge: bool = True) -> list[EvalResult]:
    dataset = json.loads(_DATASET_PATH.read_text())
    results: list[EvalResult] = []

    for item in dataset:
        print(f"  [{item['id']}] {item['question'][:60]}...", end=" ", flush=True)
        try:
            answer, latency = await _call_agent(item["agent"], item["question"])
        except Exception as exc:
            print(f"ERROR: {exc}")
            results.append(
                EvalResult(
                    id=item["id"],
                    agent=item["agent"],
                    question=item["question"],
                    answer="",
                    keyword_score=0.0,
                    contains_score=0.0,
                    llm_score=None,
                    latency_ms=0.0,
                    error=str(exc),
                )
            )
            continue

        kw_score = _keyword_score(answer, item.get("expected_keywords", []))
        ct_score = _contains_score(answer, item.get("expected_contains", ""))
        lm_score = None
        if use_llm_judge:
            lm_score = await _llm_judge(item["question"], item.get("expected_keywords", []), answer)

        result = EvalResult(
            id=item["id"],
            agent=item["agent"],
            question=item["question"],
            answer=answer,
            keyword_score=kw_score,
            contains_score=ct_score,
            llm_score=lm_score,
            latency_ms=latency,
        )
        results.append(result)
        print(f"score={result.composite_score:.2f}  latency={latency:.0f}ms")

    return results


def _print_table(results: list[EvalResult]) -> None:
    print("\n" + "=" * 80)
    print(f"{'ID':<12} {'AGENT':<10} {'KW':>5} {'CT':>5} {'LLM':>5} {'COMP':>6} {'MS':>6}  ERR")
    print("-" * 80)
    for r in results:
        llm = f"{r.llm_score:.1f}" if r.llm_score is not None else "  -"
        print(
            f"{r.id:<12} {r.agent:<10} {r.keyword_score:>5.2f} {r.contains_score:>5.2f} "
            f"{llm:>5} {r.composite_score:>6.2f} {r.latency_ms:>6.0f}  {r.error[:20]}"
        )
    print("=" * 80)
    total = len(results)
    ok = [r for r in results if not r.error]
    avg_comp = sum(r.composite_score for r in ok) / len(ok) if ok else 0.0
    avg_lat = sum(r.latency_ms for r in ok) / len(ok) if ok else 0.0
    print(
        f"\nTotal: {total}  Passed: {len(ok)}  Errors: {total - len(ok)}"
        f"  Avg composite: {avg_comp:.3f}  Avg latency: {avg_lat:.0f}ms\n"
    )


def _log_mlflow(results: list[EvalResult], run_name: str = "eval") -> None:
    tracking = os.getenv("MLFLOW_TRACKING_URI")
    if not tracking:
        print("MLFLOW_TRACKING_URI not set — skipping MLflow logging")
        return
    try:
        import mlflow  # type: ignore[import]

        mlflow.set_tracking_uri(tracking)
        mlflow.set_experiment("wealthmesh-eval")
        with mlflow.start_run(run_name=run_name):
            ok = [r for r in results if not r.error]
            if ok:
                mlflow.log_metric("avg_keyword_score", sum(r.keyword_score for r in ok) / len(ok))
                mlflow.log_metric("avg_contains_score", sum(r.contains_score for r in ok) / len(ok))
                mlflow.log_metric(
                    "avg_composite_score", sum(r.composite_score for r in ok) / len(ok)
                )
                mlflow.log_metric("avg_latency_ms", sum(r.latency_ms for r in ok) / len(ok))
                mlflow.log_metric("pass_rate", len(ok) / len(results))
                lm_scores = [r.llm_score for r in ok if r.llm_score is not None]
                if lm_scores:
                    mlflow.log_metric("avg_llm_judge_score", sum(lm_scores) / len(lm_scores))
            # Log dataset and results as artifacts
            mlflow.log_dict(
                {"results": [r.__dict__ for r in results]},
                "eval_results.json",
            )
        print(f"MLflow run logged to {tracking}")
    except ImportError:
        print("mlflow not installed — skipping")
    except Exception as exc:
        print(f"MLflow error: {exc}")


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WealthMesh eval harness")
    parser.add_argument("--no-llm-judge", action="store_true", help="Skip LLM-as-judge scoring")
    parser.add_argument("--run-name", default="eval", help="MLflow run name")
    args = parser.parse_args(argv)

    print(f"Running {_DATASET_PATH.name} against agents...")
    results = await run_eval(use_llm_judge=not args.no_llm_judge)
    _print_table(results)
    _log_mlflow(results, run_name=args.run_name)

    ok = [r for r in results if not r.error]
    avg = sum(r.composite_score for r in ok) / len(ok) if ok else 0.0
    return 0 if avg >= 0.5 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
