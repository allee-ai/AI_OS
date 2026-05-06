#!/usr/bin/env python3
"""Inject `reverse_proxy /contact-submit 127.0.0.1:8042` into both vanguard
site blocks of /etc/caddy/Caddyfile, validate, and reload.

Idempotent: if the line is already present, skip.
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

CADDYFILE = Path("/etc/caddy/Caddyfile")
PROXY_LINE = "    reverse_proxy /contact-submit 127.0.0.1:8042"
SITES = ["vanguard-relocations.com", "vanguard-reconstruction.com"]


def main() -> int:
    src = CADDYFILE.read_text()
    new = src
    for site in SITES:
        if f"reverse_proxy /contact-submit 127.0.0.1:8042" in new:
            # Already in file; check if it's in *both* blocks by counting
            pass
        # Match the opening of the site block: `<site>, www.<site> {` then
        # insert the proxy line right after `encode ...`
        pattern = re.compile(
            rf"(^{re.escape(site)},\s*www\.{re.escape(site)}\s*\{{\s*\n"
            rf"\s*root \*[^\n]+\n"
            rf"\s*encode[^\n]+\n)",
            re.MULTILINE,
        )
        m = pattern.search(new)
        if not m:
            print(f"could not find block for {site}", file=sys.stderr)
            return 1
        block_start = m.group(1)
        # Check if proxy line already in this block
        block_end_idx = new.find("\n}\n", m.end())
        block_text = new[m.start():block_end_idx] if block_end_idx > 0 else ""
        if "reverse_proxy /contact-submit" in block_text:
            print(f"{site}: already has /contact-submit proxy, skipping")
            continue
        replacement = block_start + "\n    # Contact form -> Mac (via SSH reverse tunnel)\n" + PROXY_LINE + "\n"
        new = new[:m.start()] + replacement + new[m.end():]
        print(f"{site}: injected /contact-submit proxy")

    if new == src:
        print("no changes needed")
        return 0

    backup = CADDYFILE.with_suffix(".bak")
    backup.write_text(src)
    CADDYFILE.write_text(new)
    print(f"backup -> {backup}")

    print("validating...")
    r = subprocess.run(
        ["caddy", "validate", "--config", str(CADDYFILE), "--adapter", "caddyfile"],
        capture_output=True, text=True,
    )
    if r.returncode != 0:
        print("VALIDATION FAILED, restoring backup", file=sys.stderr)
        print(r.stderr, file=sys.stderr)
        CADDYFILE.write_text(src)
        return 1
    print(r.stdout or "validate ok")

    print("reloading...")
    r = subprocess.run(["systemctl", "reload", "caddy"], capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        return 1
    print("reload ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
