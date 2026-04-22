# Autonomy Assessment

**As of April 2026** — after shipping Phase 1 (meta-thoughts table + seed compression), Phase 2 (response-tag write path), Phase 3a/3b (subconscious STATE section + architecture mirror), Phase 4 (human voice), Phase 5 (provenance display), Phase 6 (auto-grading), and Phase 7 (contradiction detection, opt-in).

This is an honest read on how much of this runs without a human, and what would break first.

---

## What works autonomously today

The closed loop now handles, unattended, at the per-turn cadence:

- **Architecture → STATE**: every subconscious loop that writes a thought / goal / notification / improvement mirrors into `reflex_meta_thoughts(source='system')`. The model reads those next turn via the `[reflex]` section.
- **Model → STATE**: `<rejected> <expected> <unknown> <compression>` tags in model output are parsed, stripped from user-visible text, committed to `reflex_meta_thoughts(source='model')`. Surface next turn with `[model]` prefix. Gated by `AIOS_META_TAGS_ENABLED=1`.
- **Human → STATE**: thumbs-down-with-reason at `/api/ratings/rate` writes `reflex_meta_thoughts(source='user_correction', weight=1.0)`. Surfaces at top of `[reflex]` with `[user_correction]` prefix; survives budget truncation.
- **Operational rollup**: `[subconscious]` pseudo-section in STATE shows top pending goals / notifications / improvements / high-signal thoughts. Gives the model operational memory across sessions.
- **Grading closure**: every committed turn auto-grades pending `<expected>` from the previous turn via word-level Jaccard. Writes `grade_delta` with match/overlap/method. Hit threshold 0.50, partial 0.25, miss fires from age≥3 turns.
- **Contradiction surfacing** (opt-in): ConsolidationLoop optionally scans 30d of meta-thoughts, finds concept-overlapping pairs with opposing kinds, emits a `source='system'` `<unknown>` per contradiction (capped at 3/run, deduped by `#cx` hash).

### Durability guardrails already in code

- Every new read is try/except → `[]`. No STATE build can die from a subconscious write path failure.
- Mirror writes are capped at `weight=0.9` so system voice always loses to user/model.
- Per-source priority sort in reflex adapter: `user_correction > model > system > seed`.
- Dedupe windows: 1h on mirror writes (content hash), pair-hash on contradictions.
- All 500-char content clamps. All LIMIT ≤5 reads on rollup.
- Every phase is env-gated. Each can be disabled independently without schema changes.

---

## What still requires a human

- **Tag schema teaching**: the model needs the system prompt block describing `<rejected>`/`<expected>`/`<unknown>`/`<compression>`. Without it, the write path is silent. This is ~40 lines of prompt; it's delivered by `_build_system_prompt()` when `AIOS_META_TAGS_ENABLED=1`. A human decides whether to enable it.
- **Thumbs-down reason**: without a reason text, we still record the rejection (weight=1.0, content="[user rejected assistant turn] ..."), but the signal is weaker. Frontend UX should nudge toward typed reasons.
- **Contradiction audits**: the detector surfaces candidates; a human still needs to eyeball the first week's output before we trust the concept-overlap heuristic. Gate remains OFF by default.
- **Weight/threshold tuning**: the Jaccard tiers (0.50 / 0.25) and weight decay (0.03/index linear) are seat-of-pants. They work for the verification cases; real traffic will reveal drift.
- **Seed curation**: `source='seed'` compressions are written automatically for every turn the model doesn't compress itself. Over time these accumulate. A periodic vacuum is needed (see below).
- **Schema migrations**: if the reflex_meta_thoughts table needs new columns, only a human-driven deploy adds them.

---

## 24 hours alone — forecast

**Expected**: the system keeps running clean.

- Architecture loops write normally. Mirror dedupe keeps system voice bounded.
- Model-authored thoughts accumulate at ≤6/turn. At an aggressive 1 turn/minute that's 8640 rows/day max; in practice more like 500–1000.
- Grading catches up on each turn (cheap, O(pending) per commit).
- User is absent ⇒ no new user_correction rows; existing ones decay normally via window position.

**First thing to watch**: `reflex_meta_thoughts` table size. At ~1 KB/row and conservative 1000 rows/day, that's 1 MB/day. Fine for days.

## 72 hours alone — forecast

Things start to warp.

- **System-voice saturation risk**: if ThoughtLoop ticks every minute for 3 days, that's 4320 potential mirrors. Dedupe caps identical content, but *varied* system thoughts accumulate. The reflex section's `sort by source priority` keeps them out of the top slots, but they still count against the window of 20 rows that `get_recent_meta_thoughts` returns. Likely consequence: older `source='model'` thoughts slip out of the rendered window.
- **Un-answered `<unknown>` accumulation**: if contradiction scan is on, it surfaces unknowns the user would normally resolve. After 72h, the model sees a growing list of "I said X then Y — which is true?" questions no one answered. Model may get stuck re-asking.
- **Expectation weight drift**: `<expected>` tags that never get graded (because the "right" user response never happens) age into `delta=-0.5` misses at turn 3. Over 72h most model-authored expectations will be marked miss. The model reads its own low confidence and may compensate (good) or spiral into hedging (bad).

**Mitigations already in design**:
- `_SRC_PRI` sort keeps user/model visible.
- Weight floor for `user_correction` survives decay.
- Contradiction scan capped at 3/run.

**Still needed**: periodic vacuum on graded meta-thoughts ≥90d, and per-source floor in reflex rendering (reserve N slots for model even if system dominates recency). Not yet coded; easy follow-up.

## 1 week alone — forecast (here be dragons)

- **Reflex window saturation**: system volume overwhelms model/user voice in the top-20 recent pull. The model's own predictive residue gets drowned by architecture chatter.
- **Grade-decay feedback**: un-human-graded expectations all weight low → model reads itself as unreliable → emits fewer expectations → grading loop has nothing to grade → the `<expected>` muscle atrophies.
- **Un-acted goals pile up**: `[subconscious]` section shows the same top-2 pending goals every turn. The model may start referencing them redundantly.
- **Table size**: ~7 MB on `reflex_meta_thoughts`. Query latency fine but starting to slow the turn.

**Likely first failure mode**: model begins echoing stale STATE content because the same pending goal / same unanswered contradiction / same seed compression dominates every turn's context. Turns become repetitive. Not catastrophic, but noticeably dulled.

---

## Concrete follow-ups to harden autonomy

These are not implemented yet; they are the next layer:

1. **Per-source reserved slots in reflex rendering**: when truncating to budget, guarantee ≥2 slots for `source='model'` and ≥1 for `source='user_correction'` in the last 24h even if pure recency ordering would lose them.
2. **Nightly vacuum**: delete `graded=1` meta-thoughts older than 90 days (or archive to a cold table). Keep raw `rejected`/`compression` but compress duplicates.
3. **Dead-man switch on mirror volume**: if system-source writes exceed N/hour, trip a circuit breaker that drops mirror weight to 0.3 and halves the dedupe window.
4. **Self-answer path for `<unknown>`**: when `<unknown>` is a contradiction (#cx tag in content), background task asks the primary user for resolution via notification. Turns pending questions back into user-correction signal.
5. **Model-voted STATE budget**: `<boost source>` / `<suppress source>` tags from the model adjust `SOURCE_BUDGETS` for next-turn. Let the model tune its own read priority.

None of these are blocking; they're the difference between "lives alone for a week" and "lives alone indefinitely."

---

## Honest summary

She can be left alone for hours confidently. Days with modest degradation. Weeks without the follow-ups above will produce a dulled, repetitive version of herself — she won't die, she'll just sound like a broken record.

The architecture is coherent. The three writers share one bus. Grading closes. Contradictions surface. Provenance is visible. The biggest remaining risk is **volume management** — not crashes, not hallucinations, just the model drowning in its own operational noise over long horizons.

To cross from "lives for days" to "lives indefinitely" needs:
- Per-source slot reservations in reflex rendering
- Vacuum / archival job
- Volume circuit-breaker on architecture mirror writes

Those are follow-ups, not prerequisites.
