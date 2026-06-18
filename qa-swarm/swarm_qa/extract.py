"""
Helpers to pull structured output out of small-model replies.

Local SLMs frequently wrap their answer in prose or ```fences```. These helpers recover
the JSON object / code block we actually asked for, so the pipeline stays robust.
"""

from __future__ import annotations

import json
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    """Return the first balanced ``{...}`` object in *text* as a dict, or ``{}``."""
    start = text.find("{")
    while start != -1:
        depth = 0
        in_str = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    try:
                        obj = json.loads(candidate)
                    except json.JSONDecodeError:
                        break  # try next "{"
                    return obj if isinstance(obj, dict) else {}
        start = text.find("{", start + 1)
    return {}


def strip_code_fences(text: str) -> str:
    """Drop markdown ```python / ``` fences, keeping the code between them when present."""
    lines = text.splitlines()
    if any(ln.strip().startswith("```") for ln in lines):
        out: list[str] = []
        inside = False
        for ln in lines:
            if ln.strip().startswith("```"):
                inside = not inside
                continue
            if inside:
                out.append(ln)
        if out:
            return "\n".join(out).strip()
    return "\n".join(ln for ln in lines if not ln.strip().startswith("```")).strip()
