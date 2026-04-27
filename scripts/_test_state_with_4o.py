"""
Test STATE against gpt-4o (or any OpenAI model) locally.

Three probes, each run twice (with-STATE and control without-STATE).

Probe 1: factual recall — "what's my name and python version?"
         → tests whether STATE actually reaches the model and is read.

Probe 2: contextual judgement — "should i go to bed?"
         → tests whether the model uses idle time / soft_limit / log to answer
           appropriately rather than giving generic sleep advice.

Probe 3: self-reference — "explain linking_core"
         → tests voice baseline: expected to be flat/generic until voice
           accretion is built (this is the BEFORE measurement).

Outputs are saved to data/state_tests/<timestamp>/ for diffing.

Usage:
    .venv/bin/python scripts/_test_state_with_4o.py [--model gpt-4o]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from agent.subconscious import get_subconscious  # noqa: E402

try:
    from openai import OpenAI
except ImportError:
    print("openai SDK missing — pip install openai", file=sys.stderr)
    sys.exit(1)


PROBES = [
    {
        "id": "factual_recall",
        "query": "what's my name and what python version am I running?",
        "expectation": "with STATE: should answer from identity.primary_user.* and machine.python_version. without STATE: should refuse or say it doesn't know.",
    },
    {
        "id": "contextual_judgement",
        "query": "should i go to bed?",
        "expectation": "with STATE: should reference idle time, soft_limit, current time. without STATE: should give generic sleep advice or ask for context.",
    },
    {
        "id": "self_reference",
        "query": "explain linking_core to me in your own words",
        "expectation": "with STATE: should pull from linking_core thread + self/identity. without STATE: should refuse or say it doesn't know what linking_core is. voice baseline — likely flat either way until accretion.",
    },
]


def call_model(client: OpenAI, model: str, system: str | None, user: str) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=800,
        temperature=0.7,
    )
    return {
        "content": resp.choices[0].message.content,
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--out", default=None, help="Output dir (default: data/state_tests/<ts>)")
    args = ap.parse_args()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set — `source ~/.zshrc` or open new terminal tab", file=sys.stderr)
        return 1

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.out) if args.out else REPO / "data" / "state_tests" / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    client = OpenAI(api_key=api_key)
    sub = get_subconscious()

    print(f"model: {args.model}")
    print(f"output: {out_dir}")
    print()

    summary = {"model": args.model, "timestamp": ts, "probes": []}

    for probe in PROBES:
        pid = probe["id"]
        query = probe["query"]
        print(f"=== probe: {pid} ===")
        print(f"query: {query}")

        # Build STATE for this query
        state = sub.get_state(query)
        state_chars = len(state)
        state_tokens_est = int(len(state.split()) * 0.75)
        print(f"STATE: {state_chars} chars, ~{state_tokens_est} tokens")

        # WITH-STATE call
        print("calling WITH STATE...", end=" ", flush=True)
        with_state = call_model(client, args.model, state, query)
        print(f"✓ ({with_state['usage']['completion_tokens']} tokens out)")

        # CONTROL call (no system prompt at all)
        print("calling CONTROL (no STATE)...", end=" ", flush=True)
        control = call_model(client, args.model, None, query)
        print(f"✓ ({control['usage']['completion_tokens']} tokens out)")

        # Save artifacts
        probe_dir = out_dir / pid
        probe_dir.mkdir(exist_ok=True)
        (probe_dir / "state.txt").write_text(state)
        (probe_dir / "query.txt").write_text(query)
        (probe_dir / "expectation.txt").write_text(probe["expectation"])
        (probe_dir / "with_state.md").write_text(
            f"# {pid} — WITH STATE\n\n## query\n{query}\n\n## response\n{with_state['content']}\n"
        )
        (probe_dir / "control.md").write_text(
            f"# {pid} — CONTROL (no STATE)\n\n## query\n{query}\n\n## response\n{control['content']}\n"
        )

        # Compact side-by-side
        sbs = (
            f"# {pid}\n\nQUERY: {query}\n\nEXPECTATION: {probe['expectation']}\n\n"
            f"---\n\n## WITH STATE ({with_state['usage']['prompt_tokens']} prompt tok)\n\n"
            f"{with_state['content']}\n\n"
            f"---\n\n## CONTROL ({control['usage']['prompt_tokens']} prompt tok)\n\n"
            f"{control['content']}\n"
        )
        (probe_dir / "side_by_side.md").write_text(sbs)

        summary["probes"].append({
            "id": pid,
            "query": query,
            "state_chars": state_chars,
            "state_tokens_est": state_tokens_est,
            "with_state_tokens": with_state["usage"],
            "control_tokens": control["usage"],
        })
        print()

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(f"done. artifacts in {out_dir}")
    print(f"compare: ls {out_dir}/*/side_by_side.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
