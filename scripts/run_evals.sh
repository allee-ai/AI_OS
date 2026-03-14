#!/bin/bash
# Run all evals via API and pretty-print results
curl -s -X POST http://localhost:8000/api/eval/evals/run-all \
  -H "Content-Type: application/json" \
  -d "{\"save\": true, \"overrides\": {}}" \
  | python3 scripts/print_eval.py
