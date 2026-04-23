"""
sensory/taxonomy.py — canonical kinds per source.

Not enforced at the DB layer (the `kind` column is free text so we can
extend), but read by the API layer and by writers so we stay consistent.
Adding a new kind = update this file + document why.

Rule: sensory events are EVENT-ORIENTED. A source writes when something
worth noticing happens, not on a clock. Cadence matches rate-of-
meaningful-change. Timer-based sampling is allowed only for `ambient`.
"""
from __future__ import annotations
from typing import Dict, List, TypedDict


class KindSpec(TypedDict):
    description: str
    trigger: str         # when this event fires
    typical_confidence: str


# ───────────────────────────────────────────────────────────────────
# CAMERA — visual sense from the user-facing or world-facing camera.
# Always on-command OR on a detected event. NEVER on a timer.
# ───────────────────────────────────────────────────────────────────
CAMERA_KINDS: Dict[str, KindSpec] = {
    "snapshot": {
        "description": "A single frame captured and captioned by cloud vision.",
        "trigger": "user command: 'look at this', 'what is this', or /api/sensory/camera/snap",
        "typical_confidence": "0.8-0.95",
    },
    "presence": {
        "description": "A face or person entered / left the frame after >5s absence.",
        "trigger": "local face-detect watcher crosses threshold (opt-in, off by default)",
        "typical_confidence": "0.7-0.9",
    },
    "object_change": {
        "description": "A significant object appeared/disappeared in the scene.",
        "trigger": "frame-diff > N% over stable baseline, then caption the delta",
        "typical_confidence": "0.6-0.85",
    },
    "text_in_frame": {
        "description": "Printed/handwritten text detected; OCR'd content attached.",
        "trigger": "user command OR OCR watcher flags >20 chars readable text",
        "typical_confidence": "0.75-0.95",
    },
    "qr_or_barcode": {
        "description": "QR code or barcode scanned; decoded value in text.",
        "trigger": "decoder match in frame",
        "typical_confidence": "1.0 (decoded) or skipped",
    },
    "gesture": {
        "description": "Hand gesture recognized (wave, thumbs-up, point).",
        "trigger": "future — requires gesture model (deferred)",
        "typical_confidence": "0.5-0.8",
    },
}


# ───────────────────────────────────────────────────────────────────
# SCREEN — what's visible on the user's own display.
# Event-driven: app switch, window focus change, explicit capture.
# ───────────────────────────────────────────────────────────────────
SCREEN_KINDS: Dict[str, KindSpec] = {
    "snapshot": {
        "description": "Explicit screen capture + caption.",
        "trigger": "user command: 'read my screen'",
        "typical_confidence": "0.9",
    },
    "app_switch": {
        "description": "Active app changed; store app name + window title only (not pixels).",
        "trigger": "macOS frontmost-app observer fires",
        "typical_confidence": "1.0",
    },
    "window_title": {
        "description": "Frontmost window title changed meaningfully.",
        "trigger": "title diff from last event on same app",
        "typical_confidence": "1.0",
    },
    "ocr_selection": {
        "description": "User selected text / took a screenshot; OCR'd content attached.",
        "trigger": "screenshot file created in ~/Desktop OR clipboard image update",
        "typical_confidence": "0.85",
    },
}


# ───────────────────────────────────────────────────────────────────
# MIC — audio, already converted to text by voice/api.py:/transcribe.
# Mix of event-driven (push-to-talk) and interval-driven (ambient).
# ───────────────────────────────────────────────────────────────────
MIC_KINDS: Dict[str, KindSpec] = {
    "push_to_talk": {
        "description": "User held a button and spoke; full transcript.",
        "trigger": "user UI (mobile walkie-talkie, scripts/mic.py)",
        "typical_confidence": "0.85-0.95",
    },
    "ambient": {
        "description": "Short periodic clip (~4s) during active hours; captioned only if speech detected.",
        "trigger": "every 5-10 min while user is active; off when idle >30 min; opt-in",
        "typical_confidence": "0.5-0.8",
    },
    "wake_word": {
        "description": "Configured wake word detected in ambient stream.",
        "trigger": "future — requires local wake-word model (deferred)",
        "typical_confidence": "0.6-0.9",
    },
    "silence_break": {
        "description": "Long silence followed by speech — signals attention returning.",
        "trigger": "VAD state flip from silent to voiced after >N min",
        "typical_confidence": "1.0 (boolean)",
    },
}


# ───────────────────────────────────────────────────────────────────
# CLIPBOARD — things the user copied. Event-driven always.
# ───────────────────────────────────────────────────────────────────
CLIPBOARD_KINDS: Dict[str, KindSpec] = {
    "text_copy": {
        "description": "User copied text; store content (truncated) + source app if known.",
        "trigger": "pbpaste poll sees content change",
        "typical_confidence": "1.0",
    },
    "url_copy": {
        "description": "User copied a URL; optionally fetch title.",
        "trigger": "copied text matches URL regex",
        "typical_confidence": "1.0",
    },
    "file_copy": {
        "description": "User copied file paths; store paths.",
        "trigger": "clipboard type == file list",
        "typical_confidence": "1.0",
    },
}


# ───────────────────────────────────────────────────────────────────
# SYSTEM — machine-state events that affect presence.
# ───────────────────────────────────────────────────────────────────
SYSTEM_KINDS: Dict[str, KindSpec] = {
    "lock":   {"description": "User locked the laptop.",      "trigger": "IOKit", "typical_confidence": "1.0"},
    "unlock": {"description": "User unlocked the laptop.",    "trigger": "IOKit", "typical_confidence": "1.0"},
    "lid_close": {"description": "Lid closed.",               "trigger": "pmset", "typical_confidence": "1.0"},
    "lid_open":  {"description": "Lid opened.",               "trigger": "pmset", "typical_confidence": "1.0"},
    "idle_start":{"description": "User went idle (>10 min).", "trigger": "HIDIdleTime", "typical_confidence": "1.0"},
    "idle_end":  {"description": "User returned from idle.",  "trigger": "HIDIdleTime", "typical_confidence": "1.0"},
    "battery_low": {"description": "Battery crossed 20%.",    "trigger": "pmset watcher", "typical_confidence": "1.0"},
}


SOURCES: Dict[str, Dict[str, KindSpec]] = {
    "camera":    CAMERA_KINDS,
    "screen":    SCREEN_KINDS,
    "mic":       MIC_KINDS,
    "clipboard": CLIPBOARD_KINDS,
    "system":    SYSTEM_KINDS,
}


def all_kinds() -> List[str]:
    out: List[str] = []
    for kinds in SOURCES.values():
        out.extend(kinds.keys())
    return sorted(set(out))


def describe(source: str, kind: str) -> KindSpec | None:
    return SOURCES.get(source, {}).get(kind)
