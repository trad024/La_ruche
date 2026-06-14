"""Voice service tests — no faster-whisper or piper required."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from voice.main import _synthesize_text, _transcribe_audio, app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["service"] == "voice"


def test_transcribe_mock():
    # Without faster-whisper, falls back to mock transcript
    result = _transcribe_audio(b"fake audio bytes")
    assert isinstance(result, str)
    assert len(result) > 0


def test_synthesize_mock():
    # Without piper, falls back to silent WAV bytes
    audio = _synthesize_text("Hello world")
    assert isinstance(audio, bytes)


def test_transcribe_endpoint():
    fake_audio = io.BytesIO(b"RIFF" + b"\x00" * 40)
    r = client.post("/voice/transcribe", files={"audio": ("test.wav", fake_audio, "audio/wav")})
    assert r.status_code == 200
    data = r.json()
    assert "transcript" in data
    assert isinstance(data["transcript"], str)


def test_synthesize_endpoint():
    r = client.post("/voice/synthesize", data={"text": "Your AUM is 20 million dollars."})
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/wav"
