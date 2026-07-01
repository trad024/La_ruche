"""
Central configuration for the testing backoffice.

Everything is overridable via environment variables so the same pipeline can run
against a local dev SUT, a Dockerised SUT, or a Keycloak-protected deployment, and
so each Swarm agent can use a different SLM (the "un agent = un SLM" idea from the deck).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    # ── Ollama / OpenAI-compatible endpoint ──────────────────────────────────
    ollama_base_url: str = field(
        default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    )
    ollama_api_key: str = field(default_factory=lambda: _env("OLLAMA_API_KEY", "ollama"))

    # ── Per-agent models ─────────────────────────────────────────────────────
    # Default everything to qwen2.5:3b: it fits fully in 4 GB VRAM, does reliable
    # tool-calling (needed for Swarm handoffs) and avoids model-reload thrash when
    # the handoff chain runs. Bump the Executor to qwen2.5:7b for stronger code
    # generation if the GPU budget allows.
    model_generator: str = field(default_factory=lambda: _env("MODEL_GENERATOR", "qwen2.5:3b"))
    model_executor: str = field(default_factory=lambda: _env("MODEL_EXECUTOR", "qwen2.5:3b"))
    model_evaluator: str = field(default_factory=lambda: _env("MODEL_EVALUATOR", "qwen2.5:3b"))
    model_reporter: str = field(default_factory=lambda: _env("MODEL_REPORTER", "qwen2.5:3b"))

    # ── System Under Test (the conversational agent / wealth mesh) ───────────
    sut_api_url: str = field(
        default_factory=lambda: _env("SUT_API_URL", "http://localhost:8000").rstrip("/")
    )
    sut_web_url: str = field(
        default_factory=lambda: _env("SUT_WEB_URL", "http://localhost:5173").rstrip("/")
    )
    sut_chat_path: str = field(default_factory=lambda: _env("SUT_CHAT_PATH", "/api/chat"))
    # Bearer token for the API channel. The orchestrator dev-bypass (no KEYCLOAK_URL)
    # accepts any value; a Keycloak-on run needs a real token here.
    sut_dev_token: str = field(default_factory=lambda: _env("SUT_DEV_TOKEN", "dev-token"))
    # Version label stamped onto a run so two runs can be diffed for regressions.
    sut_version: str = field(default_factory=lambda: _env("SUT_VERSION", "dev"))

    # ── Mobile channel (Appium + Android emulator) ───────────────────────────
    appium_url: str = field(
        default_factory=lambda: _env("APPIUM_URL", "http://localhost:4723").rstrip("/")
    )
    android_device: str = field(default_factory=lambda: _env("ANDROID_DEVICE", "emulator-5554"))
    android_app_package: str = field(
        default_factory=lambda: _env("ANDROID_APP_PACKAGE", "host.exp.exponent")
    )
    android_app_activity: str = field(
        default_factory=lambda: _env("ANDROID_APP_ACTIVITY", ".MainActivity")
    )

    # ── Verdict thresholds (deck slides 15 & 17) ─────────────────────────────
    timeout_seconds: float = field(default_factory=lambda: float(_env("QA_TIMEOUT_SECONDS", "30")))
    min_score_pass: float = field(default_factory=lambda: float(_env("QA_MIN_SCORE_PASS", "3.0")))
    divergence_threshold: float = field(
        default_factory=lambda: float(_env("QA_DIVERGENCE_THRESHOLD", "0.20"))
    )

    @property
    def openai_base_url(self) -> str:
        return f"{self.ollama_base_url}/v1"

    @property
    def sut_chat_url(self) -> str:
        return f"{self.sut_api_url}{self.sut_chat_path}"


settings = Settings()
