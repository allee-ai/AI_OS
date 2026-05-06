"""File the slow-import worker as a goal."""
from agent.subconscious.loops.goals import propose_goal

goal = """\
Slow-import worker for archived conversations + new imports.

Read prior conversation transcripts and chat exports as a low-priority
background pass. For each turn:
  - score it for "evolutionary weight" (introduced concept, decision,
    contradiction, commitment, named_entity, file_create_in_agent)
  - if score >= threshold, emit a backdated meta_thought via
    add_meta_thought(...) with first_asserted_at = original_ts and
    weight scaled by score.
  - otherwise emit only a low-weight 'compression' summary every N turns.

Goals:
  1. Treat history as a feedstock the substrate digests over time, not
     a one-shot dump.
  2. Same pipeline ingests *new imports* (vscode logs, slack exports,
     email archives) so the "evolution events" function stays valuable
     no matter where data comes from.
  3. Live conversation stays untouched on the recency-weighted path —
     this worker is strictly historical.

Implementation sketch:
  scripts/import_history.py
    --source <dir|file|table>
    --max-per-tick 50
    --score-threshold 0.5
    --dry-run

  Internals:
    - chunk source into turn-shaped units
    - score(turn) -> (weight, kind, sig) using existing
      response_tags + linking_core.extract_concepts heuristics, no LLM
    - if not seen-before-sig and weight >= threshold: emit meta_thought
    - record progress in a new table: import_progress(source, last_id,
      processed, kept, skipped)

Constraint: pure DB + heuristic. No LLM. Adding LLM scoring is a
separate goal."""

gid = propose_goal(
    goal=goal,
    rationale=(
        "User explicit ask: 'treat all previous conversations as history "
        "to be read through slowly, scored, and tracked as prior evolution "
        "events.' The function stays valuable when new imports arrive."
    ),
    priority="medium",
    sources=["live-conversation", "user-explicit"],
)
print(f"goal queued: #{gid}")
