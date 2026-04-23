"""
Mobile Voice API — phone mic → VS Code Copilot → TTS back to phone.

Separate router from /api/mobile/chat by design. The flow:

  Phone                            Mac                           VS Code
  ─────                            ───                           ───────
  tap mic                                                        
  record audio   ──POST /transcribe──▶ whisper
                 ◀── transcript ──
  show + confirm
  tap send       ──POST /send-to-vscode──▶ vs_bridge.forward ──▶ Copilot Chat
                 ◀── ok ──                                        (I respond here)
  poll inbox     ──GET /inbox?after=...──▶                         │
                 ◀── audio url ──                                  │
  play audio                                                       │
                                    ◀── POST /reply ── any process ┘
                                        (I can call this from here to
                                         push my text response back
                                         to phone, TTS'd)

No /api/chat dependency. Holds its own state in-memory (voice_messages).
"""

from __future__ import annotations

import hmac
import io
import os
import re
import subprocess
import tempfile
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api/mobile/voice", tags=["mobile-voice"])

_AUDIO_DIR = Path(tempfile.gettempdir()) / "aios_mobile_voice"
_AUDIO_DIR.mkdir(exist_ok=True)

# In-memory voice inbox: list of {id, text, audio_path, created_at, seen}.
# Small cap so memory doesn't grow unbounded.
_INBOX: List[Dict] = []
_INBOX_MAX = 50

# Lazy whisper model
_WHISPER = None
_WHISPER_MODEL = os.environ.get("AIOS_WHISPER_MODEL", "small.en")


# ── Auth (shared with mobile_api) ────────────────────────────────────────────

def _check_token(x_device_token: Optional[str] = Header(None)):
    expected = os.getenv("AIOS_MOBILE_TOKEN")
    if not expected:
        return
    if not x_device_token:
        raise HTTPException(status_code=401, detail="X-Device-Token header required")
    if not hmac.compare_digest(x_device_token, expected):
        raise HTTPException(status_code=401, detail="Invalid device token")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_whisper():
    global _WHISPER
    if _WHISPER is None:
        from faster_whisper import WhisperModel
        _WHISPER = WhisperModel(_WHISPER_MODEL, device="cpu", compute_type="int8")
    return _WHISPER


def _convert_to_wav(src: Path, dst: Path) -> bool:
    """Use ffmpeg to convert any browser upload (webm/opus/mp4) to mono 16k wav."""
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(src),
             "-ac", "1", "-ar", "16000",
             "-loglevel", "error",
             str(dst)],
            capture_output=True, timeout=30,
        )
        return proc.returncode == 0 and dst.exists() and dst.stat().st_size > 100
    except Exception:
        return False


def _transcribe(wav: Path) -> str:
    model = _get_whisper()
    segments, info = model.transcribe(
        str(wav),
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    return " ".join(s.text.strip() for s in segments).strip()


def _say_to_aiff(text: str, out_path: Path) -> bool:
    """Use macOS `say` to produce an audio file."""
    if not text.strip():
        return False
    try:
        proc = subprocess.run(
            ["say", "-v", os.getenv("AIOS_TTS_VOICE", "Samantha"),
             "-r", os.getenv("AIOS_TTS_RATE", "190"),
             "-o", str(out_path),
             text[:2000]],  # cap so a runaway message doesn't block
            capture_output=True, timeout=60,
        )
        return proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 100
    except Exception:
        return False


def _aiff_to_mp3(aiff: Path, mp3: Path) -> bool:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff),
             "-codec:a", "libmp3lame", "-qscale:a", "4",
             "-loglevel", "error",
             str(mp3)],
            capture_output=True, timeout=30,
        )
        return proc.returncode == 0 and mp3.exists()
    except Exception:
        return False


def _append_inbox(text: str, audio_path: Optional[Path]) -> Dict:
    global _INBOX
    entry = {
        "id": str(uuid.uuid4())[:12],
        "text": text,
        "audio_path": str(audio_path) if audio_path else None,
        "created_at": time.time(),
        "seen": False,
    }
    _INBOX.append(entry)
    if len(_INBOX) > _INBOX_MAX:
        # drop oldest; also clean its file
        old = _INBOX.pop(0)
        try:
            if old.get("audio_path"):
                Path(old["audio_path"]).unlink(missing_ok=True)
        except Exception:
            pass
    return entry


# ── Models ────────────────────────────────────────────────────────────────────

class SendToVSCode(BaseModel):
    text: str
    also_ping: bool = False


class VoiceReply(BaseModel):
    text: str
    speak: bool = True


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/transcribe")
async def transcribe(
    audio: UploadFile = File(...),
    _=Depends(_check_token),
):
    """Accept a browser-recorded audio blob. Return the transcript."""
    suffix = Path(audio.filename or "").suffix or ".webm"
    raw = _AUDIO_DIR / f"in_{uuid.uuid4().hex}{suffix}"
    wav = _AUDIO_DIR / f"in_{uuid.uuid4().hex}.wav"

    try:
        with raw.open("wb") as f:
            f.write(await audio.read())
        if raw.stat().st_size < 500:
            raise HTTPException(status_code=400, detail="Audio too short or empty")

        if not _convert_to_wav(raw, wav):
            raise HTTPException(status_code=500, detail="ffmpeg conversion failed")

        text = _transcribe(wav)
        return {"transcript": text, "audio_size": raw.stat().st_size}
    finally:
        for p in (raw, wav):
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass


@router.post("/send-to-vscode")
async def send_to_vscode(body: SendToVSCode, _=Depends(_check_token)):
    """Forward the (already-transcribed) text to this Mac's VS Code Copilot chat."""
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    prefixed = f"« voice from phone » {text}"

    try:
        from agent.services.vs_bridge import forward
        ok = forward(prefixed, source="phone_voice")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"vs_bridge failed: {e}")

    if body.also_ping:
        try:
            from agent.services.alerts import fire_alerts
            fire_alerts(
                message=f"voice: {text[:80]}",
                priority="default",
                source="phone_voice",
            )
        except Exception:
            pass

    # Log to unified event stream so it appears in log thread
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="mobile_voice:forward",
            data=text[:200],
            metadata={"source": "phone_voice", "chars": len(text)},
            source="mobile_voice",
        )
    except Exception:
        pass

    return {"forwarded": ok, "text": text}


@router.post("/reply")
async def voice_reply(body: VoiceReply, _=Depends(_check_token)):
    """Push a text reply onto the phone's inbox, optionally TTS'd.

    Anyone can call this — a background loop, a Copilot tool call, or a
    manual curl. This is how my response in VS Code makes it back to the
    phone as audio.
    """
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text cannot be empty")

    audio_mp3: Optional[Path] = None
    if body.speak:
        aiff = _AUDIO_DIR / f"rep_{uuid.uuid4().hex}.aiff"
        mp3 = _AUDIO_DIR / f"rep_{uuid.uuid4().hex}.mp3"
        if _say_to_aiff(text, aiff):
            if _aiff_to_mp3(aiff, mp3):
                audio_mp3 = mp3
            try:
                aiff.unlink(missing_ok=True)
            except Exception:
                pass

    entry = _append_inbox(text, audio_mp3)
    return {
        "id": entry["id"],
        "text": entry["text"],
        "has_audio": audio_mp3 is not None,
        "audio_url": f"/api/mobile/voice/audio/{entry['id']}" if audio_mp3 else None,
    }


@router.get("/inbox")
async def voice_inbox(after: float = 0.0, mark_seen: bool = True,
                      _=Depends(_check_token)):
    """Phone polls here. Returns entries created after `after` (unix ts)."""
    fresh = [e for e in _INBOX if e["created_at"] > after]
    out = []
    for e in fresh:
        out.append({
            "id": e["id"],
            "text": e["text"],
            "created_at": e["created_at"],
            "audio_url": (f"/api/mobile/voice/audio/{e['id']}"
                          if e.get("audio_path") else None),
            "seen": e["seen"],
        })
        if mark_seen:
            e["seen"] = True
    latest_ts = max((e["created_at"] for e in _INBOX), default=0.0)
    return {"messages": out, "latest_ts": latest_ts, "count": len(out)}


@router.get("/audio/{msg_id}")
async def voice_audio(msg_id: str):
    for e in _INBOX:
        if e["id"] == msg_id and e.get("audio_path"):
            p = Path(e["audio_path"])
            if p.exists():
                return FileResponse(p, media_type="audio/mpeg",
                                    filename=f"{msg_id}.mp3")
    raise HTTPException(status_code=404, detail="audio not found")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def voice_panel():
    """Serve the mobile voice UI."""
    html_path = Path(__file__).parent / "mobile_voice.html"
    if not html_path.exists():
        return HTMLResponse("<h1>mobile_voice.html missing</h1>", status_code=500)
    return HTMLResponse(html_path.read_text())


@router.get("/health")
async def voice_health():
    return {
        "ok": True,
        "whisper_model": _WHISPER_MODEL,
        "whisper_loaded": _WHISPER is not None,
        "inbox_size": len(_INBOX),
        "audio_dir": str(_AUDIO_DIR),
        "token_required": bool(os.getenv("AIOS_MOBILE_TOKEN")),
    }
