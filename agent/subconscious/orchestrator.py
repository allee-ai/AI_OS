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
import json


# Thread list - linking_core included for UI visibility
THREADS = ["identity", "log", "form", "philosophy", "reflex", "linking_core"]

# Top-level modules — scored for relevance alongside threads.
# Each module provides summarised context (conversations, files, etc.)
# and goes through the same score → level → threshold pipeline.
MODULES = ["chat", "workspace"]

# Score thresholds for context levels
# Score determines: (1) block order, (2) L1/L2/L3 level, (3) fact weight threshold
SCORE_THRESHOLDS = {
    "L1": 3.5,   # 0 - 3.5: L1 (lean), only high-weight facts
    "L2": 7.0,   # 3.5 - 7: L2 (medium)
    "L3": 10.0,  # 7 - 10: L3 (full)
}

# Per-source token budget caps — prevents any single source from
# dominating STATE.  Sources with large fact stores (identity) get
# a tighter budget so smaller sources stay visible.
SOURCE_BUDGETS = {
    # Threads
    "identity":     200,
    "log":          120,
    "form":         120,   # Now includes tool traces
    "philosophy":    80,
    "reflex":        60,
    "linking_core":  60,
    # Modules
    "chat":         150,   # Past conversation summaries
    "workspace":    150,   # Files, summaries, FTS matches
}


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
        
        return scores
    
    def build_state(self, scores: Dict[str, float], query: str = "") -> str:
        """
        Build STATE block from scored threads AND modules.
        
        Step 2 of the flow: build_state(scores) → STATE
        
        All sources (threads like identity/log/form AND modules like
        chat/workspace) are sorted by relevance score together.  Each
        source goes through the same score → level → threshold pipeline
        and is subject to its SOURCE_BUDGETS cap.
        
        Args:
            scores: Source relevance scores from score()
            query: Optional query for filtering
        
        Returns:
            Formatted STATE block string
        """
        # Order ALL sources (threads + modules) by score, highest first
        ordered_sources: List[Tuple[str, float]] = sorted(
            scores.items(),
            key=lambda x: x[1],
            reverse=True,
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
            
            if source_name in THREADS:
                # ---------- Thread source ----------
                section = self._build_thread_section(
                    source_name, level, threshold, query
                )
            elif source_name in MODULES:
                # ---------- Module source ----------
                section = self._build_module_section(
                    source_name, level, threshold, query
                )
            else:
                continue
            
            if section:
                lines.append("")
                lines.extend(section)
        
        lines.append("")
        lines.append("== END STATE ==")
        
        self._last_context_time = datetime.now(timezone.utc).isoformat()
        self._last_query = query
        
        return "\n".join(lines)
    
    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    
    def _build_thread_section(
        self, thread_name: str, level: int, threshold: float, query: str
    ) -> List[str]:
        """Build a STATE section for a scored thread via its adapter."""
        adapter = self._get_adapter(thread_name)
        if not adapter:
            return []
        
        # Apply per-source token budget cap
        cap = SOURCE_BUDGETS.get(thread_name)
        if cap and hasattr(adapter, '_token_budgets'):
            adapter._token_budgets = {
                1: min(adapter._token_budgets.get(1, 150), cap),
                2: min(adapter._token_budgets.get(2, 400), cap),
                3: min(adapter._token_budgets.get(3, 800), cap),
            }
        
        try:
            result = adapter.introspect(
                context_level=level, query=query, threshold=threshold
            )
            result_dict = result.to_dict()
            facts = result_dict.get("facts", [])
        except TypeError:
            # Adapter doesn't support threshold yet
            try:
                result = adapter.introspect(context_level=level, query=query)
                result_dict = result.to_dict()
                facts = result_dict.get("facts", [])
            except Exception as e:
                print(f"⚠️ {thread_name} introspect failed: {e}")
                return []
        except Exception as e:
            print(f"⚠️ {thread_name} introspect failed: {e}")
            return []
        
        if not facts:
            return []
        
        description = getattr(adapter, '_description', '')
        section = [
            f"[{thread_name}] {description}",
            f"  context_level: {level}",
            f"  fact_count: {len(facts)}",
        ]
        section.extend(facts)
        return section
    
    def _build_module_section(
        self, module_name: str, level: int, threshold: float, query: str
    ) -> List[str]:
        """Build a STATE section for a scored module (chat, workspace, …)."""
        providers = {
            "chat": self._get_chat_context,
            "workspace": self._get_workspace_context,
        }
        provider = providers.get(module_name)
        if not provider:
            return []
        
        facts = provider(query=query, level=level, threshold=threshold)
        if not facts:
            return []
        
        # Enforce token budget
        cap = SOURCE_BUDGETS.get(module_name, 200)
        budget_facts: List[str] = []
        tokens = 0
        for f in facts:
            t = len(f.split())
            if tokens + t > cap:
                break
            budget_facts.append(f)
            tokens += t
        
        if not budget_facts:
            return []
        
        descriptions = {
            "chat": "Past conversations and discussion history",
            "workspace": "Files and documents I have access to",
        }
        section = [
            f"[{module_name}] {descriptions.get(module_name, '')}",
            f"  context_level: {level}",
            f"  fact_count: {len(budget_facts)}",
        ]
        section.extend(budget_facts)
        return section
    
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
            "  | reflex | HOW | My learned patterns, my shortcuts |",
            "  | log | WHEN/WHERE | My event timeline, my session history |",
            "  | linking_core | WHICH | My concept graph, my relevance scoring |",
            "  | Module | | |",
            "  | chat | RECALL | Past conversations, discussion history |",
            "  | workspace | CONTEXT | Files, documents, project state |",
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
        state_block = self.build_state(scores, query)
        # Rough token estimate: ~0.75 tokens per word
        token_est = len(state_block.split()) * 0.75
        return {
            "query": query,
            "thread_scores": scores,
            "state_block": state_block,
            "total_tokens": int(token_est),
            "thresholds": SCORE_THRESHOLDS,
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
