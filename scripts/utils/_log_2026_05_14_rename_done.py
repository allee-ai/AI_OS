"""Log rename completion + resolve goal #69."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import log_event  # noqa: E402

eid = log_event(
    "code_change",
    "Codebase domain rename complete: 'vanguard-reconstruction.com' -> "
    "'vre-construction.com' and 'vanguard-relocations.com' -> "
    "'vanguardrelocations.com'. Touched 9 files + 1 directory rename. "
    "Local form-server reloaded and /health confirms new route map. "
    "Resolves goal #69. Goal #70 (Namecheap DNS) still pending user action.",
    metadata={
        "files_edited": [
            "infra/form_server.py",
            "infra/form_server_droplet.py",
            "infra/_patch_caddy_contact.py",
            "infra/RUNBOOK_form_server.md",
            "infra/RUNBOOK_site_migration.md",
            "workspace/vre-construction/contact.html",
            "workspace/vre-construction/services.html",
            "workspace/vre-construction/index.html",
            "workspace/vre-construction/sales/investor-onepager.md",
            "workspace/allee-ai.github.io/reconstruction/contact.html",
        ],
        "directory_renamed": {
            "from": "workspace/vanguard-reconstruction",
            "to": "workspace/vre-construction",
        },
        "verified": {
            "py_syntax": "ok",
            "form_server_routes": [
                "vre-construction.com",
                "vanguardrelocations.com",
                "allee-ai.com",
            ],
            "remaining_refs": "only historical (in this very log entry's predecessor)",
        },
        "resolves_goal": 69,
        "still_blocked_by": "goal#70 (Namecheap DNS A records to 24.144.115.72)",
    },
    source="machine",
    thread_subject="vre_construction_launch",
    tags=["rename", "complete", "vre", "code_change", "goal_69"],
)

# Resolve goal #69 in the DB.
from data.db import get_connection
from contextlib import closing
with closing(get_connection()) as conn:
    conn.execute(
        "UPDATE proposed_goals SET status='done', resolved_at=CURRENT_TIMESTAMP "
        "WHERE id = ?",
        (69,),
    )
    conn.commit()

print(f"logged event {eid}, resolved goal #69")
