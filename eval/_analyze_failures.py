#!/usr/bin/env python3
"""Analyze eval failures in detail."""
import sqlite3, json

db = sqlite3.connect('data/db/state_demo.db')

for eval_name in ['retrieval_precision', 'fact_recall', 'hallucination', 'tier_comparison', 'tool_use', 'injection_resistance', 'state_drift']:
    row = db.execute(
        'SELECT status, score, passed, total, details_json FROM eval_runs WHERE eval_name=? AND status != "running" ORDER BY created_at DESC LIMIT 1',
        (eval_name,)
    ).fetchone()
    if not row:
        continue
    status, score, passed, total, details_json = row
    details = json.loads(details_json) if details_json else []
    print(f"{'='*60}")
    print(f"{eval_name}: {status} score={score} {passed}/{total}")
    print(f"{'='*60}")
    for d in details:
        s = "PASS" if d.get("passed") else "FAIL"
        label = d.get("prompt", d.get("query", d.get("attack_type", "")))
        if isinstance(label, str):
            label = label[:65]
        print(f"  [{s}] {label}")
        # Show key diagnostic fields
        for k in ['error', 'expected_thread', 'actual_top', 'keyword_hits', 'min_required',
                   'has_state_context', 'semantic_score', 'combined_score', 'category',
                   'attack_type', 'identity_held']:
            if k in d and d[k] is not None:
                print(f"       {k}: {d[k]}")
        if not d.get("passed") and "response_preview" in d:
            resp = d["response_preview"][:150].replace("\n", " ")
            print(f"       response: {resp}")
    print()

db.close()
