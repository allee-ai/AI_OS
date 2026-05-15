"""One-shot logger: vre-construction.com deployed live with TLS."""
from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import log_event  # noqa: E402
from data.db import get_connection  # noqa: E402


def main() -> None:
    events = []
    events.append(
        log_event(
            "system",
            "vre-construction.com is LIVE. HTTPS 200, www->apex 301, Let's Encrypt certs obtained for "
            "vre-construction.com, www.vre-construction.com, vanguardrelocations.com, www.vanguardrelocations.com. "
            "Site served from AIOS droplet (24.144.115.72) via Caddy reverse-proxy. "
            "/contact-submit routes to local form-server on 127.0.0.1:8042 (droplet-bound).",
            thread_subject="vre_construction_launch",
            tags=["deploy", "live", "tls", "complete", "reconstruction"],
        )
    )
    events.append(
        log_event(
            "system",
            "Caddy reload bug encountered + fixed: new site blocks referenced log files in /var/log/caddy/ "
            "that didn't exist with caddy ownership. systemctl reload looped failing; full restart resolved "
            "after touch + chown caddy:caddy on the new log files. Lesson: pre-create per-domain log files "
            "with correct ownership before reload, not just on first request.",
            thread_subject="caddy_ops_lesson",
            tags=["caddy", "ops", "lesson", "infra"],
        )
    )

    # Resolve goal #70 (Namecheap DNS) — both name servers now point to AIOS droplet
    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE proposed_goals SET status='done', resolved_at=CURRENT_TIMESTAMP WHERE id = ?",
            (70,),
        )
        conn.commit()

    print(f"logged events: {events}; resolved goal #70")


if __name__ == "__main__":
    main()
