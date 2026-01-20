"""
Nola Consolidation Daemon
=========================
Periodic service that compresses temp_memory facts using L3→L2→L1 pipeline
and promotes high-scoring ones to permanent threads.

FACT LIFECYCLE (L3 → L2 → L1 Compression):
    1. New facts enter temp_memory at full detail (L3)
    2. Consolidation scores all facts using linking_core.score_relevance()
    3. High-scoring facts (>0.8): Keep L1+L2+L3, weight=0.9
    4. Medium facts (0.5-0.8): Keep L1+L2 only, drop L3, weight=0.6
    5. Low facts (0.3-0.5): Keep L1 only, weight=0.3
    6. Very low (<0.3): Discard entirely
    7. Update concept_links with co-occurrences
    8. Clear temp_memory

SUBCONSCIOUS LOOPS:
    - Consolidation: Every N turns or session end
    - Decay: Daily/weekly temporal decay
    - Reinforcement: Per-access Hebbian strengthening
    - Deduplication: On new fact creation

Usage:
    from Nola.services.consolidation_daemon import ConsolidationDaemon
    
    daemon = ConsolidationDaemon()
    result = daemon.run()  # Returns stats about what was consolidated
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

# Import dependencies
from Nola.temp_memory import get_all_pending, mark_consolidated, get_stats
from Nola.services.memory_service import MemoryService
from data.db import get_connection
from Nola.threads.linking_core.schema import (
    extract_concepts_from_text,
    record_concept_cooccurrence,
)

# upsert_fact_relevance may not exist yet - make optional
try:
    from Nola.threads.schema import upsert_fact_relevance
except ImportError:
    def upsert_fact_relevance(*args, **kwargs): pass

# Import linking_core for modern scoring
try:
    from Nola.threads.linking_core.adapter import LinkingCoreThreadAdapter
    HAS_LINKING_CORE = True
except ImportError:
    HAS_LINKING_CORE = False
    LinkingCoreThreadAdapter = None

# Import log functions from new thread system
try:
    from Nola.threads.log import log_event
    from Nola.threads import get_thread
except ImportError:
    log_event = None
    get_thread = None


@dataclass
class ConsolidationConfig:
    """Configuration for L3→L2→L1 compression consolidation."""
    
    # Score thresholds for compression tiers (0.0-1.0 scale from linking_core)
    high_score_threshold: float = 0.8    # Keep L1+L2+L3, weight=0.9
    medium_score_threshold: float = 0.5  # Keep L1+L2 only, weight=0.6
    low_score_threshold: float = 0.3     # Keep L1 only, weight=0.3
    discard_threshold: float = 0.3       # Below this: discard entirely
    
    # Batch settings
    max_facts_per_run: int = 50  # Process at most N facts per run
    
    # Trigger settings
    auto_trigger_after_convos: int = 5  # Auto-run after N conversations
    
    # Model
    model: Optional[str] = None  # Uses env NOLA_MODEL_NAME or default


class ConsolidationDaemon:
    """
    Daemon for consolidating short-term memory facts to long-term storage.
    """
    
    def __init__(self, config: Optional[ConsolidationConfig] = None):
        self.config = config or ConsolidationConfig()
        self.memory_service = MemoryService(
            model=self.config.model or "",
            session_id="consolidation_daemon"
        )
        self._ensure_history_table()
    
    def _ensure_history_table(self):
        """Ensure consolidation_history table exists."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS consolidation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT DEFAULT CURRENT_TIMESTAMP,
                fact_text TEXT NOT NULL,
                fact_id INTEGER,
                original_level INTEGER DEFAULT 0,
                new_level INTEGER NOT NULL,
                score_json TEXT,
                reason TEXT,
                session_id TEXT
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_consolidation_ts 
            ON consolidation_history(ts)
        """)
        
        conn.commit()
    
    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Run L3→L2→L1 compression consolidation.
        
        Uses linking_core for multidimensional scoring and compresses facts
        based on score tiers (high/medium/low).
        
        Args:
            dry_run: If True, score facts but don't actually consolidate
        
        Returns:
            Stats dict with counts and details
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "facts_processed": 0,
            "high_score": 0,      # L1+L2+L3
            "medium_score": 0,    # L1+L2
            "low_score": 0,       # L1 only
            "discarded": 0,       # Below threshold
            "concept_links_updated": 0,
            "errors": [],
            "details": []
        }
        
        # Get pending facts
        pending = get_all_pending()
        
        if not pending:
            result["message"] = "No pending facts to consolidate"
            return result
        
        # Limit batch size
        pending = pending[:self.config.max_facts_per_run]
        result["facts_processed"] = len(pending)
        
        # Generate session summary for context (combine all pending fact text)
        session_summary = " ".join([fact.text for fact in pending])
        
        # Score all facts using linking_core
        scored_facts = self._score_facts_batch(session_summary, pending)
        
        # Extract concepts from session for co-occurrence tracking
        if not dry_run:
            concepts = extract_concepts_from_text(session_summary)
            if concepts:
                record_concept_cooccurrence(concepts)
                result["concept_links_updated"] = len(concepts)
        
        # Process each scored fact with L3→L2→L1 compression
        for fact, score_data in scored_facts:
            try:
                final_score = score_data.get("final_score", 0.0)
                
                detail = {
                    "fact_id": fact.id,
                    "text": fact.text[:100],
                    "score": final_score,
                    "levels_kept": None,
                    "weight": None,
                    "action": None
                }
                
                # L3→L2→L1 Compression tiers
                if final_score >= self.config.high_score_threshold:
                    # High score → Keep L1+L2+L3, weight=0.9
                    levels = [1, 2, 3]
                    weight = 0.9
                    if not dry_run:
                        self._promote_with_levels(fact, levels, weight, score_data)
                        mark_consolidated(fact.id, json.dumps(score_data))
                        self._record_history(fact, levels, score_data)
                    detail["action"] = "high_score"
                    detail["levels_kept"] = levels
                    detail["weight"] = weight
                    result["high_score"] += 1
                    
                elif final_score >= self.config.medium_score_threshold:
                    # Medium score → Keep L1+L2 only, weight=0.6
                    levels = [1, 2]
                    weight = 0.6
                    if not dry_run:
                        self._promote_with_levels(fact, levels, weight, score_data)
                        mark_consolidated(fact.id, json.dumps(score_data))
                        self._record_history(fact, levels, score_data)
                    detail["action"] = "medium_score"
                    detail["levels_kept"] = levels
                    detail["weight"] = weight
                    result["medium_score"] += 1
                    
                elif final_score >= self.config.low_score_threshold:
                    # Low score → Keep L1 only, weight=0.3
                    levels = [1]
                    weight = 0.3
                    if not dry_run:
                        self._promote_with_levels(fact, levels, weight, score_data)
                        mark_consolidated(fact.id, json.dumps(score_data))
                        self._record_history(fact, levels, score_data)
                    detail["action"] = "low_score"
                    detail["levels_kept"] = levels
                    detail["weight"] = weight
                    result["low_score"] += 1
                    
                else:
                    # Very low score → Discard
                    if not dry_run:
                        mark_consolidated(fact.id, json.dumps(score_data))
                        self._record_history(fact, [], score_data, "discarded_low_score")
                    detail["action"] = "discarded"
                    result["discarded"] += 1
                
                result["details"].append(detail)
                
            except Exception as e:
                result["errors"].append({
                    "fact_id": fact.id,
                    "error": str(e)
                })
        
        # Log the consolidation event
        if log_event and not dry_run:
            log_event(
                "memory:consolidate",
                "consolidation_daemon",
                f"Processed {result['facts_processed']} facts: {result['high_score']} high, {result['medium_score']} medium, {result['low_score']} low, {result['discarded']} discarded",
                high_score=result["high_score"],
                medium_score=result["medium_score"],
                low_score=result["low_score"],
                discarded=result["discarded"],
                concepts_updated=result["concept_links_updated"]
            )
        
        return result
    
    def _score_facts_batch(self, session_summary: str, facts: List) -> List[Tuple[Any, Dict]]:
        """
        Score all facts using linking_core or fallback to MemoryService.
        
        Args:
            session_summary: Combined text from all facts for context
            facts: List of fact objects to score
        
        Returns:
            List of (fact, score_dict) tuples
        """
        if HAS_LINKING_CORE and LinkingCoreThreadAdapter:
            # Use linking_core for modern multi-dimensional scoring
            adapter = LinkingCoreThreadAdapter()
            fact_texts = [f.text for f in facts]
            
            # score_relevance returns List[Tuple[str, float]] - (fact_text, score)
            scored_tuples = adapter.score_relevance(
                stimuli=session_summary,
                facts=fact_texts,
                use_embeddings=True,
                use_cooccurrence=True,
                use_spread_activation=True
            )
            
            # Build dict for easy lookup: fact_text -> score
            score_map = {text: score for text, score in scored_tuples}
            
            # Match facts with their scores, create full score dicts
            results = []
            for fact in facts:
                final_score = score_map.get(fact.text, 0.0)
                score_dict = {
                    "final_score": final_score,
                    "embedding_score": final_score,  # Simplified for now
                    "identity_score": 0.0,
                    "log_score": 0.0,
                    "form_score": 0.0,
                    "philosophy_score": 0.0,
                    "reflex_score": 0.0,
                    "cooccurrence_score": 0.0
                }
                results.append((fact, score_dict))
            return results
        else:
            # Fallback to old MemoryService scoring
            results = []
            for fact in facts:
                score = self.memory_service.score_fact(fact.text)
                # Convert old score (0-10) to new format (0-1.0)
                normalized = {
                    "final_score": min(1.0, score.get("total", 0) / 10.0),
                    "legacy_score": score,
                    "identity_score": 0.0,
                    "log_score": 0.0,
                    "form_score": 0.0,
                    "philosophy_score": 0.0,
                    "reflex_score": 0.0,
                    "cooccurrence_score": 0.0
                }
                results.append((fact, normalized))
            return results
    
    def _promote_with_levels(self, fact, levels: List[int], weight: float, score_data: dict):
        """
        Promote a fact to identity thread with L3→L2→L1 compression.
        
        Args:
            fact: Fact object from temp_memory
            levels: Which levels to keep (e.g., [1,2,3] or [1,2] or [1])
            weight: Importance weight (0.0-1.0)
            score_data: Score dict from linking_core
        """
        try:
            # Get identity thread
            if get_thread:
                identity = get_thread("identity")
                
                # Push to identity using new thread system with levels
                identity.push(
                    key="dynamic_memory",
                    value=fact.text,  # L3 is full text
                    levels=levels,
                    weight=weight,
                    metadata={
                        "source": "consolidation_daemon",
                        "consolidated_at": datetime.now(timezone.utc).isoformat(),
                        "final_score": score_data.get("final_score", 0.0)
                    }
                )
                
                # Write dimensional scores to fact_relevance table
                fact_key = fact.text[:50]  # Use first 50 chars as key
                upsert_fact_relevance(
                    fact_key=fact_key,
                    fact_text=fact.text,
                    scores={
                        "identity_score": score_data.get("identity_score", 0.0),
                        "log_score": score_data.get("log_score", 0.0),
                        "form_score": score_data.get("form_score", 0.0),
                        "philosophy_score": score_data.get("philosophy_score", 0.0),
                        "reflex_score": score_data.get("reflex_score", 0.0),
                        "cooccurrence_score": score_data.get("cooccurrence_score", 0.0),
                        "final_score": score_data.get("final_score", 0.0)
                    },
                    source_thread="identity",
                    session_id=self.memory_service.session_id
                )
        except Exception as e:
            # Fallback to old method if new thread system unavailable
            self._promote_to_level_legacy(fact, max(levels), score_data)
    
    def _promote_to_level_legacy(self, fact, level: int, score: dict):
        """
        Promote a fact to the specified level in the thread database.
        
        Args:
            fact: Fact object from temp_memory
            level: Target level (2 or 3)
            score: Score dict from scorer
        """
        from Nola.threads.schema import push_to_module, pull_from_module
        
        # Get current dynamic memory from DB
        try:
            rows = pull_from_module("identity", "user_profile", level=3)
            memory_row = next((r for r in rows if r.get("key") == "dynamic_memory"), None)
            if memory_row:
                data = memory_row.get("data", {}).get("levels", {})
            else:
                data = {}
        except Exception:
            data = {}
        
        # Ensure structure exists
        if not data:
            data = {"level_1": [], "level_2": [], "level_3": []}
        
        level_key = f"level_{level}"
        
        # Add to target level if not duplicate
        if fact.text not in data.get(level_key, []):
            data.setdefault(level_key, []).append(fact.text)
            
            # If promoting to L2, also add to L3
            if level == 2 and fact.text not in data.get("level_3", []):
                data.setdefault("level_3", []).append(fact.text)
            
            # Save to thread database
            push_to_module(
                "identity", "user_profile", "dynamic_memory",
                {"type": "memory_structure", "description": "User's dynamic memory levels"},
                {"levels": data},
                level=level
            )
    
    def _record_history(self, fact, levels: List[int], score: dict, reason: Optional[str] = None):
        """
        Record consolidation history with L3→L2→L1 compression info.
        
        Args:
            fact: Fact object
            levels: List of levels kept (e.g., [1,2,3])
            score: Score dict
            reason: Optional reason string
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        if reason is None:
            final_score = score.get("final_score", score.get("total", 0))
            reason = f"L3→L2→L1: kept levels {levels}, score={final_score:.3f}"
        
        cursor.execute("""
            INSERT INTO consolidation_history 
            (fact_text, fact_id, original_level, new_level, score_json, reason, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fact.text,
            fact.id,
            0,  # Original level (0 = temp_memory)
            max(levels) if levels else 0,  # Record highest level kept
            json.dumps(score),
            reason,
            fact.session_id
        ))
        
        conn.commit()
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get recent consolidation history.
        
        Args:
            limit: Max records to return
        
        Returns:
            List of history records
        """
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM consolidation_history
            ORDER BY ts DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        
        return [
            {
                "id": row["id"],
                "timestamp": row["ts"],
                "fact_text": row["fact_text"],
                "fact_id": row["fact_id"],
                "new_level": row["new_level"],
                "score": json.loads(row["score_json"]) if row["score_json"] else None,
                "reason": row["reason"],
                "session_id": row["session_id"]
            }
            for row in rows
        ]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get consolidation statistics."""
        temp_stats = get_stats()
        
        conn = get_connection(readonly=True)
        cursor = conn.cursor()
        
        # Count by level
        cursor.execute("""
            SELECT new_level, COUNT(*) 
            FROM consolidation_history 
            GROUP BY new_level
        """)
        level_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Recent activity
        cursor.execute("""
            SELECT COUNT(*) FROM consolidation_history 
            WHERE ts > datetime('now', '-24 hours')
        """)
        recent_24h = cursor.fetchone()[0]
        
        return {
            "temp_memory": temp_stats,
            "history": {
                "promoted_l1": level_counts.get(1, 0),
                "promoted_l2": level_counts.get(2, 0),
                "promoted_l3": level_counts.get(3, 0),
                "discarded": level_counts.get(0, 0),
                "total": sum(level_counts.values()),
                "last_24h": recent_24h
            }
        }


# Convenience function for manual/API trigger
def run_consolidation(dry_run: bool = False) -> Dict[str, Any]:
    """
    Run the consolidation daemon.
    
    Args:
        dry_run: If True, score but don't consolidate
    
    Returns:
        Consolidation result stats
    """
    daemon = ConsolidationDaemon()
    return daemon.run(dry_run=dry_run)
