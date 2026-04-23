#!/usr/bin/env python3
"""Regenerate the live-status block in allee-ai.github.io/aios.html.

Pulls real numbers from the AI_OS database so the marketing page can't lie
about the system. Idempotent — rerun anytime. Never pushes to git; user pushes.

Injects between two markers:
    <!-- BEGIN live-status -->  ...  <!-- END live-status -->
"""
from __future__ import annotations

import inspect
import re
import subprocess
import sys
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402

SITE_DIR = ROOT / "workspace" / "allee-ai.github.io"
AIOS_HTML = SITE_DIR / "aios.html"
BEGIN_MARKER = "<!-- BEGIN live-status -->"
END_MARKER = "<!-- END live-status -->"


# ------------------------------------------------------------------ queries


def _count(conn, sql: str, *args) -> int:
    try:
        return conn.execute(sql, args).fetchone()[0] or 0
    except Exception:
        return 0


def _builtin_loop_count() -> int:
    """Count loops defined in code (not DB) — these live as Python classes
    in agent/subconscious/loops/manager.py:create_default_loops().
    """
    try:
        from agent.subconscious.loops import manager as m
        src = inspect.getsource(m.create_default_loops)
        # Each loop is registered via `manager.add(<instance>)`. Count those.
        return src.count("manager.add(")
    except Exception:
        return 0


def collect_stats() -> dict:
    with closing(get_connection(readonly=True)) as c:
        # Threads: 7 core subconscious threads (identity, log, form, reflex,
        # chat, workspace, goals) + sensory. Hardcode honestly.
        threads = 8
        registry = _count(c, "SELECT COUNT(*) FROM form_tools")

        loops_builtin = _builtin_loop_count()
        loops_custom = _count(c, "SELECT COUNT(*) FROM custom_loops")
        loops_total = loops_builtin + loops_custom

        philosophy_facts = _count(
            c,
            "SELECT COUNT(*) FROM philosophy_profile_facts "
            "WHERE profile_id='value_system.machine'",
        )
        # Identity lives in the identity thread's profile_facts table.
        identity_facts = _count(c, "SELECT COUNT(*) FROM profile_facts")

        # No "concepts" table; we only track edges. Count distinct nodes via union.
        concepts = _count(
            c,
            "SELECT COUNT(*) FROM ("
            "SELECT concept_a AS c FROM concept_links "
            "UNION SELECT concept_b FROM concept_links)",
        )
        links = _count(c, "SELECT COUNT(*) FROM concept_links")

        goals_open = _count(
            c,
            "SELECT COUNT(*) FROM proposed_goals "
            "WHERE status IN ('pending','approved')",
        )
        meta_thoughts = _count(c, "SELECT COUNT(*) FROM reflex_meta_thoughts")
        sensory_events = _count(c, "SELECT COUNT(*) FROM sensory_events")
        sensory_consent_on = _count(
            c, "SELECT COUNT(*) FROM sensory_consent WHERE enabled=1"
        )
        sensory_consent_total = _count(c, "SELECT COUNT(*) FROM sensory_consent")

    # git HEAD + commit count
    try:
        rev = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True
        ).strip()
        commits = int(
            subprocess.check_output(
                ["git", "-C", str(ROOT), "rev-list", "--count", "HEAD"], text=True
            ).strip()
        )
        last = subprocess.check_output(
            ["git", "-C", str(ROOT), "log", "-1", "--format=%s%n%ci"], text=True
        ).strip().splitlines()
        last_subject = last[0] if last else ""
        last_date = last[1] if len(last) > 1 else ""
    except Exception:
        rev, commits, last_subject, last_date = "?", 0, "", ""

    return {
        "threads": threads,
        "registry": registry,
        "loops_builtin": loops_builtin,
        "loops_custom": loops_custom,
        "loops_total": loops_total,
        "philosophy_facts": philosophy_facts,
        "identity_facts": identity_facts,
        "concepts": concepts,
        "links": links,
        "goals_open": goals_open,
        "meta_thoughts": meta_thoughts,
        "sensory_events": sensory_events,
        "sensory_consent_on": sensory_consent_on,
        "sensory_consent_total": sensory_consent_total,
        "rev": rev,
        "commits": commits,
        "last_subject": last_subject,
        "last_date": last_date,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="minutes"),
    }


# ------------------------------------------------------------------ render


def render_block(s: dict) -> str:
    if s["loops_total"]:
        loops_line = (
            f"{s['loops_total']} defined "
            f"({s['loops_builtin']} built-in + {s['loops_custom']} custom) &middot; "
            f'<span style="opacity:.6">none auto-started — user opts in per loop</span>'
        )
    else:
        loops_line = "none defined yet"

    return f"""{BEGIN_MARKER}
<!-- Auto-generated by scripts/update_aios_page.py — do not hand-edit. -->
<section class="main">
    <header class="major">
        <h2>Live Status</h2>
        <p>Honest numbers pulled from the running system at build time, not marketing claims.</p>
    </header>
    <div class="table-wrapper">
        <table>
            <tbody>
                <tr><td><strong>Commit</strong></td>
                    <td><code>{s['rev']}</code> &middot; {s['commits']} commits total</td></tr>
                <tr><td><strong>Last change</strong></td>
                    <td>{s['last_subject']} <span style="opacity:.6">({s['last_date']})</span></td></tr>
                <tr><td><strong>Thread modules</strong></td>
                    <td>{s['threads']} &middot; {s['registry']} tools in the form registry</td></tr>
                <tr><td><strong>Background loops</strong></td>
                    <td>{loops_line}</td></tr>
                <tr><td><strong>Identity facts</strong></td>
                    <td>{s['identity_facts']} stored about the user + their world</td></tr>
                <tr><td><strong>Philosophy (values)</strong></td>
                    <td>{s['philosophy_facts']} written values in <code>value_system.machine</code></td></tr>
                <tr><td><strong>Concept graph</strong></td>
                    <td>{s['concepts']:,} concepts &middot; {s['links']:,} links</td></tr>
                <tr><td><strong>Self-reflections</strong></td>
                    <td>{s['meta_thoughts']} meta-thoughts logged</td></tr>
                <tr><td><strong>Open goals</strong></td>
                    <td>{s['goals_open']} proposed or approved</td></tr>
                <tr><td><strong>Sensory bus</strong></td>
                    <td>{s['sensory_events']} events recorded &middot;
                        {s['sensory_consent_on']}/{s['sensory_consent_total']} sources consented
                        <span style="opacity:.6">(off by default)</span></td></tr>
            </tbody>
        </table>
    </div>
    <p style="opacity:.55;font-size:.85em;text-align:center;margin-top:1em">
        generated {s['generated_at']} UTC
    </p>
</section>
{END_MARKER}
"""


# ------------------------------------------------------------------ inject


def inject(html: str, block: str) -> str:
    if BEGIN_MARKER in html and END_MARKER in html:
        pattern = re.compile(
            re.escape(BEGIN_MARKER) + r".*?" + re.escape(END_MARKER), re.DOTALL
        )
        return pattern.sub(block.rstrip("\n"), html)

    anchor = "<!-- Live Demo -->"
    if anchor in html:
        return html.replace(anchor, block + "\n" + anchor)
    anchor2 = "<!-- Key Features -->"
    if anchor2 in html:
        return html.replace(anchor2, block + "\n" + anchor2)
    raise RuntimeError("Could not find anchor to insert live-status block")


def main() -> int:
    if not AIOS_HTML.exists():
        print(f"error: {AIOS_HTML} not found", file=sys.stderr)
        return 1

    stats = collect_stats()
    print("stats:")
    for k, v in stats.items():
        print(f"  {k:22s} {v}")

    html = AIOS_HTML.read_text()
    block = render_block(stats)
    new_html = inject(html, block)

    if new_html == html:
        print("no change (block already current)")
        return 0

    AIOS_HTML.write_text(new_html)
    print(f"\nupdated: {AIOS_HTML.relative_to(ROOT)}")
    print(f"review with: git -C {SITE_DIR.relative_to(ROOT)} diff aios.html")
    print("then push from the site repo when you're happy with it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
