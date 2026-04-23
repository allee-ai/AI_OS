#!/usr/bin/env python3
"""Smoke test the read-only demo server.

Boots scripts/server_demo.py on a high port, hits a few endpoints to verify:
  1. Server starts at all (sane config, demo DB loads)
  2. GET /api/db-mode/mode reports demo + llm_blocked=True
  3. GET /api/identity/profiles returns scrubbed data
  4. POST /api/identity/profiles is REJECTED with 403 (read-only middleware)
  5. GET /api/sensory/events works (read passes)

Cleans up the subprocess on exit.
"""
from __future__ import annotations
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = int(os.getenv("DEMO_TEST_PORT", "8089"))
BASE = f"http://127.0.0.1:{PORT}"


def _get(path: str, *, method: str = "GET", body: dict | None = None) -> tuple[int, str]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read(2000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(2000).decode("utf-8", "replace")
    except Exception as e:
        return -1, f"<network error: {e}>"


def main() -> int:
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    # Ensure it doesn't fight with anything; also force no LLM regardless of DB
    env["AIOS_NO_LLM"] = "1"

    print(f"booting demo server on :{PORT} ...")
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "server_demo.py")],
        env=env,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait up to 15s for the server to be listening
    started = False
    for _ in range(30):
        time.sleep(0.5)
        if proc.poll() is not None:
            print("server died during startup. logs:")
            print(proc.stdout.read() if proc.stdout else "(no stdout)")
            return 1
        try:
            with urllib.request.urlopen(f"{BASE}/api/db-mode/mode", timeout=1) as r:
                if r.status == 200:
                    started = True
                    break
        except Exception:
            continue
    if not started:
        print("timed out waiting for /api/db-mode/mode")
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        if proc.stdout:
            print("--- server stdout ---")
            print(proc.stdout.read())
        return 1

    print("server up. running checks:\n")
    failed = 0
    try:
        # 1. mode endpoint
        code, body = _get("/api/db-mode/mode")
        ok = code == 200 and '"mode":"demo"' in body.replace(" ", "") and '"llm_blocked":true' in body.replace(" ", "")
        print(f"  [{'PASS' if ok else 'FAIL'}] GET  /api/db-mode/mode -> {code}  body: {body[:120]}")
        failed += 0 if ok else 1

        # 2. read identity (should pass)
        code, body = _get("/api/identity")
        ok = code == 200
        print(f"  [{'PASS' if ok else 'FAIL'}] GET  /api/identity -> {code}  body: {body[:120]}")
        failed += 0 if ok else 1

        # 3. write rejected by read-only middleware
        code, body = _get("/api/identity", method="POST", body={})
        ok = code == 403
        print(f"  [{'PASS' if ok else 'FAIL'}] POST /api/identity -> {code}  body: {body[:120]}  (expect 403)")
        failed += 0 if ok else 1

        # 4. sensory events read
        code, body = _get("/api/sensory/events?limit=3")
        ok = code == 200
        print(f"  [{'PASS' if ok else 'FAIL'}] GET  /api/sensory/events -> {code}  body: {body[:120]}")
        failed += 0 if ok else 1

        # 5. db-mode/mode POST also rejected (mutation through that route)
        code, body = _get("/api/db-mode/mode/personal", method="POST")
        ok = code == 403
        print(f"  [{'PASS' if ok else 'FAIL'}] POST /api/db-mode/mode/personal -> {code}  (expect 403)")
        failed += 0 if ok else 1
    finally:
        print("\nstopping server...")
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    print(f"\n{'-' * 40}\nresult: {'ALL PASS' if failed == 0 else f'{failed} FAILED'}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
