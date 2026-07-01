"""Robust extraction of JSON / code from chatty small-model output."""

from __future__ import annotations

from swarm_qa.extract import extract_json, strip_code_fences


def test_extract_json_from_fenced_prose():
    txt = 'Sure!\n```json\n{"verdict": "PASS", "pertinence": 5}\n```\nHope that helps.'
    obj = extract_json(txt)
    assert obj["verdict"] == "PASS"
    assert obj["pertinence"] == 5


def test_extract_json_nested():
    txt = 'noise {"a": {"b": 1}, "c": [1, 2]} tail'
    assert extract_json(txt) == {"a": {"b": 1}, "c": [1, 2]}


def test_extract_json_skips_unparseable_first_brace():
    txt = 'prose {not json} then {"ok": true}'
    assert extract_json(txt) == {"ok": True}


def test_extract_json_none():
    assert extract_json("no json here") == {}


def test_strip_code_fences():
    code = "```python\nimport x\nprint(1)\n```"
    assert strip_code_fences(code) == "import x\nprint(1)"
