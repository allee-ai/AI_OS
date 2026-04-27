"""
Reflex Thread Adapter
=====================

Provides quick patterns, shortcuts, and triggers to Agent.

This thread answers: "What's my instant response? Is this a familiar pattern?"

Modules:
- greetings: Quick greeting patterns
- shortcuts: User-defined shortcuts
- system: System reflexes (resource management)
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import re
import json

try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.reflex.schema import (
        get_greetings, get_shortcuts, get_system_reflexes,
        add_greeting, add_shortcut, add_system_reflex,
    )
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import (
        get_greetings, get_shortcuts, get_system_reflexes,
        add_greeting, add_shortcut, add_system_reflex,
    )


class ReflexThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for quick patterns and automatic responses.
    
    Uses local schema.py for in-memory pattern storage.
    - greetings: Greeting responses
    - shortcuts: User shortcuts
    - system: System reflexes
    """
    
    _name = "reflex"
    _description = "Quick patterns, shortcuts, and triggers"
    
    def health(self) -> HealthReport:
        """Check reflex thread health."""
        try:
            greetings = get_greetings(level=1)
            shortcuts = get_shortcuts(level=1)
            
            total_patterns = len(greetings) + len(shortcuts)
            
            if total_patterns > 0:
                return HealthReport.ok(
                    f"{total_patterns} patterns",
                    row_count=total_patterns
                )
            else:
                # Even with no patterns, reflex is ready
                return HealthReport.ok(
                    "Ready (no patterns yet)",
                    row_count=0
                )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def get_greetings(self, level: int = 2) -> List[Dict]:
        """Get greeting patterns."""
        return get_greetings(level)
    
    def get_shortcuts(self, level: int = 2) -> List[Dict]:
        """Get user shortcuts."""
        return get_shortcuts(level)
    
    def get_system_reflexes(self, level: int = 2) -> List[Dict]:
        """Get system reflexes."""
        return get_system_reflexes(level)
    
    def get_modules(self) -> List[str]:
        """List modules in this thread."""
        return ["greetings", "shortcuts", "system"]
    
    def get_data(self, level: int = 2, limit: int = 50) -> List[Dict]:
        """Pull all data from this thread."""
        all_data = []
        for g in get_greetings(level)[:limit]:
            all_data.append({**g, "module": "greetings"})
        for s in get_shortcuts(level)[:limit]:
            all_data.append({**s, "module": "shortcuts"})
        for r in get_system_reflexes(level)[:limit]:
            all_data.append({**r, "module": "system"})
        return all_data[:limit]
    
    def add_greeting(
        self,
        key: str,
        response: str,
        weight: float = 0.8
    ) -> None:
        """Add a greeting response."""
        add_greeting(key, response, weight)
    
    def add_shortcut(
        self,
        trigger: str,
        response: str,
        description: str = ""
    ) -> None:
        """Add a user shortcut."""
        add_shortcut(trigger, response, description)
    
    def match_greeting(self, text: str) -> Optional[str]:
        """
        Check if text matches a greeting pattern.
        
        Returns the response if matched, None otherwise.
        """
        text_lower = text.lower().strip()
        
        greetings = self.get_greetings(level=1)
        for g in greetings:
            key = g.get("key", "")
            data = g.get("data", {})
            response = data.get("value", "")
            
            # Simple keyword match
            if key in text_lower or text_lower.startswith(key):
                return response
        
        return None
    
    def match_shortcut(self, text: str) -> Optional[str]:
        """
        Check if text matches a shortcut.
        
        Returns the response if matched, None otherwise.
        """
        text_lower = text.lower().strip()
        
        shortcuts = self.get_shortcuts(level=1)
        for s in shortcuts:
            data = s.get("data", {})
            trigger = data.get("trigger", "").lower()
            response = data.get("response", "")
            
            if trigger and trigger in text_lower:
                return response
        
        return None
    
    def try_quick_response(self, text: str) -> Optional[str]:
        """
        Try to get a quick response for the input.
        
        Checks greetings and shortcuts.
        Returns response string or None if no match.
        """
        # Check shortcuts first (more specific)
        shortcut_resp = self.match_shortcut(text)
        if shortcut_resp:
            return shortcut_resp
        
        # Check greetings
        greeting_resp = self.match_greeting(text)
        if greeting_resp:
            return greeting_resp
        
        return None
    
    def get_section_metadata(self) -> List[str]:
        """Permanent reflex metadata for STATE section header."""
        try:
            greetings = get_greetings()
            shortcuts = get_shortcuts()
            patterns = len(greetings) + len(shortcuts)
            lines = [f"  patterns: {patterns}"]
            # Trigger stats from DB
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN enabled THEN 1 ELSE 0 END) as active "
                    "FROM reflex_triggers"
                ).fetchone()
                total = row["total"] if row else 0
                active = row["active"] if row else 0
                if total > 0:
                    lines.append(f"  triggers: {total} ({active} active)")
            except Exception:
                pass
            # Meta-thoughts stats (cognitive residue)
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute(
                    "SELECT COUNT(*) as total, "
                    "SUM(CASE WHEN kind='expected' AND graded=1 THEN 1 ELSE 0 END) as graded_expected, "
                    "SUM(CASE WHEN kind='expected' THEN 1 ELSE 0 END) as total_expected "
                    "FROM reflex_meta_thoughts"
                ).fetchone()
                if row and row["total"]:
                    total = row["total"]
                    ge = row["graded_expected"] or 0
                    te = row["total_expected"] or 0
                    if te > 0:
                        lines.append(f"  meta_thoughts: {total} (graded: {ge}/{te} expectations)")
                    else:
                        lines.append(f"  meta_thoughts: {total}")
                # Pending expectations that are aging — prompts self-grading
                pending = conn.execute("""
                    SELECT COUNT(*) as cnt FROM reflex_meta_thoughts
                    WHERE kind = 'expected'
                      AND graded = 0
                      AND created_at <= datetime('now', '-5 minutes')
                """).fetchone()
                if pending and pending["cnt"]:
                    lines.append(f"  pending_expectations: {pending['cnt']}")
            except Exception:
                pass
            return lines
        except Exception:
            return []

    def get_section_rules(self) -> List[str]:
        return [
            "  rules:",
            "  - Apply matching patterns when relevant. These are learned shortcuts.",
            "  - Do not invent patterns not listed here.",
            "  - reflex.meta.* entries are my own prior thoughts about earlier turns. Read them; do not treat them as user statements.",
        ]

    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Reflex introspection with budget-aware fact packing.

        Uses _budget_fill to fit pattern/shortcut facts within a
        per-level token budget.

        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Minimum weight for patterns (0-10 scale)
        """
        relevant_concepts: List[str] = []

        min_weight = threshold / 10.0
        raw = self._get_raw_facts(min_weight=min_weight)

        if query:
            raw, relevant_concepts = self._relevance_boost(raw, query)

        facts = self._budget_fill(raw, context_level, query=query)

        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts,
        )

    def _get_raw_facts(self, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """Get raw facts with l1/l2/l3 value tiers for _budget_fill.

        Returns dicts with: path, l1_value, l2_value, l3_value, weight.
        """
        raw: List[Dict] = []

        # Greetings
        greetings = self.get_greetings(3)
        for g in greetings:
            key = g.get("key", "")
            weight = g.get("weight", 0.8)
            if weight < min_weight or not key:
                continue
            data = g.get("data", {})
            response = data.get("value", "")
            raw.append({
                "path": f"reflex.greetings.{key}",
                "l1_value": key,
                "l2_value": f"{key} → {response[:50]}" if response else key,
                "l3_value": f"{key} → {response}" if response else key,
                "weight": weight,
            })

        # Shortcuts
        shortcuts = self.get_shortcuts(3)
        for s in shortcuts:
            key = s.get("key", "")
            weight = s.get("weight", 0.5)
            if weight < min_weight:
                continue
            data = s.get("data", {})
            trigger = data.get("trigger", "")
            response = data.get("response", "")
            if trigger:
                safe_key = (
                    key.replace("/", "_").replace(" ", "_")
                    if key
                    else trigger.replace("/", "_")
                )
                raw.append({
                    "path": f"reflex.shortcuts.{safe_key}",
                    "l1_value": trigger,
                    "l2_value": f"{trigger} → {response[:50]}" if response else trigger,
                    "l3_value": f"{trigger} → {response}" if response else trigger,
                    "weight": weight,
                })

        # System reflexes
        system = self.get_system_reflexes(3)
        for r in system:
            key = r.get("key", "")
            weight = r.get("weight", 0.5)
            if weight < min_weight or not key:
                continue
            data = r.get("data", {})
            action = data.get("action", "")
            raw.append({
                "path": f"reflex.system.{key}",
                "l1_value": key,
                "l2_value": f"{key}: {action[:50]}" if action else key,
                "l3_value": f"{key}: {action}" if action else key,
                "weight": weight,
            })

        # Meta-thoughts (cognitive residue from prior turns)
        # Best-effort read: if the table is missing or DB fails, we just
        # contribute nothing. Meta-thoughts never break the STATE read.
        #
        # Session-scoping rule (2026-04-23):
        #   - Session-less entries (session_id IS NULL) are situational
        #     reflexes that fire on key/trigger — always eligible.
        #     These are the curated copilot/user_correction priors.
        #   - Session-scoped entries (session_id IS NOT NULL) are
        #     in-conversation residue — only visible inside that session,
        #     never bled across conversations.
        try:
            import os as _os_prov
            provenance_on = _os_prov.getenv("AIOS_META_PROVENANCE", "1") == "1"
            from agent.threads.reflex.schema import get_recent_meta_thoughts
            # Resolve current session if available so session-scoped
            # residue from THIS conversation survives, other sessions
            # don't leak in.
            _current_sid = None
            try:
                from agent.threads.log.schema import get_active_sessions
                _active = get_active_sessions()
                if _active:
                    _current_sid = (_active[0].get("data") or {}).get("session_id")
            except Exception:
                _current_sid = None

            # Pull a wider window than we'll surface (60) so high-weight
            # curated entries aren't crowded out by fresh auto-generated
            # system grades. We then rank + truncate below.
            meta = get_recent_meta_thoughts(
                min_weight=min_weight,
                limit=60,
            )
            # Session-scope filter: drop residue from OTHER sessions.
            # Session-less (session_id is None/"") always survives —
            # those are the situational priors.
            def _session_ok(m):
                sid = m.get("session_id")
                if not sid:
                    return True  # session-less prior, always eligible
                if _current_sid and sid == _current_sid:
                    return True  # residue from current conversation
                return False
            meta = [m for m in meta if _session_ok(m)]

            # Source priority: user_correction is the highest-signal
            # source — it carries off-policy ground-truth the agent
            # cannot generate from inside its own loop. copilot self-notes
            # are still curated but must not co-mingle with that tier;
            # they're on-policy and risk self-reinforcement. Within a
            # priority tier, rank by weight desc.
            #   2026-04-27: split copilot from user_correction so the
            #   asymmetry between external correction and self-note is
            #   structural, not implicit.
            _SRC_PRI = {
                "user_correction": 0,
                "copilot": 1,
                "model": 2,
                "seed": 3,
                "system": 4,
            }
            try:
                meta = sorted(
                    meta,
                    key=lambda m: (
                        _SRC_PRI.get(m.get("source", ""), 9),
                        -float(m.get("weight", 0.0) or 0.0),
                    ),
                )
            except Exception:
                pass
            # Cap to 20 for STATE packing; curated entries now at top.
            meta = meta[:20]
            # Reserve at least 1 slot for user_correction entries from
            # the last 24h so they survive budget truncation downstream.
            # (Implemented simply via the sort above; reflex adapter's
            # caller honours list order.)
            # Newest first; oldest (end of list) gets a mild weight decay
            # so stale thoughts are more easily filtered by threshold.
            for i, m in enumerate(meta):
                kind = m.get("kind", "")
                content = m.get("content", "")
                if not content or kind not in ("rejected", "expected", "unknown", "compression"):
                    continue
                base_weight = float(m.get("weight", 0.5) or 0.5)
                # Asymmetric weight floors:
                #   user_correction: 0.9 — off-policy ground-truth, must
                #     not be decayed out by window position. Also immune
                #     to the min_weight threshold filter below.
                #   copilot: 0.7 — curated self-notes, but on-policy.
                #     Floor is lower so weak self-notes can still be
                #     filtered if they fall under threshold.
                src = m.get("source", "")
                if src == "user_correction":
                    base_weight = max(base_weight, 0.9)
                elif src == "copilot":
                    base_weight = max(base_weight, 0.7)
                # Simple linear decay across the returned window
                decayed = max(0.1, base_weight * (1.0 - 0.03 * i))
                # Only user_correction bypasses min_weight — everything
                # else (including copilot) must clear the bar.
                if decayed < min_weight and src != "user_correction":
                    continue
                tid = m.get("id", 0)
                short = content if len(content) <= 100 else content[:97] + "..."
                # For 'expected' that has been graded, suffix with match signal
                if kind == "expected" and m.get("graded"):
                    try:
                        delta = json.loads(m.get("grade_delta") or "{}")
                        suffix = " [hit]" if delta.get("match") else " [miss]"
                    except Exception:
                        suffix = ""
                    short = short + suffix
                # Provenance prefix — seeds get no prefix (keep the
                # teaching example clean); all other sources get [source].
                if provenance_on and src and src != "seed":
                    prov = f"[{src}] "
                else:
                    prov = ""
                raw.append({
                    "path": f"reflex.meta.{kind}.{tid}",
                    "l1_value": f"{prov}{kind}: {short[:60]}",
                    "l2_value": f"{prov}{kind}: {short}",
                    "l3_value": f"{prov}{kind}: {content}",
                    "weight": decayed,
                })
        except Exception:
            # Silent: meta-thoughts are an enhancement, never required.
            pass

        return raw[:limit]
    
    def score_relevance(self, fact: str, context: Dict[str, Any] = None) -> float:
        """
        Score a fact by access frequency (Basal Ganglia function).
        
        High score if fact has been accessed many times.
        Uses stored weight when available; falls back to low default
        for facts that haven't formed habits yet.
        """
        if context and "weight" in context:
            return float(context["weight"])
        return 0.3
    
    def get_score_explanation(self, fact: str, score: float, context: Dict[str, Any] = None) -> str:
        """Explain frequency-based scoring."""
        if score > 0.7:
            return f"Reflex: {score:.2f} (high frequency - habitual)"
        elif score > 0.5:
            return f"Reflex: {score:.2f} (moderate frequency)"
        else:
            return f"Reflex: {score:.2f} (low frequency - new/rare)"


__all__ = ["ReflexThreadAdapter"]
