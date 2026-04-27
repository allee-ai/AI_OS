#!/usr/bin/env python3
"""One-off: prune cooccurrence pairs containing known hub keys.

Hub keys are structural-metadata facts that appear at the top of every STATE
for their section. They co-fire with everything, so their pair counts are
zero-information noise. Going forward they're filtered at pair-recording
time (see _HUB_KEYS in orchestrator.py); this script removes the legacy
rows accumulated before that filter existed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import get_connection

HUB_KEYS = (
    "form.tools._usage",
    "form.env.local",
    "form.env.vm",
    "linking_core.function",
    "linking_core.mechanism",
    "log.session.duration",
)


def main() -> int:
    total = 0
    with get_connection() as conn:
        # legacy bare env.* keys (pre-prefix fix)
        cur = conn.execute(
            "SELECT COUNT(*) FROM key_cooccurrence "
            "WHERE key_a LIKE 'env.%' OR key_b LIKE 'env.%'"
        )
        n_env = cur.fetchone()[0]
        conn.execute(
            "DELETE FROM key_cooccurrence "
            "WHERE key_a LIKE 'env.%' OR key_b LIKE 'env.%'"
        )
        total += n_env
        for k in HUB_KEYS:
            cur = conn.execute(
                "SELECT COUNT(*) FROM key_cooccurrence "
                "WHERE key_a = ? OR key_b = ?",
                (k, k),
            )
            n = cur.fetchone()[0]
            if n:
                conn.execute(
                    "DELETE FROM key_cooccurrence "
                    "WHERE key_a = ? OR key_b = ?",
                    (k, k),
                )
                print(f"  {k}: {n} rows pruned")
                total += n
        conn.commit()
    print(f"total pruned: {total} rows (legacy env.*: {n_env})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
