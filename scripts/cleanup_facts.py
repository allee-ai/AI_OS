#!/usr/bin/env python3
"""
Fact Cleanup Script
===================
Purges low-quality profile_facts down to MAX_PER_PROFILE (default 12)
per profile, keeping the highest-weight facts.

Also clears noise from temp_facts (rejects obvious garbage).

Usage:
    python scripts/cleanup_facts.py              # dry run
    python scripts/cleanup_facts.py --apply      # actually delete
    python scripts/cleanup_facts.py --max 20     # keep top 20 per profile
"""

import re
import sys
from pathlib import Path

# Ensure project root is on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MAX_PER_PROFILE = 12

# Patterns that indicate a fact is technical noise, not personal
NOISE_PATTERNS = [
    r"(500 Internal Server Error|404 not found|403 forbidden)",
    r"(GET|POST|PUT|DELETE|PATCH)\s+/",
    r"(\.gitignore|\.env|node_modules|__pycache__|\.pyc)",
    r"(traceback|stacktrace|errno|exception.*error)",
    r"(pip install|npm install|brew install|apt-get)",
    r"(import\s+\w+|from\s+\w+\s+import)",
    r"(localhost:\d+|127\.0\.0\.1|0\.0\.0\.0)",
    r"\.(js|ts|py|json|yaml|yml|md|css|html)$",
    r"(commit\s+[a-f0-9]{7,}|merge\s+branch)",
    r"(Added to|Removed from|Updated|Created|Deleted)\s+\.",
    r"(returns empty|returns null|returns undefined)",
    r"(API endpoint|HTTP status|response code)",
    r"(webpack|vite|eslint|prettier|typescript)",
    r"^(The|This|That)\s+(file|module|function|class|method|variable)",
    r"(def |class |function |const |let |var )",
    r"(\.py\b|\.js\b|\.ts\b|\.jsx\b|\.tsx\b)",
]


def is_noise(text: str) -> bool:
    """Check if a fact text is technical noise."""
    text_lower = text.lower()
    for pattern in NOISE_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    # Too many special chars = code
    special = sum(1 for c in text if c in "{}[]()=><;|&@#$%^*~`")
    if len(text) > 0 and special > len(text) * 0.15:
        return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean up profile_facts")
    parser.add_argument("--apply", action="store_true", help="Actually delete (default: dry run)")
    parser.add_argument("--max", type=int, default=MAX_PER_PROFILE, help="Max facts per profile")
    args = parser.parse_args()

    from data.db import get_connection
    from contextlib import closing

    with closing(get_connection()) as conn:
        cur = conn.cursor()

        # ── Profile facts cleanup ─────────────────────────────
        cur.execute("SELECT DISTINCT profile_id FROM profile_facts")
        profiles = [r[0] for r in cur.fetchall()]

        total_deleted = 0
        total_noise = 0

        for pid in profiles:
            cur.execute(
                "SELECT profile_id, key, l1_value, l2_value, weight, protected, fact_type "
                "FROM profile_facts WHERE profile_id = ? ORDER BY weight DESC, access_count DESC",
                (pid,),
            )
            facts = cur.fetchall()
            print(f"\n{'='*60}")
            print(f"Profile: {pid} ({len(facts)} facts, keeping top {args.max})")
            print(f"{'='*60}")

            # First pass: mark noise
            noise_keys = []
            clean_facts = []
            for f in facts:
                fpid, key, l1, l2, weight, protected, ftype = f
                text = l1 or l2 or ""
                if not protected and is_noise(text):
                    noise_keys.append((fpid, key))
                    total_noise += 1
                else:
                    clean_facts.append(f)

            if noise_keys:
                print(f"  Noise facts to remove: {len(noise_keys)}")

            # Second pass: keep top N from clean facts
            keep = clean_facts[:args.max]
            evict = clean_facts[args.max:]

            evict_keys = [(f[0], f[1]) for f in evict if not f[5]]  # skip protected

            print(f"  Clean facts: {len(clean_facts)}")
            print(f"  Keeping: {len(keep)}")
            print(f"  Evicting (over cap): {len(evict_keys)}")

            # Show what we're keeping
            for f in keep:
                fpid, key, l1, l2, weight, protected, ftype = f
                prot = " [PROTECTED]" if protected else ""
                print(f"  + [{weight:.2f}] {key}: {(l1 or '')[:60]}{prot}")

            # Show a sample of what we're removing
            all_remove = noise_keys + evict_keys
            for fpid, key in all_remove[:5]:
                cur.execute("SELECT key, l1_value, weight FROM profile_facts WHERE profile_id = ? AND key = ?", (fpid, key))
                r = cur.fetchone()
                if r:
                    print(f"  x [{r[2]:.2f}] {r[0]}: {(r[1] or '')[:60]}")
            if len(all_remove) > 5:
                print(f"  ... and {len(all_remove) - 5} more")

            total_deleted += len(all_remove)

            if args.apply and all_remove:
                for fpid, key in all_remove:
                    cur.execute(
                        "DELETE FROM profile_facts WHERE profile_id = ? AND key = ?",
                        (fpid, key),
                    )

        # ── Temp facts cleanup (reject obvious noise) ─────────
        cur.execute(
            "SELECT id, text FROM temp_facts WHERE status IN ('pending', 'pending_review', 'approved')"
        )
        temp_facts = cur.fetchall()
        temp_noise = 0
        for tf_id, tf_text in temp_facts:
            if is_noise(tf_text or ""):
                temp_noise += 1
                if args.apply:
                    cur.execute(
                        "UPDATE temp_facts SET status = 'rejected' WHERE id = ?",
                        (tf_id,),
                    )

        if args.apply:
            conn.commit()

        print(f"\n{'='*60}")
        print(f"SUMMARY")
        print(f"{'='*60}")
        print(f"Profile facts to remove: {total_deleted} (noise: {total_noise})")
        print(f"Temp facts to reject: {temp_noise}")
        if not args.apply:
            print(f"\nDRY RUN — no changes made. Use --apply to execute.")
        else:
            print(f"\nDONE — changes applied.")


if __name__ == "__main__":
    main()
