"""Tracing tests — noop path (no LANGFUSE_SECRET_KEY set in CI)."""

from __future__ import annotations

import pytest
from agentkit.tracing import trace_span
from agentkit.tracing.langfuse import _get_client


def test_trace_span_executes_body() -> None:
    result = []
    with trace_span("test.span", model="qwen2.5:3b", agent="financial"):
        result.append(1)
    assert result == [1]


def test_trace_span_propagates_exceptions() -> None:
    with pytest.raises(ValueError, match="boom"), trace_span("test.error"):
        raise ValueError("boom")


def test_no_langfuse_client_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without LANGFUSE_SECRET_KEY the client must be None (graceful noop)."""
    import agentkit.tracing.langfuse as lf_mod

    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    # Reset cached state so _get_client() re-evaluates
    lf_mod._lf = None
    lf_mod._lf_checked = False
    client = _get_client()
    assert client is None
    # Restore cache so other tests are not affected
    lf_mod._lf = None
    lf_mod._lf_checked = False


def test_trace_span_noop_when_no_langfuse(monkeypatch: pytest.MonkeyPatch) -> None:
    """trace_span works as a noop when Langfuse is not configured."""
    import agentkit.tracing.langfuse as lf_mod

    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    lf_mod._lf = None
    lf_mod._lf_checked = False
    ran = []
    with trace_span("test.noop"):
        ran.append(True)
    assert ran == [True]
    lf_mod._lf = None
    lf_mod._lf_checked = False
