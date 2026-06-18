"""
Mobile channel — Appium, code-based (deck slides 12, 16).

Same code-based philosophy as the web channel: the Executor SLM writes an Appium
(UiAutomator2) script for the scenario, validated with ``ast.parse`` and run in a subprocess
sandbox, with a deterministic fallback. The script drives the Expo chat screen
(mobile/screens/ChatScreen.tsx) via the accessibility ids ``chat-input`` / ``chat-send``.

Prerequisites (documented in the README): Android SDK + a running AVD, an Appium server
(`appium`) on :4723, and the Expo app installed on the emulator. When those aren't present
the channel reports unavailability gracefully instead of breaking the run.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

from swarm_qa.client import get_swarm
from swarm_qa.config import settings
from swarm_qa.extract import strip_code_fences
from swarm_qa.models import ChannelResult, TestCase

_SCREENS = Path(__file__).resolve().parent.parent / "runs" / "_screens"

GEN_INSTRUCTIONS = (
    "You write a single self-contained Python script using the Appium-Python-Client to test "
    "an Android chat app. The script MUST: create a UiAutomator2 driver at APPIUM_URL with the "
    "given capabilities; find the input by accessibility id 'chat-input' and type MESSAGE; tap "
    "the 'chat-send' accessibility id; wait for the assistant's reply TextView; capture its "
    'text; screenshot to SHOT; and print exactly one line RESULT_JSON:{"actual":..., '
    '"latency_ms":..., "crashed":..., "screenshot":SHOT}. Output ONLY Python code.'
)


def appium_available() -> bool:
    try:
        r = httpx.get(f"{settings.appium_url}/status", timeout=3)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def _caps_literal() -> str:
    return (
        "{"
        f"'platformName': 'Android', 'appium:automationName': 'UiAutomator2', "
        f"'appium:deviceName': {settings.android_device!r}, "
        f"'appium:appPackage': {settings.android_app_package!r}, "
        f"'appium:appActivity': {settings.android_app_activity!r}, "
        f"'appium:noReset': True"
        "}"
    )


def _fallback_script(message: str, shot: str) -> str:
    return f"""import json, time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy

MESSAGE = {message!r}
SHOT = {shot!r}
out = {{"actual": "", "latency_ms": 0.0, "crashed": False, "screenshot": SHOT}}

options = UiAutomator2Options().load_capabilities({_caps_literal()})
driver = webdriver.Remote({settings.appium_url!r}, options=options)
try:
    driver.implicitly_wait(10)
    box = driver.find_element(AppiumBy.ACCESSIBILITY_ID, "chat-input")
    box.send_keys(MESSAGE)
    t0 = time.time()
    driver.find_element(AppiumBy.ACCESSIBILITY_ID, "chat-send").click()
    time.sleep(2)
    last = ""
    while time.time() - t0 < 60:
        texts = [e.text for e in driver.find_elements(AppiumBy.CLASS_NAME, "android.widget.TextView") if e.text]
        cur = texts[-1] if texts else ""
        if cur and cur == last:
            break
        last = cur
        time.sleep(1.5)
    out["actual"] = last
    out["latency_ms"] = round((time.time() - t0) * 1000, 1)
    driver.save_screenshot(SHOT)
except Exception as exc:
    out["crashed"] = True
    out["actual"] = f"[mobile error] {{exc}}"
finally:
    driver.quit()

print("RESULT_JSON:" + json.dumps(out))
"""


def _is_runnable(script: str) -> bool:
    if "webdriver" not in script or "RESULT_JSON" not in script:
        return False
    try:
        ast.parse(script)
        return True
    except SyntaxError:
        return False


def generate_script(test_case: TestCase, shot: str) -> tuple[str, bool]:
    prompt = (
        f"{GEN_INSTRUCTIONS}\n\nAPPIUM_URL = {settings.appium_url!r}\n"
        f"capabilities = {_caps_literal()}\nMESSAGE = {test_case.input!r}\nSHOT = {shot!r}"
    )
    try:
        from swarm import Agent

        agent = Agent(
            name="MobileExecutor", model=settings.model_executor, instructions=GEN_INSTRUCTIONS
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
        "w", suffix=".py", prefix="mobiletest_", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script)
        path = fh.name
    try:
        proc = subprocess.run(
            [sys.executable, path], capture_output=True, text=True, timeout=wall_timeout
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


def run_mobile_test(test_case: TestCase) -> ChannelResult:
    if not appium_available():
        return ChannelResult(
            channel="mobile",
            crashed=True,
            error=f"Appium server unavailable at {settings.appium_url} (start an AVD + `appium`).",
        )

    _SCREENS.mkdir(parents=True, exist_ok=True)
    shot = str(_SCREENS / f"{test_case.id}_mobile_{int(time.time())}.png")
    wall = settings.timeout_seconds + 60  # driver init + app launch overhead

    script, generated = generate_script(test_case, shot)
    start = time.perf_counter()
    data = _run_script(script, wall)
    if data is None and generated:
        data = _run_script(_fallback_script(test_case.input, shot), wall)
    elapsed = round((time.perf_counter() - start) * 1000, 1)

    if data is None:
        return ChannelResult(
            channel="mobile",
            actual="",
            timed_out=True,
            crashed=True,
            latency_ms=elapsed,
            error="mobile script produced no result (timeout/crash)",
            screenshot=shot,
        )
    return ChannelResult(
        channel="mobile",
        actual=str(data.get("actual", "")).strip(),
        latency_ms=float(data.get("latency_ms") or elapsed),
        crashed=bool(data.get("crashed", False)),
        screenshot=str(data.get("screenshot", shot)),
        status_code=200,
    )
