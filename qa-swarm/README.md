# QA-Swarm — Autonomous Testing System

An autonomous testing pipeline built with **OpenAI Swarm + Ollama** that tests a conversational agent across **3 channels** (API / Web / Mobile), scores hallucinations, and **detects regressions** between two versions of the target agent.

## Architecture

```
Generator → Executor → Evaluator → Reporter
   │            │           │           │
   │     ┌──────┼───────┐   │           │
   │     │      │       │   │           │
   │   API    Web    Mobile │           │
   │  (httpx) (Playwright) (Appium)     │
   │            │           │           │
   └────────────┴───────────┘           │
        52 scenarios (JSON corpus)      │
                                        ▼
                              Plotly HTML Dashboard
                              Markdown Report
                              Regression Diff
```

**4 Swarm agents** chained via handoffs:

| Agent | Role | Model |
|---|---|---|
| **Generator** | Loads/synthesizes test cases from the JSON corpus | qwen2.5:3b |
| **Executor** | Dispatches each case to the target channel (API/Web/Mobile) | qwen2.5:3b |
| **Evaluator** | LLM-as-judge scoring (pertinence, exactitude, coherence, hallucination) | qwen2.5:3b |
| **Reporter** | Produces Markdown report + interactive Plotly HTML dashboard | qwen2.5:3b |

## Setup

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- [Ollama](https://ollama.ai/) running locally with `qwen2.5:3b` pulled
- The wealth-management agent mesh running (SUT)

### Install

```bash
cd qa-swarm
uv sync

# Optional extras
uv pip install -e ".[web]"         # Playwright (web channel)
uv pip install -e ".[mobile]"      # Appium (mobile channel)
uv pip install -e ".[report]"      # Plotly HTML dashboard
uv pip install -e ".[metrics]"     # BLEU/ROUGE metrics
uv pip install -e ".[backoffice]"  # FastAPI console

# Playwright browser (web channel only)
playwright install chromium
```

### Ollama model

```bash
ollama pull qwen2.5:3b
```

### Mobile channel (optional)

Requires Android SDK + AVD, Appium server, and the Expo app on the emulator:

```bash
npm install -g appium
appium driver install uiautomator2
appium  # starts on :4723
```

## Usage

### Run the pipeline (CLI)

```bash
# API channel only (default)
uv run python -m swarm_qa.pipeline --channel api

# Multiple channels
uv run python -m swarm_qa.pipeline --channel api web --version v1.0

# Limit scenarios
uv run python -m swarm_qa.pipeline --channel api --limit 5 --version baseline
```

Reports are saved to `swarm_qa/runs/<run_id>/`:
- `run.json` — structured results
- `report.md` — Markdown table
- `report.html` — interactive Plotly dashboard

### Regression detection

Compare two runs to detect PASS→FAIL flips, score drops, and latency spikes:

```python
from swarm_qa.regression import compare_from_files
from pathlib import Path

reg = compare_from_files(
    Path("swarm_qa/runs/run_baseline/run.json"),
    Path("swarm_qa/runs/run_candidate/run.json"),
)
print(f"Regressions: {reg.has_regressions}")
for flip in reg.flips:
    print(f"  FLIP: {flip.intent} [{flip.channel}]")
```

### Backoffice console

```bash
uv pip install -e ".[backoffice]"
uv run uvicorn backoffice.app:app --port 8090 --reload
```

Open `http://localhost:8090` to:
- Trigger pipeline runs
- Browse scenarios (52 cases)
- View Plotly dashboards
- Compare regressions between runs

### CI smoke gate

```bash
uv run python qa-swarm/ci_smoke.py
# exit 0 = pass, exit 1 = blocking failure
```

## Test corpus

52 scenarios in `swarm_qa/corpus/scenarios.json`:

| Type | Count | Examples |
|---|---|---|
| **Nominal** | 30 | AUM, TWR, Sharpe, geo/sector breakdown, market quotes, doc lookup |
| **Limit** | 10 | Empty input, unicode, typos, multi-question, very long input |
| **Adversarial** | 12 | Prompt injection, XSS, SQL injection, jailbreak, PII extraction |

## Scoring

The Evaluator uses LLM-as-judge with strict-JSON output:

- **Pertinence** (1-5): relevance to the user's intent
- **Exactitude** (1-5): factual correctness vs expected answer
- **Coherence** (1-5): logical consistency
- **Hallucination**: boolean flag (FAIL if true)
- **Verdict**: PASS/FAIL based on mean score ≥ 3.0 and no hallucination

Blocking FAIL rules (applied before LLM judge):
- Timeout (>30s) → FAIL
- Crash (5xx / UI crash) → FAIL
- Empty reply → FAIL
- Hallucination detected → FAIL

## Metrics

- Latency per channel (avg ms)
- Availability % (non-crash, non-timeout)
- Pass rate by type (nominal/limit/adversarial)
- Web↔Mobile divergence (text similarity, >20% = FAIL flag)
- BLEU / ROUGE-L (optional, with `metrics` extra)

## Tests

```bash
uv run pytest qa-swarm/tests/ -v
```

## Project structure

```
qa-swarm/
├── swarm_qa/
│   ├── config.py          # Ollama URL, models, thresholds
│   ├── client.py          # Swarm↔Ollama wiring
│   ├── models.py          # TestCase, ChannelResult, Score, RunReport
│   ├── pipeline.py        # Deterministic pipeline driver
│   ├── regression.py      # Compare two runs for regressions
│   ├── extract.py         # JSON extraction from SLM output
│   ├── agents/
│   │   ├── generator.py   # Load/synthesize test cases
│   │   ├── executor.py    # Dispatch to channels
│   │   ├── evaluator.py   # LLM-as-judge scoring
│   │   └── reporter.py    # Markdown + Plotly reports
│   ├── channels/
│   │   ├── api_channel.py    # httpx POST /api/chat (SSE)
│   │   ├── web_channel.py    # Playwright code-based
│   │   └── mobile_channel.py # Appium UiAutomator2
│   ├── scoring/
│   │   └── metrics.py     # Latency, availability, divergence, BLEU/ROUGE
│   ├── corpus/
│   │   └── scenarios.json # 52 test scenarios
│   └── runs/              # Persisted run results
├── backoffice/
│   ├── app.py             # FastAPI console
│   └── templates/         # Jinja2 HTML templates
├── tests/                 # pytest suite
├── ci_smoke.py            # CI pre-merge gate
└── pyproject.toml
```
