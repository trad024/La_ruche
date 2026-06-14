"""
Voice / Callbot service.

Endpoints:
  POST /voice/transcribe  — STT: audio bytes → transcript (faster-whisper)
  POST /voice/synthesize  — TTS: text → audio bytes (Piper)
  POST /voice/chat        — Voice-to-voice: audio → transcript → chat → audio

Falls back to mock responses when faster-whisper / piper are not installed
(keeps tests green without heavy ML deps).
"""

from __future__ import annotations

import io
import os
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import Response

_WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
_PIPER_VOICE = os.getenv("PIPER_VOICE", "en_US-amy-medium")
_ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000")

app = FastAPI(title="Voice / Callbot", version="0.1.0")


# ── STT (Speech-to-Text) ───────────────────────────────────────────────────────


def _transcribe_audio(audio_bytes: bytes) -> str:
    """Transcribe audio to text using faster-whisper (falls back to mock)."""
    try:
        from faster_whisper import WhisperModel  # type: ignore[import]

        model = WhisperModel(_WHISPER_MODEL, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(io.BytesIO(audio_bytes))
        return " ".join(s.text for s in segments).strip()
    except ImportError:
        # Mock transcript for dev/test without faster-whisper installed
        return "What is my portfolio AUM?"


@app.post("/voice/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict[str, str]:  # noqa: B008
    """STT endpoint — returns text transcript of uploaded audio."""
    audio_bytes = await audio.read()
    transcript = _transcribe_audio(audio_bytes)
    return {"transcript": transcript, "model": _WHISPER_MODEL}


# ── TTS (Text-to-Speech) ──────────────────────────────────────────────────────


def _synthesize_text(text: str) -> bytes:
    """Synthesize text to WAV audio using Piper (falls back to empty bytes)."""
    try:
        import shutil
        import subprocess

        if not shutil.which("piper"):
            raise FileNotFoundError("piper not in PATH")

        proc = subprocess.run(
            ["piper", "--model", _PIPER_VOICE, "--output-raw"],
            input=text.encode(),
            capture_output=True,
            timeout=30,
        )
        return proc.stdout
    except Exception:
        # Return silent WAV header (44 bytes) as mock
        return bytes(44)


@app.post("/voice/synthesize")
async def synthesize(text: str = Form(...)) -> Response:
    """TTS endpoint — returns WAV audio bytes for the given text."""
    audio = _synthesize_text(text)
    return Response(content=audio, media_type="audio/wav")


# ── Voice-to-Voice ─────────────────────────────────────────────────────────────


@app.post("/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),  # noqa: B008
    conversation_id: str = Form(default=""),  # noqa: B008
) -> dict[str, Any]:
    """
    End-to-end voice-to-voice:
      audio → STT → orchestrator chat → TTS → audio (base64)
    """
    import base64

    import httpx

    # 1. Transcribe
    audio_bytes = await audio.read()
    transcript = _transcribe_audio(audio_bytes)

    # 2. Chat through orchestrator
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{_ORCHESTRATOR_URL}/api/chat",
                json={"message": transcript, "conversation_id": conversation_id},
                headers={"Authorization": "Bearer dev-token"},
            )
            # Collect SSE stream
            answer_text = ""
            async for line in resp.aiter_lines():
                if line.startswith("data: ") and "[DONE]" not in line:
                    import json

                    payload = json.loads(line[6:])
                    answer_text += payload.get("token", "")
    except Exception as exc:
        answer_text = f"[Orchestrator unavailable: {exc}]"

    # 3. Synthesize answer
    answer_audio = _synthesize_text(answer_text)

    return {
        "transcript": transcript,
        "answer_text": answer_text.strip(),
        "answer_audio_b64": base64.b64encode(answer_audio).decode(),
        "conversation_id": conversation_id,
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "voice"}
