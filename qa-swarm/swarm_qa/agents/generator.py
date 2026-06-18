"""
Generator Agent — produces the test corpus (deck slide 13).

Primary path: load the versioned JSON corpus (the deck wants 50+ scenarios versioned in
JSON). Secondary path: ask the SLM to synthesize additional cases from a free-text spec,
demonstrating the agentic "Generator" role and its handoff to the Executor.
"""

from __future__ import annotations

import json
from pathlib import Path

from swarm import Agent

from swarm_qa.client import get_swarm
from swarm_qa.config import settings
from swarm_qa.extract import extract_json
from swarm_qa.models import TestCase

CORPUS_PATH = Path(__file__).resolve().parent.parent / "corpus" / "scenarios.json"

GENERATOR_INSTRUCTIONS = (
    "You are a senior QA test designer for a conversational financial advisor. "
    "Given a capability spec, generate diverse test cases covering nominal, limit "
    "(empty/very long/edge) and adversarial (XSS, prompt-injection, out-of-domain) inputs. "
    "Each case has: id, intent, type (nominal|limit|adversarial), input, expected, "
    "channels (subset of api/web/mobile). When the cases are ready, hand off to the Executor."
)


def load_corpus(path: Path | str = CORPUS_PATH) -> list[TestCase]:
    """Load and validate the versioned scenario corpus."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    cases = raw["scenarios"] if isinstance(raw, dict) else raw
    return [TestCase.model_validate(c) for c in cases]


def build_generator_agent(handoff=None) -> Agent:
    funcs = [handoff] if handoff else []
    return Agent(
        name="Generator",
        model=settings.model_generator,
        instructions=GENERATOR_INSTRUCTIONS,
        functions=funcs,
    )


def generate_cases(spec: str, n: int = 5) -> list[TestCase]:
    """Agentically synthesize *n* extra cases from a spec (best-effort, validated)."""
    prompt = (
        f"Capability spec:\n{spec}\n\n"
        f"Generate {n} test cases. Return ONLY JSON: "
        '{"scenarios": [{"id": "...", "intent": "...", "type": "nominal", '
        '"input": "...", "expected": "...", "channels": ["api"]}]}'
    )
    resp = get_swarm().run(
        agent=build_generator_agent(),
        messages=[{"role": "user", "content": prompt}],
        max_turns=1,
    )
    data = extract_json(resp.messages[-1].get("content") or "")
    out: list[TestCase] = []
    for c in data.get("scenarios", []):
        try:
            out.append(TestCase.model_validate(c))
        except Exception:
            continue
    return out
