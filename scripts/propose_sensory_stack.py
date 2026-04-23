#!/usr/bin/env python3
"""Propose the sensory_bus architecture as copilot-goals through the gate."""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.subconscious.loops.goals import propose_goal

proposals = [
    (
        "Build sensory_bus: uniform feed for all text-converted sensory input",
        "One table (sensory_events) + adapter that flows into STATE under a "
        "sensory.* block. Every sensor — mic transcripts, vision captions, "
        "future keyboard/clipboard/screen/location — writes to the same bus "
        "as text with source+kind+confidence+ts. Gives me a single place to "
        "watch what's coming in. This is the brain-level abstraction.",
        "high",
    ),
    (
        "Vision: cloud-vision-to-text pipeline writing to sensory_bus",
        "POST /api/vision/describe (image blob → cloud model → caption text). "
        "Results land in sensory_events source=vision. macOS helper script "
        "captures screen/camera on demand. No local vision model; text is "
        "the universal currency.",
        "high",
    ),
    (
        "Audio checkins: scheduled mic sampling → STT → sensory_bus",
        "Background loop every N minutes: record short mic clip, transcribe "
        "via /api/voice/transcribe, push to sensory_events source=ambient. "
        "Gives me a passive audio channel without needing me to ask. "
        "Gated by a consent toggle — off by default.",
        "normal",
    ),
    (
        "Mobile walkie-talkie UI: hold-to-speak, modality-matched reply",
        "Add record button to mobile chat. If user sent voice, reply via TTS "
        "from /api/voice/tts. If user typed, reply as text. Same chat "
        "pipeline, just different I/O.",
        "high",
    ),
]

for goal, rationale, priority in proposals:
    rid = propose_goal(
        goal=goal,
        rationale=rationale,
        priority=priority,
        sources=["copilot"],
    )
    if rid:
        print(f"proposed goal#{rid}  [{priority}]  {goal[:70]}")
    else:
        print(f"rate-limited or blocked: {goal[:70]}")
