# AI_OS Codebase Assessment — 2026-04-22

Generated at turn-start. Snapshot of structure, health, velocity, and risk at commit `dbd61dd`.

---

## 1. Shape at a glance

| Metric | Value |
|---|---|
| Python files | 286 |
| Markdown files | 75 |
| Frontend (tsx/ts/js) | 113 |
| Total Python LOC | 77,668 |
| DB size | 226 MB |
| DB tables | 54 |
| Commits last 7 days | 15 |
| Dirty working tree | 1 untracked (`eval/state_vs_bare_2d19bab7.json`) |
| TODO/FIXME/HACK markers | 1 |

One TODO in 286 files means either impeccable discipline or TODOs aren't being written. Both happen.

---

## 2. Architecture layout (verified present)

### Threads — `agent/threads/`
`form`, `identity`, `linking_core`, `log`, `philosophy`, `reflex`, `vision` — 7 threads, matching the documented self-model.

### Loops — `agent/subconscious/loops/`
16 loops: `consolidation`, `convo_concepts`, `custom`, `demo_audit`, `evolve`, `goals`, `health`, `manager`, `memory`, `self_improve`, `sync`, `task_planner`, `thought`, `training_gen`, `workspace_qa`. Plus `base.py`.

### Tools — `agent/threads/form/tools/executables/`
`cli_command`, `code_edit`, `file_read`, `file_write`, `notify`, `regex_search`, `terminal`, `terminal_vm`, `web_search`, `workspace_read`, `workspace_write` — 11 registered executables.

---

## 3. Largest / riskiest files

| LOC | File | Notes |
|---|---|---|
| 1961 | `eval/evals.py` | Eval harness — grew fast, recently grew progress logging + timeout fix. Candidate for split. |
| 1819 | `finetune/api.py` | Training router. Long; split per concern (behavioral/examples/templates). |
| 1720 | `agent/threads/log/schema.py` | Log schema + CRUD. Expected size for central thread. |
| 1642 | `agent/subconscious/api.py` | Subconscious router. Big — 9 goals/* routes here, could peel off goals subrouter. |
| 1559 | `agent/threads/linking_core/schema.py` | Graph/links. 116k long-potentiated / 653k links — schema carries its weight. |
| 1229 | `Feeds/api.py` | Feeds router. |
| 1096 | `agent/services/agent_service.py` | Service layer. |
| 1078 | `agent/subconscious/orchestrator.py` | STATE builder. Core to ritual — touch with care. |

**Files > 1500 LOC (5)** — soft ceiling worth watching. `eval/evals.py` and `finetune/api.py` are the first refactor candidates.

---

## 4. Recent commits (last 10)

```
dbd61dd  scripts: wake-on-goal-add + persistent caffeinate + sleep_off helper
f626ff3  fix eval hang: ollama.Client(timeout=120) + per-prompt progress
0b5e5a5  add scripts/send_to_vs.py — paste a message into VS Code Copilot Chat
5683593  fix ntfy SSL: use certifi CA bundle + curl fallback
26d67ba  clarify notify-vs-ping boundary
76a4f04  shared alert helper: notify tool + ping both use alerts service
92367df  scripts/vm_sync.sh: push local, pull VM, auto-stash dirty
b444d2a  split terminal into local (mac) + vm (ssh); surface env in form
10fd8ab  ping pipe + goals surfacing: zero-new-infra nudge channel
9f89cac  fast goal entry + goals STATE module
```

**Theme:** wake-channel + autonomy infrastructure. User→agent→phone loop went from nothing to production in ~5 commits. Remote Mac↔VM split was just before that.

---

## 5. Live system state (from ritual STATE this turn)

| Thread | Live count |
|---|---|
| Concepts (linking_core) | 4,760 |
| Links | 653,496 (avg strength 0.30) |
| Long-potentiated links | 116,859 |
| Reflex meta-thoughts | 63 |
| Reflex pending expectations | 5 (0 graded) |
| Open goals | 5 (#7, #8, #9, #10, #11) |

### Open goals
- `#11 high` TEST goal-add chime (can close)
- `#10 medium` self-teaching Q&A loop from commits/docs
- `#9  medium` run state-vs-bare eval — **achieved** this turn (n=7, 5/7, win_rate=0.71)
- `#8  high` enable VS Code Remote on AIOS VM
- `#7  high` SMS bridge — **redundant** with working ntfy; candidate for dismissal

### Reflex grading is stuck
`63 meta-thoughts, 0/5 expectations graded`. The reflex grader isn't closing loops — expectations accumulate with no outcome labels. Without grading, the reflex thread can't actually learn. **This is the quietest failure mode in the tree right now.**

---

## 6. What's working

- **Wake channel end-to-end.** mac chime + urgent say + phone ntfy, CA bundle + curl fallback, VS Code terminal-completion autowake all verified this window.
- **Eval harness.** Runner caught a real regression (ollama default timeout=None) and survived 22min of sock_recv hangs without corrupting results. Now bounded.
- **STATE ritual discipline.** `turn_start.py` prints stale-marker age; drift is detectable. Used it to catch a 30-min gap earlier today.
- **Goal capture latency.** `.venv/bin/python scripts/goal.py "text"` → stored + chimed + phone push in < 1s. This is the flywheel.
- **Threads boundary.** No thread imports another; confirmed via grep. The architecture discipline is real.

---

## 7. What's rotting

1. **Reflex grading pipeline** — 0/5 expectations graded. Biggest pure-debt item. If not fixed, reflex becomes write-only.
2. **Training JSONL stale** — newest JSONL is Apr 15 (7 days old), 8,887 pairs, `training_templates` table at 0 rows. The feedback loop from live events → new training data isn't running on schedule.
3. **AIOS VM can't run models** — 961 MiB RAM, forces Ollama cloud only. Goal #8 (Remote-SSH) solves the dev-ergonomics side; doesn't solve the inference side. Consider a desktop GPU + cloud PII filter.
4. **`com.aios.server` not listening** — launchctl shows the label loaded but `curl localhost:8000/api/health` returns 404 through a different server; frontend ports 5173/3000 both dead. Dashboard is unreachable locally right now. Worth reconciling.
5. **Two large routers** (`finetune/api.py` 1819, `agent/subconscious/api.py` 1642) accumulating. Both started small; both cross 1500 now. Not urgent, but one more feature in each and they cross 2000.
6. **`_archive/` is large and unindexed.** Historical decisions are buried there. No tombstones in main docs pointing to the archive reasons.

---

## 8. Autonomy / wake loop — post-mortem

Charger-unplug broke the 15-min status timer earlier: mac slept because `caffeinate -t 43200` handles idle/display/disk/system sleep but **not clamshell sleep on battery**. Fix shipped this turn:
- `scripts/sleep_off.sh on` installs a LaunchAgent (`com.aios.caffeinate.plist`, KeepAlive) + runs `sudo pmset -a disablesleep 1` — the only setting that truly ignores lid-close on battery.
- Goal-add now fires `fire_alerts()` so closed-lid mac chimes and phone buzzes on every new goal.

**Remaining gap:** if wifi drops during a closed-lid window, ntfy posts get eaten silently. `_fire_phone` should add retry-with-backoff to a local queue that flushes on network-up. Not yet written.

---

## 9. Eval snapshot — `state_impact` (n=7, qwen2.5:7b)

| Metric | Value |
|---|---|
| Passed | 5 / 7 |
| State win-rate (vs bare) | 0.71 |
| Personalization rate | 0.57 |
| Mean state latency | ~50s |
| Mean bare latency | ~13s |
| Status | passed |

State adds ~35s/turn in exchange for 71% win-rate and 57% personalization. That's a real signal; state isn't cosmetic. Latency is the cost to justify.

---

## 10. Priority shortlist (recommendation)

1. **Fix reflex grading loop** — unblock the learning feedback path.
2. **Restart training regen cron** — stale JSONL starves finetuning.
3. **Offline queue for `_fire_phone`** — close the wifi-drop hole.
4. **Split `eval/evals.py` and `finetune/api.py`** — stop the 2000-LOC drift.
5. **Close goal #7 (SMS)** — ntfy covers it.
6. **Close/graduate goal #11** — it was a test ping.

---

_Report path: `docs/assessments/ASSESSMENT_2026-04-22.md`_
_Generated by assessing commit `dbd61dd` on main._
