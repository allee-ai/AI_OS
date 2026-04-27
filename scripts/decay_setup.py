"""Install a daily reflex trigger that runs scripts/decay_facts.py.

Idempotent: updates in place if a trigger with the same name exists.
Default schedule: 03:30 every day (quiet hour).
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402
from agent.threads.reflex.schema import (  # noqa: E402
    init_triggers_table,
    create_trigger,
)

NAME = "identity-decay"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cron", default="30 3 * * *",
                   help="Five-field cron expression (default '30 3 * * *' = 03:30 daily).")
    args = p.parse_args()

    tool_params = {"command": ".venv/bin/python scripts/decay_facts.py"}

    with closing(get_connection()) as conn:
        init_triggers_table(conn)
        existing = conn.execute(
            "SELECT id FROM reflex_triggers WHERE name = ?", (NAME,)
        ).fetchone()

    if existing:
        with closing(get_connection()) as conn:
            conn.execute(
                """UPDATE reflex_triggers
                   SET cron_expression = ?, enabled = 1,
                       trigger_type = 'schedule', response_mode = 'tool',
                       tool_name = 'terminal', tool_action = 'run_command',
                       tool_params_json = ?
                   WHERE id = ?""",
                (args.cron, json.dumps(tool_params), existing["id"]),
            )
            conn.commit()
        print(f"updated trigger #{existing['id']} ({NAME}): cron='{args.cron}'")
        return 0

    trigger_id = create_trigger(
        name=NAME,
        feed_name="schedule",
        event_type="cron_fired",
        tool_name="terminal",
        tool_action="run_command",
        description="Decay/prune learned identity facts daily.",
        trigger_type="schedule",
        cron_expression=args.cron,
        tool_params=tool_params,
        priority=3,
        response_mode="tool",
    )
    print(f"created trigger #{trigger_id} ({NAME}): cron='{args.cron}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
