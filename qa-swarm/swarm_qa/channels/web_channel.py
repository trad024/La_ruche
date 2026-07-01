"""
Web channel — Playwright, code-based (deck slides 9, 10, 14).

Faithful to the deck's "code-based" philosophy: the Executor SLM writes a whole Playwright
(Python) script for the scenario, which is validated with ``ast.parse`` and run in a
subprocess sandbox. A known-good deterministic script is used as a fallback when the model's
output does not parse or fails to produce a result — the same generate -> sanitize -> fallback
pattern the in-mesh QA agent already uses.

The script speaks a tiny protocol back to the harness: it prints one line
``RESULT_JSON:{...}`` with the captured reply, latency, screenshot path and crash flag.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from swarm_qa.client import get_swarm
from swarm_qa.config import settings
from swarm_qa.extract import strip_code_fences
from swarm_qa.models import ChannelResult, TestCase

_SCREENS = Path(__file__).resolve().parent.parent / "runs" / "_screens"

# DOM contract of the LaRuche chat page (frontend/src/pages/Chat.tsx).
_CHAT_URL = f"{settings.sut_web_url}/chat"
_INPUT_SEL = "input.composer-input"
_SEND_SEL = "button.composer-primary"
_REPLY_SEL = ".assistant-answer"

GEN_INSTRUCTIONS = (
    "You write a single self-contained Python script using playwright.sync_api to test a "
    "web chat UI. The script MUST:\n"
    f"1. launch chromium headless and open {_CHAT_URL}\n"
    f"2. wait for the input '{_INPUT_SEL}', fill it with the MESSAGE, click '{_SEND_SEL}'\n"
    f"3. wait for a NEW '{_REPLY_SEL}' element and read the assistant's reply text once it "
    "stops streaming\n"
    "4. take a screenshot to SHOT\n"
    '5. print exactly one line: RESULT_JSON:{"actual": <reply>, "latency_ms": <ms>, '
    '"crashed": <bool>, "screenshot": SHOT}\n'
    "Output ONLY Python code, no markdown, no prose."
)


def _fallback_script(message: str, shot: str) -> str:
    """A robust, known-good Playwright script (used when generation is unusable)."""
    return f"""import json, time
from playwright.sync_api import sync_playwright

URL = {_CHAT_URL!r}
MESSAGE = {message!r}
SHOT = {shot!r}
out = {{"actual": "", "latency_ms": 0.0, "crashed": False, "screenshot": SHOT}}

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    try:
        page.goto(URL, wait_until="networkidle", timeout=30000)
        page.wait_for_selector({_INPUT_SEL!r}, timeout=15000)
        before = page.locator({_REPLY_SEL!r}).count()
        page.fill({_INPUT_SEL!r}, MESSAGE)
        page.click({_SEND_SEL!r})
        t0 = time.time()
        page.wait_for_function(
            "args => document.querySelectorAll(args.sel).length > args.n",
            arg={{"sel": {_REPLY_SEL!r}, "n": before}}, timeout=60000)
        last, stable = "", 0
        while time.time() - t0 < 60:
            txt = page.locator({_REPLY_SEL!r}).last.inner_text().strip()
            if txt and txt != "Thinking..." and txt == last:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last = txt
            page.wait_for_timeout(400)
        out["actual"] = last
        out["latency_ms"] = round((time.time() - t0) * 1000, 1)
        page.screenshot(path=SHOT)
    except Exception as exc:
        out["crashed"] = True
        out["actual"] = f"[web error] {{exc}}"
        try:
            page.screenshot(path=SHOT)
        except Exception:
            pass
    finally:
        browser.close()

print("RESULT_JSON:" + json.dumps(out))
"""


def _is_runnable(script: str) -> bool:
    if "sync_playwright" not in script or "RESULT_JSON" not in script:
        return False
    try:
        ast.parse(script)
        return True
    except SyntaxError:
        return False


def generate_script(test_case: TestCase, shot: str) -> tuple[str, bool]:
    """Return (script, generated?) — SLM-written script if usable, else the fallback."""
    prompt = f"{GEN_INSTRUCTIONS}\n\nMESSAGE = {test_case.input!r}\nSHOT = {shot!r}"
    try:
        from swarm import Agent

        agent = Agent(
            name="WebExecutor", model=settings.model_executor, instructions=GEN_INSTRUCTIONS
        )
        resp = get_swarm().run(
            agent=agent, messages=[{"role": "user", "content": prompt}], max_turns=1
        )
        script = strip_code_fences(resp.messages[-1].get("content") or "")
        if _is_runnable(script):
            return script, True
    except Exception:
        pass
    return _fallback_script(test_case.input, shot), False


def _run_script(script: str, wall_timeout: float) -> dict | None:
    with tempfile.NamedTemporaryFile(
        "w", suffix=".py", prefix="webtest_", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script)
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=wall_timeout,
        )
    except subprocess.TimeoutExpired:
        return None
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT_JSON:"):
            try:
                return json.loads(line[len("RESULT_JSON:") :])
            except json.JSONDecodeError:
                return None
    return None


def run_web_test(test_case: TestCase) -> ChannelResult:
    _SCREENS.mkdir(parents=True, exist_ok=True)
    shot = str(_SCREENS / f"{test_case.id}_web_{int(time.time())}.png")
    wall = settings.timeout_seconds + 40  # browser launch + nav overhead

    script, generated = generate_script(test_case, shot)
    start = time.perf_counter()
    data = _run_script(script, wall)
    # If a generated script failed to report, retry once with the safe fallback.
    if data is None and generated:
        data = _run_script(_fallback_script(test_case.input, shot), wall)
    elapsed = round((time.perf_counter() - start) * 1000, 1)

    if data is None:
        return ChannelResult(
            channel="web",
            actual="",
            timed_out=True,
            crashed=True,
            latency_ms=elapsed,
            error="web script produced no result (timeout/crash)",
            screenshot=shot,
        )
    return ChannelResult(
        channel="web",
        actual=str(data.get("actual", "")).strip(),
        latency_ms=float(data.get("latency_ms") or elapsed),
        crashed=bool(data.get("crashed", False)),
        screenshot=str(data.get("screenshot", shot)),
        status_code=200,
    )
