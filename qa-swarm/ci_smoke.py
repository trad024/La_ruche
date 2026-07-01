"""
CI smoke gate — run the API channel on a small subset and fail the build on any blocking FAIL.

Usage (pre-merge hook or CI step):
    uv run python qa-swarm/ci_smoke.py
    # exit 0 = all pass, exit 1 = blocking failure detected
"""

from __future__ import annotations

import sys

from swarm_qa.pipeline import run_pipeline


def main() -> int:
    print("CI smoke: running 5 API scenarios...")
    report = run_pipeline(channels=["api"], limit=5, sut_version="ci-smoke")
    print(f"Pass rate: {report.pass_rate}% ({report.passed}/{report.total})")

    failures = [
        (sc, ch, score)
        for sc in report.scenarios
        for ch, score in sc.scores.items()
        if score.verdict == "FAIL"
    ]
    if failures:
        print(f"\nBLOCKING: {len(failures)} failure(s):")
        for sc, ch, score in failures:
            print(f"  - {sc.test_case.intent} [{ch}]: {score.reason}")
        return 1

    print("All scenarios passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
