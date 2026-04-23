"""Send the phone-ready voice-panel ping to Cade.

Includes the bookmarkable URL with ?key= so she just taps and goes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
from contextlib import closing
from data.db import get_connection
from agent.services.alerts import fire_alerts

# Read token from .env
TOKEN = None
env = Path(__file__).resolve().parent.parent / ".env"
for line in env.read_text().splitlines():
    if line.strip().startswith("AIOS_API_TOKEN="):
        TOKEN = line.strip().split("=", 1)[1].strip()
        break

# Get LAN IP
import subprocess
lan_ip = subprocess.run(["ipconfig", "getifaddr", "en0"],
                         capture_output=True, text=True).stdout.strip() or "127.0.0.1"

PORT = os.environ.get("AIOS_PORT", "8080")
URL = f"http://{lan_ip}:{PORT}/api/mobile/voice/?key={TOKEN}"

msg = (
    f"voice panel LIVE — open on phone:\n{URL}\n\n"
    "phone mic → whisper STT → vs code copilot chat → TTS back to phone inbox. "
    "tap mic, speak, review transcript, tap send. i'll reply here and it'll "
    "show up + speak on your phone. must be on same wifi as the mac."
)

# Notification row
with closing(get_connection()) as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL DEFAULT 'alert',
            message TEXT NOT NULL,
            priority TEXT NOT NULL DEFAULT 'normal',
            context TEXT NOT NULL DEFAULT '{}',
            read INTEGER NOT NULL DEFAULT 0,
            dismissed INTEGER NOT NULL DEFAULT 0,
            response TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur = conn.execute(
        "INSERT INTO notifications (type, message, priority, context) VALUES (?,?,?,?)",
        ("voice_panel_live", msg, "high", '{"source":"voice_launch"}'),
    )
    conn.commit()
    nid = cur.lastrowid

# ntfy
fire_alerts(
    message="voice panel live — tap to open: " + URL,
    priority="high", nid=nid, source="voice_launch",
)

print(f"sent. nid={nid}")
print(URL)
