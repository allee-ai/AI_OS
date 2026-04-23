"""
voice/ — backend voice I/O for AI_OS.

Endpoints:
    POST /api/voice/transcribe  — multipart audio blob → {text}
    POST /api/voice/tts         — {text} → audio/wav stream

STT: faster-whisper (model lazy-loaded, held in process).
TTS: macOS `say` piped through ffmpeg to wav. No extra deps.

This is intentionally boring. Speak → text → chat pipeline → text → speak.
The whole walkie-talkie loop on mobile rides on these two endpoints.
"""
from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

router = APIRouter(prefix="/api/voice", tags=["voice"])

# Lazy-loaded whisper model. None until first transcription.
_WHISPER = None
_WHISPER_LOCK = asyncio.Lock()

_DEFAULT_MODEL = os.environ.get("AIOS_WHISPER_MODEL", "small.en")
_DEFAULT_VOICE = os.environ.get("AIOS_TTS_VOICE", "Samantha")


async def _get_whisper():
    global _WHISPER
    if _WHISPER is not None:
        return _WHISPER
    async with _WHISPER_LOCK:
        if _WHISPER is not None:
            return _WHISPER
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel(_DEFAULT_MODEL, device="cpu", compute_type="int8")
        return _WHISPER


def _transcribe_sync(wav_path: str) -> str:
    from faster_whisper import WhisperModel
    global _WHISPER
    if _WHISPER is None:
        _WHISPER = WhisperModel(_DEFAULT_MODEL, device="cpu", compute_type="int8")
    segments, _ = _WHISPER.transcribe(
        wav_path,
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    return " ".join(s.text.strip() for s in segments).strip()


@router.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> dict:
    """Accept an audio blob (webm/ogg/mp4/wav), return {text}."""
    data = await audio.read()
    if not data or len(data) < 500:
        raise HTTPException(400, "audio too short")

    suffix = Path(audio.filename or "clip.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f_in:
        f_in.write(data)
        in_path = f_in.name
    wav_path = in_path + ".wav"

    try:
        # Normalize whatever the browser sent → 16kHz mono wav for whisper
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", in_path,
            "-ac", "1", "-ar", "16000",
            wav_path,
            "-loglevel", "error",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        if proc.returncode != 0:
            raise HTTPException(500, f"ffmpeg failed: {err.decode()[-300:]}")

        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _transcribe_sync, wav_path)
        return {"text": text or ""}
    finally:
        for p in (in_path, wav_path):
            try:
                os.unlink(p)
            except OSError:
                pass


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    rate: Optional[int] = None  # words per minute


@router.post("/tts")
async def tts(req: TTSRequest) -> Response:
    """Synthesize `text` via macOS `say` and return audio/mpeg (mp3 for mobile)."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "text required")
    if len(text) > 4000:
        text = text[:4000]

    if sys.platform != "darwin":
        raise HTTPException(501, "tts only implemented on macOS (say command)")

    voice = req.voice or _DEFAULT_VOICE
    with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f_aiff:
        aiff_path = f_aiff.name
    mp3_path = aiff_path.replace(".aiff", ".mp3")

    try:
        say_args = ["say", "-v", voice, "-o", aiff_path]
        if req.rate:
            say_args += ["-r", str(req.rate)]
        say_args += ["--", text]
        p1 = await asyncio.create_subprocess_exec(*say_args,
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err = await p1.communicate()
        if p1.returncode != 0:
            raise HTTPException(500, f"say failed: {err.decode()[-300:]}")

        p2 = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y", "-i", aiff_path,
            "-codec:a", "libmp3lame", "-qscale:a", "5",
            mp3_path, "-loglevel", "error",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
        )
        _, err = await p2.communicate()
        if p2.returncode != 0:
            raise HTTPException(500, f"ffmpeg failed: {err.decode()[-300:]}")

        audio = Path(mp3_path).read_bytes()
        return Response(content=audio, media_type="audio/mpeg")
    finally:
        for p in (aiff_path, mp3_path):
            try:
                os.unlink(p)
            except OSError:
                pass


@router.get("/health")
async def health() -> dict:
    return {
        "stt_model": _DEFAULT_MODEL,
        "stt_loaded": _WHISPER is not None,
        "tts_voice": _DEFAULT_VOICE,
        "tts_available": sys.platform == "darwin",
    }
