"""
Nola Consolidation Daemon
=========================
Periodic service that processes facts from temp_memory and promotes
high-scoring ones to long-term memory (user.json / identity DB).

Flow:
    1. Get pending facts from temp_memory
    2. Score each fact using MemoryService.score_fact()
    3. Facts scoring above threshold → promote to L3 (or L2 if very high)
    4. Log consolidation event
    5. Mark facts as consolidated in temp_memory
    6. Record history in consolidation_history table

Triggers:
    - After N conversations (configurable)
    - On explicit API call (/api/consolidate)
    - On timer (optional background task)

Usage:
    from Nola.services.consolidation_daemon import ConsolidationDaemon
    
    daemon = ConsolidationDaemon()
    result = daemon.run()  # Returns stats about what was consolidated
"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Dict, Any

# Import dependencies
from Nola.temp_memory import get_all_pending, mark_consolidated, get_stats
from Nola.services.memory_service import MemoryService
from Nola.threads.schema import get_connection

# Import log functions from new thread system
try:
    from Nola.threads.log import log_event
except ImportError:
    log_event = None


@dataclass
class ConsolidationConfig:
    """Configuration for the consolidation daemon."""
    
    # Score thresholds
    l2_threshold: float = 4.0   # Score >= 4.0 → promote to L2
    l3_threshold: float = 3.0   # Score >= 3.0 → promote to L3
    discard_threshold: float = 2.0  # Score < 2.0 → discard (mark consolidated but don't save)
    
    # Batch settings
    max_facts_per_run: int = 50  # Process at most N facts per run
    
    # Trigger settings
    auto_trigger_after_convos: int = 5  # Auto-run after N conversations
    
    # Model
    model: str = None  # Uses env NOLA_MODEL_NAME or default


class ConsolidationDaemon:
    """
    Daemon for consolidating short-term memory facts to long-term storage.
    """
    
    def __init__(self, config: ConsolidationConfig = None):
        self.config = config or ConsolidationConfig()
        self.memory_service = MemoryService(
            model=self.config.model,
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
        Run the consolidation process.
        
        Args:
            dry_run: If True, score facts but don't actually consolidate
        
        Returns:
            Stats dict with counts and details
        """
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "facts_processed": 0,
            "promoted_l2": 0,
            "promoted_l3": 0,
            "discarded": 0,
            "skipped": 0,
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
        
        # Process each fact
        for fact in pending:
            try:
                # Score the fact
                score = self.memory_service.score_fact(fact.text)
                score_json = json.dumps(score)
                
                detail = {
                    "fact_id": fact.id,
                    "text": fact.text[:100],
                    "score": score["total"],
                    "action": None
                }
                
                # Determine action based on score
                if score["total"] >= self.config.l2_threshold:
                    # High score → promote to L2
                    if not dry_run:
                        self._promote_to_level(fact, 2, score)
                        mark_consolidated(fact.id, score_json)
                        self._record_history(fact, 2, score)
                    detail["action"] = "promoted_l2"
                    result["promoted_l2"] += 1
                    
                elif score["total"] >= self.config.l3_threshold:
                    # Medium score → promote to L3
                    if not dry_run:
                        self._promote_to_level(fact, 3, score)
                        mark_consolidated(fact.id, score_json)
                        self._record_history(fact, 3, score)
                    detail["action"] = "promoted_l3"
                    result["promoted_l3"] += 1
                    
                elif score["total"] < self.config.discard_threshold:
                    # Low score → discard
                    if not dry_run:
                        mark_consolidated(fact.id, score_json)
                        self._record_history(fact, 0, score, "discarded_low_score")
                    detail["action"] = "discarded"
                    result["discarded"] += 1
                    
                else:
                    # Score between discard and L3 threshold → keep pending
                    detail["action"] = "skipped"
                    result["skipped"] += 1
                
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
                f"Processed {result['facts_processed']} facts",
                promoted_l2=result["promoted_l2"],
                promoted_l3=result["promoted_l3"],
                discarded=result["discarded"]
            )
        
        return result
    
    def _promote_to_level(self, fact, level: int, score: dict):
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
    
    def _record_history(self, fact, new_level: int, score: dict, reason: str = None):
        """Record the consolidation in history table."""
        conn = get_connection()
        cursor = conn.cursor()
        
        if reason is None:
            reason = f"score={score['total']:.2f}"
        
        cursor.execute("""
            INSERT INTO consolidation_history 
            (fact_text, fact_id, original_level, new_level, score_json, reason, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            fact.text,
            fact.id,
            0,  # Original level (0 = temp_memory)
            new_level,
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
