"""Dump actual responses from saved eval runs for inspection."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eval.schema import get_run

# V2-final, V2-best, V1, T0-base
run_ids = ['a9108b0c', 'f2a22bd2', '25bcd806', 'd47cfa80']

for run_id in run_ids:
    r = get_run(run_id)
    if not r:
        print(f"Run {run_id} not found")
        continue
    details = json.loads(r['details_json']) if isinstance(r['details_json'], str) else r['details_json']
    print(f"\n{'='*70}")
    print(f"  {r['model']}  |  score: {r['score']}  |  run: {run_id}")
    print(f"{'='*70}")
    for d in details:
        mark = 'Y' if d['passed'] else 'N'
        print(f"\n  [{mark}] {d['prompt']}")
        print(f"      hits: {d.get('keyword_hits','?')}/{d.get('min_required','?')}")
        resp = d.get('response_preview', '')
        # Print full response preview, wrapped
        for i in range(0, len(resp), 100):
            prefix = "  >>> " if i == 0 else "      "
            print(f"{prefix}{resp[i:i+100]}")
