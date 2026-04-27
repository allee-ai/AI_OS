"""One-shot: re-seed sensory_consent from taxonomy + verify email rows exist."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from contextlib import closing
from data.db import get_connection
from sensory.consent import seed_consent_from_taxonomy

added = seed_consent_from_taxonomy()
print(f"seeded {added} new consent rows")

with closing(get_connection(readonly=True)) as conn:
    rows = conn.execute(
        "SELECT source, kind, enabled FROM sensory_consent WHERE source='email' ORDER BY kind"
    ).fetchall()
    print(f"email consent rows: {len(rows)}")
    for r in rows:
        print(f"  {r['source']}/{r['kind']}  enabled={bool(r['enabled'])}")
