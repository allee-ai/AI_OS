"""
Subconscious Orchestrator
=========================

The orchestrator that builds STATE from all threads.

Core equation: state_t+1 = f(state_t, assess)

Two-step flow in subconscious:
    1. score(query) → thread scores
    2. build_state(scores, query) → STATE block

Then agent.generate(STATE, query) IS the assess step.
The LLM receives state + assess block and produces output.

Usage:
    from agent.subconscious.orchestrator import get_subconscious
    
    sub = get_subconscious()
    scores = sub.score("who are you")
    state = sub.build_state(scores, "who are you")
    # Then: agent.generate(user_input, state) - this IS assess

Architecture:
    - score() uses LinkingCore to score all threads for relevance
    - build_state() orders threads by score, calls introspect with threshold
    - agent.generate() IS assess - LLM evaluates query against state
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import json
import re

# Path where the previous turn's fact_keys are cached so the next turn's
# score() can apply a Hebbian recency boost to the threads/modules that
# fired last time. File-based so it survives process restarts.
_LAST_KEYS_PATH = Path("data/.last_turn_keys.json")
# Boost added to a thread/module score when at least one of its fact_keys
# lit up in the previous turn. Capped at SCORE_MAX in apply.
_RECENCY_BOOST = 0.6


# Thread list - linking_core included for UI visibility
THREADS = ["identity", "log", "form", "philosophy", "reflex", "linking_core", "field"]

# Top-level modules — scored for relevance alongside threads.
# Each module provides summarised context (conversations, files, etc.)
# and goes through the same score → level → threshold pipeline.
MODULES = ["chat", "workspace", "docs", "goals", "sensory"]

# Score thresholds for context levels
# Score determines: (1) block order, (2) L1/L2/L3 level, (3) fact weight threshold
SCORE_THRESHOLDS = {
    "L1": 3.5,   # 0 - 3.5: L1 (lean), only high-weight facts
    "L2": 7.0,   # 3.5 - 7: L2 (medium)
    "L3": 10.0,  # 7 - 10: L3 (full)
}

# ---------------------------------------------------------------------------
# Co-activation extraction (used by build_state to feed key_cooccurrence)
# ---------------------------------------------------------------------------

# Matches a leading namespaced fact key like:
#   identity.primary_user.name: ...
#   goals.open.#32 [H]: ...
#   docs.agent/threads/linking_core/IMPLEMENTATION.md: ...
# Skips:
#   "  - rule lines"
#   "  context_level: 3"   (no dot in token)
#   "[identity] header"
_FACT_KEY_RE = re.compile(r"^\s*([a-z_][a-z_]*\.[A-Za-z0-9_./#\-]+)(?=[\s:\[]|$)")

# Cap how many keys we record co-activations for in a single turn.
# 80 keys → ~3160 pairs, well within a fast single-transaction batch.
_MAX_COACTIVATION_KEYS = 80


def _extract_fact_keys(lines: List[str]) -> List[str]:
    """Pull namespaced fact keys from STATE lines, in order, deduped."""
    seen = set()
    keys: List[str] = []
    for line in lines:
        m = _FACT_KEY_RE.match(line)
        if not m:
            continue
        k = m.group(1)
        if k in seen:
            continue
        seen.add(k)
        keys.append(k)
        if len(keys) >= _MAX_COACTIVATION_KEYS:
            break
    return keys


def _save_last_keys(keys: List[str]) -> None:
    """Persist this turn's fact_keys for next turn's recency boost."""
    try:
        _LAST_KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_KEYS_PATH.write_text(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "keys": keys,
        }))
    except Exception:
        pass


def _load_last_keys() -> List[str]:
    """Load previous turn's fact_keys. Returns [] on any error."""
    try:
        if not _LAST_KEYS_PATH.exists():
            return []
        data = json.loads(_LAST_KEYS_PATH.read_text())
        keys = data.get("keys") or []
        if isinstance(keys, list):
            return [k for k in keys if isinstance(k, str)]
    except Exception:
        pass
    return []


def _namespaces_from_keys(keys: List[str]) -> set:
    """'identity.primary_user.name' -> 'identity'. Returns set of namespaces."""
    out = set()
    for k in keys:
        if "." in k:
            ns = k.split(".", 1)[0]
            out.add(ns)
    return out

# Context-window aware budget allocation.
# Total STATE budget = STATE_FRACTION of the target context window.
# Each source gets a share proportional to its relevance score.
# Higher score → more tokens to express itself.
import os as _os
CONTEXT_WINDOW = int(_os.getenv("AIOS_CONTEXT_WINDOW", "4096"))
STATE_FRACTION = float(_os.getenv("AIOS_STATE_FRACTION", "0.25"))

# Minimum tokens any included source gets (prevents zero-budget sources)
MIN_SOURCE_BUDGET = 40
# Maximum share any single source can claim (prevents domination)
MAX_SOURCE_SHARE = 0.30


def allocate_budgets(scores: Dict[str, float],
                     context_window: int = 0,
                     state_fraction: float = 0.0) -> Dict[str, int]:
    """Allocate per-source token budgets proportional to relevance scores.

    Sources with score 0 get nothing.  The rest split the total STATE
    budget in proportion to their scores, clamped by MIN/MAX.

    Returns dict mapping source_name → token budget.
    """
    cw = context_window or CONTEXT_WINDOW
    sf = state_fraction or STATE_FRACTION
    total = int(cw * sf)

    # Only sources with positive scores participate
    active = {k: v for k, v in scores.items() if v > 0}
    if not active:
        return {k: MIN_SOURCE_BUDGET for k in scores}

    score_sum = sum(active.values())
    budgets: Dict[str, int] = {}

    for source, score in active.items():
        share = score / score_sum
        # Clamp share so no single source dominates
        share = min(share, MAX_SOURCE_SHARE)
        budgets[source] = max(MIN_SOURCE_BUDGET, int(total * share))

    # Sources that scored 0 get nothing
    for source in scores:
        if source not in budgets:
            budgets[source] = 0

    return budgets


def _fmt_size(n: int) -> str:
    """Format byte size to human-readable."""
    if n < 1024:
        return f"{n}B"
    elif n < 1024 * 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n / (1024 * 1024):.1f}MB"


class Subconscious:
    """
    The orchestrator that builds STATE from all threads.
    
    Core equation: state_t+1 = f(state_t, assess)
    
    Key insight: 
    - STATE is assembled from threads, ordered by relevance
    - Each thread filters its facts by the score threshold
    - Facts use dot notation for addressability
    - The same STATE structure works for conversation, consolidation, reading, etc.
    """
    
    def __init__(self):
        self._last_context_time: Optional[str] = None
        self._last_query: Optional[str] = None
        self._linking_core = None
    
    def _get_adapter(self, thread_name: str):
        """Get a thread adapter from the central registry."""
        try:
            from agent.threads import get_thread
            return get_thread(thread_name)
        except Exception as e:
            print(f"⚠️ Failed to load {thread_name} adapter: {e}")
            return None
    
    def _get_linking_core(self):
        """Get the LinkingCore adapter for scoring."""
        if self._linking_core is None:
            self._linking_core = self._get_adapter("linking_core")
        return self._linking_core
    
    def score(self, query: str = "") -> Dict[str, float]:
        """
        Score all threads AND modules for relevance to query.
        
        Step 1 of the flow: score(query) → scores
        
        Args:
            query: The input to score against (user message, file chunk, etc.)
        
        Returns:
            Dict mapping source_name → relevance_score (0-10)
            Includes both threads (identity, log, ...) and modules (chat, workspace)
        """
        from agent.subconscious import trace_bus  # local import to avoid cycles
        trace_bus.publish("score_start", query=query[:200] if query else "")
        linking_core = self._get_linking_core()
        if linking_core and query:
            scores = linking_core.score_threads(query)
        else:
            # Default scores if linking_core unavailable or no query
            scores = {t: 5.0 for t in THREADS}
        
        # Ensure all threads have a score (default 5.0)
        for thread in THREADS:
            if thread not in scores:
                scores[thread] = 5.0
        
        # Score modules via keyword heuristics
        if query:
            scores.update(self._score_modules(query))
        else:
            for mod in MODULES:
                scores[mod] = 4.0

        # Hebbian recency: boost threads/modules whose fact_keys lit up
        # in the previous turn. Closes the loop between record_cooccurrence
        # (write side, in build_state) and score-time bias (read side).
        try:
            last_keys = _load_last_keys()
            if last_keys:
                hot_namespaces = _namespaces_from_keys(last_keys)
                boosted = []
                for ns in hot_namespaces:
                    if ns in scores:
                        before = scores[ns]
                        scores[ns] = min(10.0, before + _RECENCY_BOOST)
                        if scores[ns] != before:
                            boosted.append(ns)
                if boosted:
                    trace_bus.publish(
                        "recency_boost",
                        boosted=boosted,
                        boost=_RECENCY_BOOST,
                    )
        except Exception as e:
            trace_bus.publish("recency_boost_error", error=str(e)[:200])

        trace_bus.publish("score_done", scores={k: round(v, 2) for k, v in scores.items()})
        return scores
    
    def _score_modules(self, query: str) -> Dict[str, float]:
        """Score top-level modules for relevance to query."""
        q = query.lower()
        scores: Dict[str, float] = {}
        
        # Chat — past conversations
        if any(kw in q for kw in [
            'conversation', 'talked', 'discussed', 'said', 'chat',
            'last time', 'previously', 'remember when', 'we spoke',
            'our last', 'earlier', 'before',
        ]):
            scores["chat"] = 8.5
        elif any(kw in q for kw in ['history', 'past', 'recall']):
            scores["chat"] = 7.0
        else:
            scores["chat"] = 4.0
        
        # Workspace — files and documents
        if any(kw in q for kw in [
            'file', 'workspace', 'code', 'project', 'read',
            'document', 'folder', 'directory', 'source',
        ]):
            scores["workspace"] = 8.5
        elif any(kw in q for kw in [
            'work on', 'working', 'build', 'implement', 'edit',
            'write', 'create', 'status', 'progress',
        ]):
            scores["workspace"] = 7.0
        else:
            scores["workspace"] = 3.0

        # Sensory — recent perceptual events (mic, vision, ambient)
        if any(kw in q for kw in [
            'heard', 'saw', 'see', 'hear', 'said', 'spoke', 'voice',
            'mic', 'microphone', 'camera', 'screen', 'ambient',
            'just now', 'right now', 'just happened',
        ]):
            scores["sensory"] = 8.5
        elif any(kw in q for kw in ['notice', 'perceive', 'observed', 'observation']):
            scores["sensory"] = 6.5
        else:
            scores["sensory"] = 3.5

        # Docs — READMEs, architecture, roadmap, changelog, docs/ tree
        if any(kw in q for kw in [
            'docs', 'documentation', 'readme', 'architecture',
            'roadmap', 'changelog', 'spec', 'reference',
        ]):
            scores["docs"] = 8.5
        elif any(kw in q for kw in [
            'explain', 'describe', 'how does', 'what is', 'overview',
        ]):
            scores["docs"] = 6.0
        else:
            scores["docs"] = 3.5

        # Goals — always relatively hot; user-logged priorities should almost always
        # appear in STATE so the agent doesn't lose track of what we agreed to build.
        if any(kw in q for kw in [
            'goal', 'priority', 'todo', 'objective', 'plan',
            'working on', 'next', 'compete', 'compound',
        ]):
            scores["goals"] = 9.0
        else:
            scores["goals"] = 6.0

        return scores
    
    def build_state(self, scores: Dict[str, float], query: str = "", record_activations: bool = True) -> str:
        """
        Build STATE block from scored threads AND modules.
        
        Step 2 of the flow: build_state(scores) → STATE
        
        All sources (threads like identity/log/form AND modules like
        chat/workspace) are sorted by relevance score together.  Each
        source goes through the same score → level → threshold pipeline
        and gets a token budget proportional to its relevance score.
        
        Args:
            scores: Source relevance scores from score()
            query: Optional query for filtering
            record_activations: When True (default), record namespaced fact
                keys that co-appeared in this STATE into key_cooccurrence.
                Pass False for previews / hypothetical builds (dashboard,
                debugging) so they don't pollute Hebbian counts.
        
        Returns:
            Formatted STATE block string
        """
        from agent.subconscious import trace_bus
        import time as _t
        _build_start = _t.perf_counter()
        trace_bus.publish(
            "build_state_start",
            query=query[:200] if query else "",
            source_count=len(scores),
        )
        # Order ALL sources (threads + modules) by score, highest first
        ordered_sources: List[Tuple[str, float]] = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Allocate token budgets proportional to scores
        budgets = allocate_budgets(scores)
        trace_bus.publish(
            "budgets",
            budgets={k: int(v) for k, v in budgets.items()},
        )
        
        lines = ["== STATE =="]
        
        # Self-awareness header — injected once at top
        lines.extend(self._build_self_awareness_block())
        
        for source_name, score in ordered_sources:
            # Determine level from score
            if score < SCORE_THRESHOLDS["L1"]:
                level = 1
            elif score < SCORE_THRESHOLDS["L2"]:
                level = 2
            else:
                level = 3
            
            # Threshold is INVERTED: high score → low weight threshold
            threshold = max(0.0, 10.0 - score)
            
            source_budget = budgets.get(source_name, MIN_SOURCE_BUDGET)
            if source_budget <= 0:
                continue

            if source_name in THREADS:
                # ---------- Thread source ----------
                section = self._build_thread_section(
                    source_name, level, threshold, query, source_budget
                )
            elif source_name in MODULES:
                # ---------- Module source ----------
                section = self._build_module_section(
                    source_name, level, threshold, query, source_budget
                )
            else:
                continue
            
            if section:
                lines.append("")
                lines.extend(section)
        
        # Subconscious operational rollup (Phase 3a).
        # Gated internally; returns '' when disabled or empty.
        try:
            from agent.subconscious.state_rollup import build_subconscious_section
            sub_block = build_subconscious_section(budget=400)
            if sub_block:
                lines.append("")
                lines.append(sub_block)
        except Exception:
            pass

        lines.append("")
        lines.append("== END STATE ==")

        # Hebbian co-activation: every fact_key that lit up in this STATE is a
        # co-activation event. Pair them up and increment counts in
        # key_cooccurrence so the relevance scorer learns from real STATE
        # assembly, not from a separate text-extraction pipeline.
        if record_activations:
            try:
                fact_keys = _extract_fact_keys(lines)
                if len(fact_keys) >= 2:
                    pairs = [
                        (fact_keys[i], fact_keys[j])
                        for i in range(len(fact_keys))
                        for j in range(i + 1, len(fact_keys))
                    ]
                    from agent.threads.linking_core import record_cooccurrence_batch
                    n_recorded = record_cooccurrence_batch(pairs)
                    trace_bus.publish(
                        "cooccurrence_recorded",
                        keys=len(fact_keys),
                        pairs=n_recorded,
                    )
                # Persist for next turn's recency boost regardless of pair count.
                if fact_keys:
                    _save_last_keys(fact_keys)
            except Exception as e:
                # Never let co-activation recording break STATE assembly
                trace_bus.publish("cooccurrence_error", error=str(e)[:200])

        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        trace_bus.publish(
            "build_state_done",
            duration_ms=int((_t.perf_counter() - _build_start) * 1000),
            chars=sum(len(s) for s in lines),
            line_count=len(lines),
        )
        return "\n".join(lines)
    
    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    
    def _build_thread_section(
        self, thread_name: str, level: int, threshold: float, query: str,
        budget: int = 200,
    ) -> List[str]:
        """Build a STATE section for a scored thread via its adapter."""
        from agent.subconscious import trace_bus
        import time as _t
        adapter = self._get_adapter(thread_name)
        if not adapter:
            trace_bus.publish("adapter_missing", source=thread_name, kind="thread")
            return []
        
        # Apply score-allocated budget to adapter's token budgets
        if hasattr(adapter, '_token_budgets'):
            adapter._token_budgets = {
                1: budget,
                2: budget,
                3: budget,
            }
        
        _t0 = _t.perf_counter()
        trace_bus.publish(
            "adapter_call",
            source=thread_name,
            kind="thread",
            level=level,
            threshold=round(threshold, 2),
            budget=budget,
        )
        try:
            result = adapter.introspect(
                context_level=level, query=query, threshold=threshold
            )
            result_dict = result.to_dict()
            facts = result_dict.get("facts", [])
        except TypeError as te:
            # Adapter doesn't support threshold yet — signature mismatch
            try:
                from agent.threads.log.schema import log_event
                log_event(
                    event_type="warn:signature_mismatch",
                    data=f"{thread_name} adapter missing 'threshold' param",
                    metadata={"thread": thread_name, "error": str(te)},
                    source="orchestrator",
                )
            except Exception:
                pass
            try:
                result = adapter.introspect(context_level=level, query=query)
                result_dict = result.to_dict()
                facts = result_dict.get("facts", [])
            except Exception as e:
                trace_bus.publish("adapter_error", source=thread_name, kind="thread", error=str(e)[:200])
                print(f"⚠️ {thread_name} introspect failed: {e}")
                return []
        except Exception as e:
            trace_bus.publish("adapter_error", source=thread_name, kind="thread", error=str(e)[:200])
            print(f"⚠️ {thread_name} introspect failed: {e}")
            return []
        
        trace_bus.publish(
            "adapter_result",
            source=thread_name,
            kind="thread",
            fact_count=len(facts),
            duration_ms=int((_t.perf_counter() - _t0) * 1000),
        )
        if not facts:
            return []
        
        description = getattr(adapter, '_description', '')
        section = [
            f"[{thread_name}] {description}",
        ]
        # Permanent program-state metadata
        try:
            meta_lines = adapter.get_section_metadata()
            if meta_lines:
                section.extend(meta_lines)
        except Exception:
            pass
        section.append(f"  context_level: {level}")
        section.append(f"  fact_count: {len(facts)}")
        # Behavioral rules for this section
        try:
            rules = adapter.get_section_rules()
            if rules:
                section.extend(rules)
        except Exception:
            pass
        section.extend(facts)
        return section
    
    def _build_module_section(
        self, module_name: str, level: int, threshold: float, query: str,
        budget: int = 200,
    ) -> List[str]:
        """Build a STATE section for a scored module (chat, workspace, …)."""
        providers = {
            "chat": self._get_chat_context,
            "workspace": self._get_workspace_context,
            "docs": self._get_docs_context,
            "goals": self._get_goals_context,
            "sensory": self._get_sensory_context,
        }
        provider = providers.get(module_name)
        if not provider:
            return []
        
        facts = provider(query=query, level=level, threshold=threshold)
        if not facts:
            return []
        
        # Enforce score-allocated token budget
        budget_facts: List[str] = []
        tokens = 0
        for f in facts:
            t = len(f.split())
            if tokens + t > budget:
                break
            budget_facts.append(f)
            tokens += t
        
        if not budget_facts:
            return []
        
        descriptions = {
            "chat": "Past conversations and discussion history",
            "workspace": "Files and documents I have access to",
            "sensory": "Recent sensory events (mic, vision, ambient) converted to text",
        }
        section = [
            f"[{module_name}] {descriptions.get(module_name, '')}",
        ]
        # Permanent program-state metadata for modules
        try:
            meta_lines = self._get_module_metadata(module_name)
            if meta_lines:
                section.extend(meta_lines)
        except Exception:
            pass
        section.append(f"  context_level: {level}")
        section.append(f"  fact_count: {len(budget_facts)}")
        # Behavioral rules for modules
        module_rules = {
            "chat": [
                "  rules:",
                "  - Conversation history shown is a summary. Do not fabricate details from past chats.",
                "  - If the user asks about a past conversation not shown, say you'd need to search.",
            ],
            "workspace": [
                "  rules:",
                "  - Only reference files listed here. Do not assume other files exist.",
                "  - To find other files, use file search tools.",
            ],
            "docs": [
                "  rules:",
                "  - Module READMEs are the source of truth; root docs are generated via scripts/sync_docs.py.",
                "  - Before claiming docs say X, verify by reading the listed file.",
            ],
            "goals": [
                "  rules:",
                "  - These are user-logged or loop-proposed goals. Treat them as live priorities.",
                "  - If you complete a goal, resolve it: .venv/bin/python scripts/goal.py --done <id>.",
            ],
            "sensory": [
                "  rules:",
                "  - Sensory events are observations already converted to text (mic transcripts, vision captions, ambient clips).",
                "  - These are observations, NOT user statements. Do not treat as direct user speech unless source=user_voice.",
                "  - Low-confidence events may be inaccurate; weight by the confidence field when it's given.",
            ],
        }
        rules = module_rules.get(module_name, [])
        if rules:
            section.extend(rules)
        section.extend(budget_facts)
        return section
    
    def _get_module_metadata(self, module_name: str) -> List[str]:
        """Return permanent metadata lines for a module (chat, workspace)."""
        try:
            from data.db import get_connection
            conn = get_connection(readonly=True)
        except Exception:
            return []

        if module_name == "chat":
            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt, SUM(turn_count) as turns, "
                    "COUNT(CASE WHEN summary IS NOT NULL AND summary != '' THEN 1 END) as summaries "
                    "FROM convos"
                ).fetchone()
                cnt = row["cnt"] if row else 0
                turns = row["turns"] if row and row["turns"] else 0
                summaries = row["summaries"] if row else 0
                last_row = conn.execute(
                    "SELECT session_id FROM convos ORDER BY last_updated DESC LIMIT 1"
                ).fetchone()
                last_session = last_row["session_id"] if last_row else "none"
                return [
                    f"  conversations: {cnt}",
                    f"  total_turns: {turns}",
                    f"  summaries: {summaries}",
                    f"  last_session: {last_session}",
                ]
            except Exception:
                return []

        elif module_name == "workspace":
            try:
                from workspace.schema import get_workspace_stats
                stats = get_workspace_stats()
                return [
                    f"  files: {stats.get('files', 0)}",
                    f"  indexed: {stats.get('indexed_files', 0)}",
                ]
            except Exception:
                return []

        elif module_name == "docs":
            try:
                import os as _os
                from pathlib import Path as _Path
                root = _Path(__file__).resolve().parents[2]
                total = 0
                module_readmes = 0
                last_mtime = 0
                last_path = ""
                for dp, dns, fns in _os.walk(root):
                    # Prune noisy dirs
                    dns[:] = [d for d in dns if d not in ("_archive", "__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build", ".next")]
                    for fn in fns:
                        if fn.lower().endswith(".md"):
                            total += 1
                            if fn == "README.md":
                                module_readmes += 1
                            fp = _os.path.join(dp, fn)
                            try:
                                mt = _os.path.getmtime(fp)
                                if mt > last_mtime:
                                    last_mtime = mt
                                    last_path = _os.path.relpath(fp, root)
                            except Exception:
                                pass
                # Sync freshness: root docs mtime vs newest module README mtime
                from datetime import datetime as _dt
                age_s = int((_dt.now().timestamp() - last_mtime)) if last_mtime else -1
                lines = [
                    f"  markdown_files: {total}",
                    f"  module_readmes: {module_readmes}",
                ]
                if last_path:
                    lines.append(f"  last_edit: {last_path} ({age_s//60}m ago)" if age_s >= 0 else f"  last_edit: {last_path}")
                return lines
            except Exception:
                return []

        return []

    def _build_self_awareness_block(self) -> List[str]:
        """Build the self-awareness metadata for the top of STATE.
        
        Gives the agent awareness of its own architecture — what threads
        exist, what they store, and the current state of its concept graph.
        """
        lines = [
            "",
            "[self] My internal structure",
            "  | Thread | Question | What I Store |",
            "  |--------|----------|--------------|",
            "  | identity | WHO | My self-model, my user, our relationship |",
            "  | form | WHAT | My tools, my actions, my capabilities |",
            "  | philosophy | WHY | My values, my ethics, my reasoning style |",
            "  | reflex | HOW | My learned patterns, my shortcuts, my recent meta-thoughts |",
            "  | log | WHEN/WHERE | My event timeline, my session history |",
            "  | linking_core | WHICH | My concept graph, my relevance scoring |",
            "  | Module | | |",
            "  | chat | RECALL | Past conversations, discussion history |",
            "  | workspace | CONTEXT | Files, documents, project state |",
            "  | docs | REFERENCE | Module READMEs + root architecture/roadmap/changelog |",
            "  | goals | PRIORITY | Open + recently resolved goals (user + loop proposed) |",
        ]
        
        # Graph stats (cheap read from DB)
        try:
            from data.db import get_connection
            conn = get_connection(readonly=True)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM concept_links")
            link_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(DISTINCT concept_a) + COUNT(DISTINCT concept_b) FROM concept_links")
            concept_count = cur.fetchone()[0] // 2 or 0
            cur.execute("SELECT AVG(strength) FROM concept_links")
            avg_strength = cur.fetchone()[0] or 0
            lines.append(f"  graph: {link_count} links, ~{concept_count} concepts, avg_strength={avg_strength:.2f}")
        except Exception:
            pass
        
        return lines

    def _get_workspace_context(
        self, query: str = "", level: int = 1, threshold: float = 5.0,
        max_results: int = 5,
    ) -> List[str]:
        """Build workspace context — scored through the same pipeline as threads.
        
        level/threshold control how much detail is returned:
        - L1 (lean): file list with sizes
        - L2 (medium): + summaries
        - L3 (full): + FTS snippets, concept re-ranking
        """
        try:
            from workspace.schema import (
                get_workspace_stats, get_all_files_metadata,
                search_files, search_file_content,
            )
            
            stats = get_workspace_stats()
            if stats.get("files", 0) == 0:
                return []
            
            # Determine level by checking FTS hits
            fts_results = []
            if query and stats.get("indexed_files", 0) > 0:
                try:
                    fts_results = search_files(query, limit=max_results)
                except Exception:
                    fts_results = []
            
            facts = []

            # Re-rank FTS results by concept overlap with query
            if fts_results and query:
                try:
                    from agent.threads.linking_core.schema import (
                        extract_concepts_from_text, spread_activate,
                    )
                    query_concepts = extract_concepts_from_text(query)
                    if query_concepts:
                        activated = spread_activate(
                            query_concepts, activation_threshold=0.1,
                            max_hops=1, limit=30,
                        )
                        activated_set = {a["concept"] for a in activated}
                        activated_set.update(query_concepts)

                        def _concept_boost(result: dict) -> float:
                            text = (result.get("path", "") + " " + result.get("snippet", "")).lower()
                            hits = sum(1 for c in activated_set if c in text)
                            return hits

                        fts_results.sort(key=_concept_boost, reverse=True)
                except Exception:
                    pass  # Fallback to default FTS order

            if fts_results:
                # L3 — we have direct query matches: summaries + snippets
                for r in fts_results:
                    path = r.get("path", "")
                    dot_path = path.lstrip("/").replace("/", ".")
                    size = r.get("size", 0)
                    snippet = r.get("snippet") or ""
                    if isinstance(snippet, str):
                        snippet = snippet.replace("<mark>", "").replace("</mark>", "")
                    else:
                        snippet = str(snippet)
                    
                    facts.append(f"  workspace.{dot_path}: {_fmt_size(size)}")
                    
                    # Add summary if available
                    try:
                        from workspace.schema import get_file_summary
                        summary = get_file_summary(path)
                        if summary:
                            facts.append(f"  workspace.{dot_path}.summary: {summary[:150]}")
                    except Exception:
                        pass
                    
                    if snippet:
                        facts.append(f"  workspace.{dot_path}.match: {snippet[:200]}")
            else:
                # L1 — no query hits, just metadata for recent files
                all_files = get_all_files_metadata(limit=8)
                for f in all_files:
                    path = f.get("path", "")
                    dot_path = path.lstrip("/").replace("/", ".")
                    size = f.get("size", 0)
                    summary = f.get("summary")
                    if summary:
                        # L2 — has summary
                        facts.append(f"  workspace.{dot_path}: {_fmt_size(size)} — {summary[:100]}")
                    else:
                        facts.append(f"  workspace.{dot_path}: {_fmt_size(size)}")
            
            return facts
        except Exception:
            return []

    def _get_chat_context(
        self, query: str = "", level: int = 1, threshold: float = 5.0,
        max_results: int = 8,
    ) -> List[str]:
        """Build chat/conversation context for STATE.
        
        Surfaces past conversation summaries so the agent has memory
        of what was discussed.  Higher levels include search matches.
        
        level/threshold control detail:
        - L1: recent convo names + turn counts
        - L2: + summaries
        - L3: + search-matched message snippets
        """
        try:
            from chat.schema import (
                list_conversations, search_conversations,
            )
            
            min_weight = threshold / 10.0
            facts: List[str] = []
            
            # If query present AND level >= 2, search for relevant convos
            search_results = []
            if query and level >= 2:
                try:
                    search_results = search_conversations(query, limit=max_results)
                except Exception:
                    search_results = []
            
            if search_results:
                for r in search_results:
                    sid = r.get("session_id", "")[:12]
                    name = r.get("name") or sid
                    turns = r.get("turn_count", 0)
                    summary = r.get("summary") or ""
                    weight = r.get("weight", 0.5)
                    if weight < min_weight:
                        continue
                    
                    facts.append(f"  chat.{sid}: \"{name}\" ({turns} turns, w={weight:.1f})")
                    if summary and level >= 2:
                        facts.append(f"  chat.{sid}.summary: {summary[:150]}")
                    
                    # L3: include matched preview
                    preview = r.get("preview", "")
                    if preview and level >= 3:
                        facts.append(f"  chat.{sid}.match: {preview[:200]}")
            else:
                # No search hits — show recent conversations
                convos = list_conversations(
                    limit=max_results,
                    min_weight=min_weight if min_weight > 0.1 else None,
                )
                for c in convos:
                    sid = c.get("session_id", "")[:12]
                    name = c.get("name") or sid
                    turns = c.get("turn_count", 0)
                    weight = c.get("weight", 0.5)
                    facts.append(f"  chat.{sid}: \"{name}\" ({turns} turns, w={weight:.1f})")
            
            return facts
        except Exception:
            return []

    def _get_docs_context(
        self, query: str = "", level: int = 1, threshold: float = 5.0,
        max_results: int = 8,
    ) -> List[str]:
        """Build docs context for STATE.

        L1: recent doc edits (name + age).
        L2: + query-matched docs (filename or headings).
        L3: + first-heading preview.
        """
        try:
            import os as _os
            from pathlib import Path as _Path
            from datetime import datetime as _dt

            root = _Path(__file__).resolve().parents[2]
            md_files: List[tuple] = []  # (rel_path, mtime, size)
            for dp, dns, fns in _os.walk(root):
                dns[:] = [d for d in dns if d not in ("_archive", "__pycache__", ".git", "node_modules", ".venv", "venv", "dist", "build", ".next")]
                for fn in fns:
                    if fn.lower().endswith(".md"):
                        fp = _os.path.join(dp, fn)
                        try:
                            st = _os.stat(fp)
                            md_files.append((_os.path.relpath(fp, root), st.st_mtime, st.st_size))
                        except Exception:
                            pass

            if not md_files:
                return []

            facts: List[str] = []
            now_ts = _dt.now().timestamp()

            q_terms = [t.lower() for t in (query or "").split() if len(t) > 2]

            # Score each doc: recency + query-name hit
            def _score(item):
                rel, mt, _sz = item
                recency = max(0.0, 1.0 - (now_ts - mt) / (60 * 60 * 24 * 30))  # 30-day half-window
                hit = 0.0
                low = rel.lower()
                for t in q_terms:
                    if t in low:
                        hit += 1.0
                return recency + hit * 2.0 if q_terms else recency

            md_files.sort(key=_score, reverse=True)

            for rel, mt, sz in md_files[:max_results]:
                age_min = int((now_ts - mt) // 60)
                age_s = f"{age_min}m" if age_min < 90 else f"{age_min // 60}h" if age_min < 60 * 48 else f"{age_min // (60 * 24)}d"
                facts.append(f"  docs.{rel}: {sz}B ({age_s} ago)")
                if level >= 3:
                    try:
                        with open(root / rel, "r", encoding="utf-8", errors="ignore") as fh:
                            head = fh.read(400).strip().splitlines()
                            first = next((ln.strip("# ").strip() for ln in head if ln.strip().startswith("#")), "")
                            if first:
                                facts.append(f"  docs.{rel}.title: {first[:120]}")
                    except Exception:
                        pass

            return facts
        except Exception:
            return []

    def _get_goals_context(
        self, query: str = "", level: int = 1, threshold: float = 5.0,
        max_results: int = 10,
    ) -> List[str]:
        """Surface open + recently resolved goals so the agent sees priorities.

        L1: open goals only.
        L2: + last 3 resolved.
        L3: + rationales.
        """
        try:
            from agent.subconscious.loops.goals import get_proposed_goals
            open_goals = get_proposed_goals(status="pending", limit=max_results)
            facts: List[str] = []
            for g in open_goals:
                gid = g.get("id")
                pri = (g.get("priority") or "medium")[:1].upper()
                gt = (g.get("goal") or "").strip().replace("\n", " ")[:140]
                facts.append(f"  goals.open.#{gid} [{pri}]: {gt}")
                if level >= 3:
                    rat = (g.get("rationale") or "").strip().replace("\n", " ")[:140]
                    if rat:
                        facts.append(f"  goals.open.#{gid}.why: {rat}")
            if level >= 2:
                for status in ("approved", "rejected", "dismissed"):
                    resolved = get_proposed_goals(status=status, limit=3)
                    for g in resolved:
                        gid = g.get("id")
                        gt = (g.get("goal") or "").strip().replace("\n", " ")[:100]
                        facts.append(f"  goals.{status}.#{gid}: {gt}")
            if not facts:
                facts.append("  (no pending goals — add one with: python scripts/goal.py \"...\")")
            return facts
        except Exception:
            return []

    def _get_sensory_context(
        self, query: str = "", level: int = 1, threshold: float = 5.0,
        max_results: int = 20,
    ) -> List[str]:
        """Surface recent sensory events (mic, vision, ambient, ...).

        L1: last 5 events, one line each.
        L2: last 10 events + per-source counts in last hour.
        L3: last 20 events + meta snippets.
        """
        try:
            from sensory.schema import get_recent_events, counts_by_source
        except Exception:
            return []

        try:
            n = {1: 5, 2: 10, 3: max_results}.get(level, 10)
            rows = get_recent_events(limit=n)
            facts: List[str] = []
            if level >= 2:
                try:
                    from datetime import datetime, timedelta, timezone
                    since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
                    counts = counts_by_source(since_iso=since)
                    if counts:
                        summary = ", ".join(f"{k}:{v}" for k, v in counts.items())
                        facts.append(f"  sensory.last_hour: {summary}")
                except Exception:
                    pass
            for r in rows:
                rid = r.get("id")
                src = r.get("source", "?")
                kind = r.get("kind", "?")
                ts = (r.get("created_at") or "")[-8:]  # HH:MM:SS
                text = (r.get("text") or "").strip().replace("\n", " ")
                if len(text) > 140:
                    text = text[:137] + "..."
                facts.append(f"  sensory.{src}.{rid} [{ts} {kind}]: {text}")
            if not facts:
                facts.append("  (no sensory events yet — POST /api/sensory/record to add)")
            return facts
        except Exception:
            return []

    def get_state(self, query: str = "") -> str:
        """
        Convenience method: score + build_state in one call.
        
        For when you just need the STATE block without intermediate access.
        
        Args:
            query: The input to build state for
        
        Returns:
            Formatted STATE block string
        """
        scores = self.score(query)
        return self.build_state(scores, query)

    def preview_state(self, query: str) -> Dict[str, Any]:
        """
        Preview what STATE would look like for a given query.
        
        Returns the scores, state block, and token estimate without
        sending anything to the LLM. Used by the dashboard test panel.
        """
        scores = self.score(query)
        state_block = self.build_state(scores, query, record_activations=False)
        # Rough token estimate: ~0.75 tokens per word
        token_est = len(state_block.split()) * 0.75
        budgets = allocate_budgets(scores)
        return {
            "query": query,
            "thread_scores": scores,
            "state_block": state_block,
            "total_tokens": int(token_est),
            "thresholds": SCORE_THRESHOLDS,
            "context_window": CONTEXT_WINDOW,
            "state_budget": int(CONTEXT_WINDOW * STATE_FRACTION),
            "source_budgets": budgets,
        }
    
    def build_context(
        self,
        level: int = 2,
        query: str = "",
        threads: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build STATE + CONTEXT blocks by calling each thread's introspect().
        
        Args:
            level: Context level (1=minimal, 2=standard, 3=full)
            query: User's message - passed to threads for relevance filtering
            threads: Which threads to query (default: all)
        
        Returns:
            {
                "state": {thread: {health, state, ...}},
                "context": [{"key": ..., "value": ..., "source": ...}, ...],
                "meta": {"level": N, "total_facts": N, ...}
            }
        """
        level = max(1, min(3, level))
        threads = threads or THREADS
        
        state = {}
        all_facts = []
        all_concepts = set()
        
        # Call each thread's introspect
        for thread_name in threads:
            adapter = self._get_adapter(thread_name)
            if not adapter:
                state[thread_name] = {"health": {"status": "error", "message": "Adapter not found"}}
                continue
            
            try:
                result = adapter.introspect(context_level=level, query=query)
                result_dict = result.to_dict()
                
                # Add to state
                state[thread_name] = {
                    "health": result_dict.get("health", {}),
                    "state": result_dict.get("state", {}),
                    "fact_count": result_dict.get("fact_count", 0),
                }
                
                # Collect facts with source
                for fact in result_dict.get("facts", []):
                    all_facts.append({
                        "fact": fact,
                        "source": thread_name,
                    })
                
                # Collect relevant concepts
                for concept in result_dict.get("relevant_concepts", []):
                    all_concepts.add(concept)
                    
            except Exception as e:
                state[thread_name] = {
                    "health": {"status": "error", "message": str(e)[:100]},
                    "state": {},
                    "fact_count": 0,
                }
        
        # Track timing
        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        return {
            "state": state,
            "context": all_facts,
            "relevant_concepts": list(all_concepts),
            "meta": {
                "level": level,
                "total_facts": len(all_facts),
                "threads_queried": threads,
                "timestamp": self._last_context_time,
                "query": query[:100] if query else None,
            }
        }
    
    def get_all_health(self) -> Dict[str, Dict]:
        """Get health status from all threads. Each thread is fully isolated."""
        health = {}
        for thread_name in THREADS:
            # Completely isolated - adapter load + health check in one try block
            try:
                adapter = self._get_adapter(thread_name)
                if adapter is not None:
                    try:
                        report = adapter.health()
                        health[thread_name] = report.to_dict()
                    except Exception as e:
                        health[thread_name] = {"status": "error", "message": f"health() failed: {str(e)[:80]}"}
                else:
                    health[thread_name] = {"status": "error", "message": "Adapter failed to load"}
            except Exception as e:
                # Catch-all for any unexpected error
                health[thread_name] = {"status": "error", "message": f"Unexpected: {str(e)[:80]}"}
        return health
    
    def record_interaction(
        self,
        user_message: str,
        agent_response: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """Record an interaction to the log thread."""
        try:
            from agent.threads.log.schema import log_event
            log_event(
                event_type="convo",
                data=json.dumps({
                    "user": user_message[:500],
                    "agent": agent_response[:500],
                }),
                metadata=metadata,
                source="agent",
            )
        except Exception as e:
            print(f"⚠️ Failed to record interaction: {e}")
    
    def get_identity_facts(self, level: int = 2) -> List[str]:
        """Get identity facts as simple strings (backwards compatibility)."""
        ctx = self.build_context(level=level, threads=["identity"])
        return [item["fact"] for item in ctx.get("context", [])]
    
    def get_context_string(self, level: int = 2, query: str = "") -> str:
        """Get context as a formatted string for system prompt."""
        ctx = self.build_context(level=level, query=query)
        
        lines = []
        for item in ctx.get("context", []):
            fact = item.get("fact", "")
            source = item.get("source", "")
            lines.append(f"[{source}] {fact}")
        
        return "\n".join(lines)


# Singleton instance
_SUBCONSCIOUS: Optional[Subconscious] = None


def get_subconscious() -> Subconscious:
    """Get the singleton Subconscious instance."""
    global _SUBCONSCIOUS
    if _SUBCONSCIOUS is None:
        _SUBCONSCIOUS = Subconscious()
    return _SUBCONSCIOUS


def build_state(query: str = "") -> str:
    """
    Convenience function: score(query) + build_state(scores, query).
    
    This is the primary state assembly function for the architecture.
    Agent.generate(state, query) IS the assess step.
    
    Flow:
        scores = score(query)
        state = build_state(scores, query)
        response = agent.generate(state, query)  ← this IS assess
    
    Args:
        query: The assess block content (user message, file chunk, etc.)
    
    Returns:
        Formatted STATE block string with dot notation facts.
    """
    return get_subconscious().get_state(query)


def build_context(level: int = 2, query: str = "", threads: Optional[List[str]] = None) -> Dict[str, Any]:
    """Convenience function to build context (legacy)."""
    return get_subconscious().build_context(level, query, threads)


def record_interaction(user_msg: str, agent_resp: str, meta: Optional[Dict] = None) -> None:
    """Convenience function to record interaction."""
    get_subconscious().record_interaction(user_msg, agent_resp, meta)
