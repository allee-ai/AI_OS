#!/usr/bin/env python3
"""
scripts/mic.py — push-to-talk microphone for AI_OS.

Press Enter, speak, press Enter again. Transcribes via faster-whisper
and either prints to stdout, pings yourself, or forwards to VS Code.

Usage:
    .venv/bin/python scripts/mic.py                       # transcribe + print
    .venv/bin/python scripts/mic.py --ping                # send as ping.py
    .venv/bin/python scripts/mic.py --vs                  # forward into chat
    .venv/bin/python scripts/mic.py --loop                # stay open, transcribe repeatedly
    .venv/bin/python scripts/mic.py --device 2            # pick mic (default 2 = MBA mic)
    .venv/bin/python scripts/mic.py --model small.en      # whisper model size

First run downloads the model (~150MB for small.en, ~75MB for base.en).
"""
from __future__ import annotations
import argparse
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DEVICE = "2"        # MacBook Air Microphone on this machine
DEFAULT_MODEL = "small.en"  # good balance; .en is English-only but 2x faster


def record(device: str, out_path: Path) -> None:
    """Record from the mic until the user hits Enter a second time."""
    print(f"[mic] recording from device :{device}  —  press Enter to stop", flush=True)
    # ffmpeg: avfoundation audio-only (video=none), mono 16k wav
    proc = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-f", "avfoundation",
            "-i", f":{device}",
            "-ac", "1", "-ar", "16000",
            "-loglevel", "error",
            str(out_path),
        ],
        stdin=subprocess.PIPE,
    )
    try:
        input()  # wait for Enter
    except (EOFError, KeyboardInterrupt):
        pass
    # graceful stop — ffmpeg flushes on 'q' or SIGINT
    try:
        if proc.stdin:
            proc.stdin.write(b"q")
            proc.stdin.flush()
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


_MODEL = None


def transcribe(wav_path: Path, model_name: str) -> str:
    global _MODEL
    from faster_whisper import WhisperModel
    if _MODEL is None:
        print(f"[mic] loading whisper model={model_name} (first run downloads)...", flush=True)
        # int8 is fast on CPU; Apple Silicon will still benefit
        _MODEL = WhisperModel(model_name, device="cpu", compute_type="int8")
    t0 = time.perf_counter()
    segments, info = _MODEL.transcribe(
        str(wav_path),
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=300),
    )
    text = " ".join(s.text.strip() for s in segments).strip()
    dt = time.perf_counter() - t0
    dur = getattr(info, "duration", 0.0) or 0.0
    print(f"[mic] transcribed {dur:.1f}s audio in {dt:.1f}s", flush=True)
    return text


def dispatch(text: str, *, ping: bool, vs: bool) -> None:
    if not text:
        print("[mic] (empty transcription)")
        return
    print(f"\n>>> {text}\n")
    if ping:
        subprocess.run(
            [sys.executable, "scripts/ping.py", text,
             "--priority", "normal", "--source", "voice"],
            cwd=ROOT, check=False,
        )
    if vs:
        # Reuse the vs_bridge forward path so the ritual header is prepended
        try:
            from agent.services.vs_bridge import forward
            forward(text, source="voice")
            print("[mic] forwarded to VS Code")
        except Exception as e:
            print(f"[mic] vs forward failed: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default=os.environ.get("AIOS_MIC_DEVICE", DEFAULT_DEVICE))
    ap.add_argument("--model", default=os.environ.get("AIOS_WHISPER_MODEL", DEFAULT_MODEL))
    ap.add_argument("--ping", action="store_true", help="send transcript as a ping")
    ap.add_argument("--vs", action="store_true", help="forward transcript to VS Code Chat")
    ap.add_argument("--loop", action="store_true", help="keep listening in a loop")
    ap.add_argument("--keep", action="store_true", help="keep the wav file")
    args = ap.parse_args()

    while True:
        try:
            input("[mic] press Enter to start recording (Ctrl+C to quit)... ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        tmp = Path(tempfile.mkstemp(suffix=".wav", prefix="aios_mic_")[1])
        try:
            record(args.device, tmp)
            if not tmp.exists() or tmp.stat().st_size < 1000:
                print("[mic] recording empty or failed")
                continue
            text = transcribe(tmp, args.model)
            dispatch(text, ping=args.ping, vs=args.vs)
        finally:
            if not args.keep:
                try:
                    tmp.unlink(missing_ok=True)
                except Exception:
                    pass

        if not args.loop:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
