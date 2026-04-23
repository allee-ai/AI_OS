"""
scripts/wifi_collector.py — feed the field thread with privacy-safe wifi observations.

Collects what macOS makes available without elevated permissions or
Location Services:
  - Connection metadata of the joined network (channel/phy/security)
  - Count of other locally-visible networks (coarse environment density)

When real BSSID is unavailable (macOS hides it without Location perm), we
synthesize a stable fingerprint from connection metadata. Same network →
same fingerprint within a session, different across networks.

All identifiers are hashed by the field schema before insert. Raw values
never touch disk.

Usage:
    .venv/bin/python scripts/wifi_collector.py --once
    .venv/bin/python scripts/wifi_collector.py --watch --interval 300
    .venv/bin/python scripts/wifi_collector.py --once --env home
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _system_profiler() -> str:
    try:
        return subprocess.run(
            ["system_profiler", "SPAirPortDataType"],
            capture_output=True, text=True, timeout=15,
        ).stdout
    except Exception:
        return ""


def _parse_current(text: str) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {
        "ssid": None, "bssid": None, "signal": None,
        "channel": None, "phy": None, "security": None,
    }
    if not text or "Current Network Information:" not in text:
        return out

    block = text.split("Current Network Information:")[1]
    block = block.split("Other Local Wi-Fi Networks:")[0]

    # SSID line: indented, ends in ':'. Skipped if redacted.
    for line in block.splitlines():
        s = line.strip()
        if not s or s == "<redacted>:":
            continue
        if s.endswith(":") and ":" not in s[:-1] and "<" not in s:
            out["ssid"] = s.rstrip(":").strip()
            break

    m = re.search(r"BSSID:\s*([0-9a-fA-F:]+)", block)
    if m:
        out["bssid"] = m.group(1)
    m = re.search(r"Signal\s*/\s*Noise:\s*(-?\d+)\s*dBm", block)
    if m:
        out["signal"] = m.group(1)
    m = re.search(r"Channel:\s*([\d]+\s*\([^)]+\))", block)
    if m:
        out["channel"] = m.group(1).strip()
    m = re.search(r"PHY Mode:\s*([^\n]+)", block)
    if m:
        out["phy"] = m.group(1).strip()
    m = re.search(r"Security:\s*([^\n]+)", block)
    if m:
        out["security"] = m.group(1).strip()
    return out


def _count_others(text: str) -> int:
    if "Other Local Wi-Fi Networks:" not in text:
        return 0
    block = text.split("Other Local Wi-Fi Networks:")[1]
    return len(re.findall(r"^\s+Channel:", block, re.MULTILINE))


def _synthesize_fingerprint(parsed: Dict[str, Optional[str]]) -> Optional[str]:
    """Build a stable pseudo-BSSID from available metadata when real one is
    hidden by macOS privacy."""
    parts = [parsed.get("channel"), parsed.get("phy"), parsed.get("security")]
    parts = [p for p in parts if p]
    if not parts:
        return None
    digest = hashlib.sha1("|".join(parts).encode()).hexdigest()[:12]
    return ":".join(digest[i:i + 2] for i in range(0, 12, 2))


def collect_once(env_label: Optional[str] = None) -> Dict[str, object]:
    text = _system_profiler()
    current = _parse_current(text)
    others = _count_others(text)

    summary: Dict[str, object] = {
        "ssid_present": bool(current.get("ssid")),
        "bssid_present": bool(current.get("bssid")),
        "fingerprint_synthesized": False,
        "others_visible": others,
        "wrote_observation": False,
        "env_id": None,
    }

    bssid = current.get("bssid")
    if not bssid:
        bssid = _synthesize_fingerprint(current)
        if bssid:
            summary["fingerprint_synthesized"] = True

    if not bssid:
        return summary

    from agent.threads.field import schema as fs
    fs.init_field_tables()

    if env_label:
        env_name = env_label
    else:
        ssid = current.get("ssid")
        if not ssid or "redact" in ssid.lower():
            ssid = f"net-{others}peers"
        env_name = re.sub(r"[^A-Za-z0-9 _-]", "", ssid).strip() or "unknown-net"

    env_id = fs.upsert_environment(env_name, kind="unknown", wifi_bssid=bssid)

    rssi: Optional[int] = None
    if current.get("signal"):
        try:
            rssi = int(current["signal"])
        except Exception:
            pass
    fs.record_observation(bssid, "wifi", env_id, rssi)
    summary["wrote_observation"] = True
    summary["env_id"] = env_id
    return summary


def watch(interval: int, env_label: Optional[str] = None) -> int:
    print(f"[wifi_collector] watching every {interval}s (env={env_label or 'auto'})")
    try:
        while True:
            try:
                r = collect_once(env_label=env_label)
                ts = time.strftime("%H:%M:%S")
                print(f"[{ts}] env={r.get('env_id')} wrote={r.get('wrote_observation')} "
                      f"others_visible={r.get('others_visible')} "
                      f"synthesized={r.get('fingerprint_synthesized')}")
            except Exception as e:
                print(f"[err] {e}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[wifi_collector] stopped")
        return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--once", action="store_true")
    p.add_argument("--watch", action="store_true")
    p.add_argument("--interval", type=int, default=300)
    p.add_argument("--env", help="Force environment label")
    args = p.parse_args()

    if args.watch:
        return watch(args.interval, args.env)

    r = collect_once(env_label=args.env)
    print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
