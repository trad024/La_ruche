"""Langfuse tracing — active when LANGFUSE_SECRET_KEY is set, noop otherwise."""

from __future__ import annotations

import contextlib
import os
from collections.abc import Generator
from typing import Any


def _client() -> Any | None:
    secret = os.getenv("LANGFUSE_SECRET_KEY")
    public = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "http://langfuse:3000")
    if not (secret and public):
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(public_key=public, secret_key=secret, host=host)
    except Exception:
        return None


_lf: Any | None = None
_lf_checked = False


def _get_client() -> Any | None:
    global _lf, _lf_checked
    if not _lf_checked:
        _lf = _client()
        _lf_checked = True
    return _lf


@contextlib.contextmanager
def trace_span(name: str, **metadata: Any) -> Generator[None, None, None]:
    """Context manager that records a Langfuse span when configured, otherwise noop."""
    lf = _get_client()
    if lf is None:
        yield
        return

    trace = lf.trace(name=name, metadata=metadata)
    span = trace.span(name=name, input=metadata)
    try:
        yield
        span.end(output={"status": "ok"})
    except Exception as exc:
        span.end(output={"status": "error", "error": str(exc)})
        raise
    finally:
        with contextlib.suppress(Exception):
            lf.flush()
