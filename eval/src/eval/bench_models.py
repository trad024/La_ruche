"""
Phase 1 — Model benchmark for RTX 2050 (4 GB VRAM, 16 GB RAM).

Usage:
    uv run --package eval python eval/src/eval/bench_models.py
    uv run --package eval python eval/src/eval/bench_models.py --quick
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

OLLAMA_BASE = "http://localhost:11434"

# Models to benchmark — (name, role, origin)
ROSTER: list[tuple[str, str, str]] = [
    ("qwen2.5:3b", "router / most agents", "🇨🇳 Alibaba"),
    ("qwen2.5:7b", "financial assistant (main)", "🇨🇳 Alibaba"),
    ("llama3.2:3b", "alt small agent", "🇺🇸 Meta"),
    ("phi3.5", "alt small agent / tool use", "🇺🇸 Microsoft"),
    ("mistral:7b-instruct", "French-origin option", "🇫🇷 Mistral"),
    ("deepseek-r1:7b", "reasoning (on-demand only)", "🇨🇳 DeepSeek"),
    ("nomic-embed-text", "embeddings (RAG)", "🇺🇸 Nomic"),
]

BENCH_PROMPT = (
    "You are a financial assistant. "
    "In one sentence, what is the Sharpe ratio and why does it matter for a portfolio?"
)
EMBED_TEXT = "portfolio performance time-weighted return annualized growth Sharpe ratio"

WARMUP_PROMPT = "Say hello in one word."


@dataclass
class ModelResult:
    name: str
    role: str
    origin: str
    available: bool = False
    warmup_s: float = 0.0
    ttft_s: float = 0.0  # time to first token
    total_s: float = 0.0
    tokens: int = 0
    tok_per_s: float = 0.0
    vram_mb: int = 0
    error: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def nvidia_vram_used_mb() -> int:
    """Return current GPU memory used in MB via nvidia-smi."""
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            timeout=5,
        )
        return int(out.decode().strip().split("\n")[0])
    except Exception:
        return -1


def model_available(name: str) -> bool:
    try:
        r = httpx.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        # match short name (qwen2.5:3b matches qwen2.5:3b)
        return any(name == m or name.split(":")[0] == m.split(":")[0] for m in models)
    except Exception:
        return False


def bench_generate(name: str, prompt: str) -> tuple[float, float, int]:
    """Stream a generation, return (ttft_s, total_s, token_count)."""
    payload = {
        "model": name,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": 80, "temperature": 0},
    }
    ttft = 0.0
    token_count = 0
    t0 = time.perf_counter()
    first = True
    with httpx.stream("POST", f"{OLLAMA_BASE}/api/generate", json=payload, timeout=120) as resp:
        for line in resp.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if first and chunk.get("response"):
                ttft = time.perf_counter() - t0
                first = False
            if chunk.get("response"):
                token_count += 1
            if chunk.get("done"):
                # use eval_count if available (actual token count)
                token_count = chunk.get("eval_count", token_count)
                break
    total = time.perf_counter() - t0
    return ttft, total, token_count


def bench_embed(name: str, text: str) -> tuple[float, int]:
    """Return (total_s, dim)."""
    t0 = time.perf_counter()
    r = httpx.post(
        f"{OLLAMA_BASE}/api/embed",
        json={"model": name, "input": text},
        timeout=30,
    )
    total = time.perf_counter() - t0
    data = r.json()
    embeddings = data.get("embeddings", [[]])
    dim = len(embeddings[0]) if embeddings else 0
    return total, dim


def unload_model(name: str) -> None:
    """Ask Ollama to unload the model from VRAM (keep_alive=0)."""
    import contextlib

    with contextlib.suppress(Exception):
        httpx.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": name, "prompt": "", "keep_alive": 0},
            timeout=10,
        )


def run_benchmark(quick: bool = False) -> list[ModelResult]:
    results: list[ModelResult] = []

    for name, role, origin in ROSTER:
        print(f"\n{'-'*60}")
        print(f">>  {name}  ({role})")
        r = ModelResult(name=name, role=role, origin=origin)

        if not model_available(name):
            r.error = "not installed — run: ollama pull " + name
            print(f"   x {r.error}")
            results.append(r)
            continue

        r.available = True

        # Embeddings model: different bench path
        if "embed" in name:
            try:
                total, dim = bench_embed(name, EMBED_TEXT)
                r.total_s = total
                r.extra["dim"] = dim
                r.vram_mb = nvidia_vram_used_mb()
                print(f"   embed dim={dim}  total={total:.2f}s  vram={r.vram_mb} MB")
            except Exception as e:
                r.error = str(e)
            results.append(r)
            continue

        # Warmup pass (loads model into VRAM)
        print("   warming up …", end=" ", flush=True)
        try:
            t0 = time.perf_counter()
            bench_generate(name, WARMUP_PROMPT)
            r.warmup_s = time.perf_counter() - t0
            print(f"{r.warmup_s:.1f}s")
        except Exception as e:
            r.error = f"warmup failed: {e}"
            print(r.error)
            results.append(r)
            continue

        # Measure VRAM after load
        r.vram_mb = nvidia_vram_used_mb()

        # Actual benchmark
        if not quick:
            print("   benchmarking …", end=" ", flush=True)
            try:
                ttft, total, tokens = bench_generate(name, BENCH_PROMPT)
                r.ttft_s = ttft
                r.total_s = total
                r.tokens = tokens
                r.tok_per_s = tokens / total if total > 0 else 0
                print(
                    f"ttft={ttft:.2f}s  total={total:.1f}s  "
                    f"{tokens} tok  {r.tok_per_s:.1f} tok/s"
                )
            except Exception as e:
                r.error = str(e)
                print(r.error)

        # Unload before next model to free VRAM
        unload_model(name)
        time.sleep(1)

        results.append(r)

    return results


def print_table(results: list[ModelResult]) -> None:
    print("\n" + "=" * 90)
    print("MODEL BENCHMARK RESULTS - RTX 2050 / 16 GB RAM")
    print("=" * 90)
    header = f"{'Model':<28} {'Role':<30} {'TTFT':>6} {'Tok/s':>7} {'VRAM MB':>8} {'Status'}"
    print(header)
    print("-" * 90)
    for r in results:
        if not r.available:
            status = f"x {r.error}"
            print(f"{r.name:<28} {r.role:<30} {'—':>6} {'—':>7} {'—':>8}  {status}")
        elif "embed" in r.name:
            dim = r.extra.get("dim", "?")
            print(
                f"{r.name:<28} {r.role:<30} {'—':>6} {'—':>7} {r.vram_mb:>8}  "
                f"v dim={dim}  {r.total_s:.2f}s"
            )
        elif r.error:
            print(f"{r.name:<28} {r.role:<30} {'—':>6} {'—':>7} {r.vram_mb:>8}  x {r.error}")
        else:
            print(
                f"{r.name:<28} {r.role:<30} {r.ttft_s:>6.2f} {r.tok_per_s:>7.1f} "
                f"{r.vram_mb:>8}  v"
            )
    print("=" * 90)


def write_defaults(results: list[ModelResult]) -> None:
    """Write recommended defaults to eval/model_defaults.json."""
    # Pick best small model (fastest tok/s among 3b class, available)
    small = [
        r
        for r in results
        if r.available
        and not r.error
        and "embed" not in r.name
        and any(tag in r.name for tag in ["3b", "3.8b", "phi"])
    ]
    small.sort(key=lambda r: -r.tok_per_s)

    # Pick conversational (7b class)
    conv = [
        r
        for r in results
        if r.available and not r.error and "7b" in r.name and "deepseek" not in r.name
    ]
    conv.sort(key=lambda r: -r.tok_per_s)

    defaults = {
        "MODEL_DEFAULT": small[0].name if small else "qwen2.5:3b",
        "MODEL_CONVERSATIONAL": conv[0].name if conv else "qwen2.5:7b",
        "MODEL_EMBED": "nomic-embed-text",
        "MODEL_REASONING": "deepseek-r1:7b",
        "notes": {
            r.name: {"tok_per_s": r.tok_per_s, "vram_mb": r.vram_mb} for r in results if r.available
        },
    }

    out = "eval/model_defaults.json"
    with open(out, "w") as f:
        json.dump(defaults, f, indent=2)
    print(f"\nv defaults written to {out}")
    print(f"  MODEL_DEFAULT        = {defaults['MODEL_DEFAULT']}")
    print(f"  MODEL_CONVERSATIONAL = {defaults['MODEL_CONVERSATIONAL']}")
    print(f"  MODEL_EMBED          = {defaults['MODEL_EMBED']}")
    print(f"  MODEL_REASONING      = {defaults['MODEL_REASONING']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark local Ollama models")
    parser.add_argument("--quick", action="store_true", help="Skip full bench, warmup only")
    args = parser.parse_args()

    print("Agentic Mesh — Phase 1 Model Benchmark")
    print(f"Ollama: {OLLAMA_BASE}")
    print(f"GPU VRAM (before): {nvidia_vram_used_mb()} MB used")

    results = run_benchmark(quick=args.quick)
    print_table(results)
    write_defaults(results)


if __name__ == "__main__":
    main()
