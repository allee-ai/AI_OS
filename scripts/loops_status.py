"""Survey current state of all loops on the running aios.service.

Usage: scp this to droplet and run, OR run via ssh AIOS to localhost:8000.
"""
import json
import os
import sys
import urllib.request

BASE = os.getenv("AIOS_BASE_URL", "http://127.0.0.1:8000")
TOKEN = os.getenv("AIOS_API_TOKEN", "")


def fetch(path: str):
    req = urllib.request.Request(BASE + path)
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def main() -> int:
    data = fetch("/api/subconscious/loops")
    loops = data.get("loops") or data
    if isinstance(loops, dict) and "loops" in loops:
        loops = loops["loops"]
    print(f"  {'NAME':24s} {'STATUS':10s} {'INTERVAL':>10s}  RUNS")
    print(f"  {'-'*24} {'-'*10} {'-'*10}  ----")
    for l in loops:
        name = l.get("name", "?")
        status = l.get("status", "?")
        iv = l.get("interval_seconds") or l.get("config", {}).get("interval_seconds", 0)
        runs = l.get("total_runs", l.get("stats", {}).get("total_runs", 0))
        print(f"  {name:24s} {status:10s} {float(iv):>8.0f}s  {runs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
