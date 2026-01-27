"""
Background Loops
================
Periodic tasks that run in the subconscious to maintain state.

Loops are responsible for:
- Consolidation: Scoring and promoting temp_memory facts
- Sync: Reconciling state across threads
- Health: Monitoring thread health and logging anomalies

Each loop runs on its own thread with configurable intervals.
"""

import threading
import time
import re
import json
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum


class LoopStatus(Enum):
    """Status of a background loop."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class LoopConfig:
    """Configuration for a background loop."""
    interval_seconds: float
    name: str
    enabled: bool = True
    max_errors: int = 3  # Stop after this many consecutive errors
    error_backoff: float = 2.0  # Multiply interval by this on error


class BackgroundLoop:
    """
    Base class for background loops.
    
    Runs a task function periodically on a daemon thread.
    Handles error recovery, backoff, and graceful shutdown.
    """
    
    def __init__(self, config: LoopConfig, task: Callable[[], None]):
        self.config = config
        self.task = task
        self._status = LoopStatus.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._consecutive_errors = 0
        self._last_run: Optional[str] = None
        self._run_count = 0
        self._error_count = 0
    
    @property
    def status(self) -> LoopStatus:
        return self._status
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "status": self._status.value,
            "interval": self.config.interval_seconds,
            "last_run": self._last_run,
            "run_count": self._run_count,
            "error_count": self._error_count,
            "consecutive_errors": self._consecutive_errors,
        }
    
    def start(self) -> None:
        """Start the background loop."""
        if self._status == LoopStatus.RUNNING:
            return
        
        if not self.config.enabled:
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"loop-{self.config.name}",
            daemon=True
        )
        self._status = LoopStatus.RUNNING
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the background loop gracefully."""
        if self._status != LoopStatus.RUNNING:
            return
        
        self._stop_event.set()
        self._status = LoopStatus.STOPPED
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
    
    def pause(self) -> None:
        """Pause the loop (keeps thread alive but skips tasks)."""
        if self._status == LoopStatus.RUNNING:
            self._status = LoopStatus.PAUSED
    
    def resume(self) -> None:
        """Resume a paused loop."""
        if self._status == LoopStatus.PAUSED:
            self._status = LoopStatus.RUNNING
    
    def _run_loop(self) -> None:
        """Main loop runner (runs on background thread)."""
        interval = self.config.interval_seconds
        
        while not self._stop_event.is_set():
            # Wait for interval or stop signal
            if self._stop_event.wait(timeout=interval):
                break
            
            # Skip if paused
            if self._status == LoopStatus.PAUSED:
                continue
            
            # Run the task
            try:
                self.task()
                self._last_run = datetime.now(timezone.utc).isoformat()
                self._run_count += 1
                self._consecutive_errors = 0
                interval = self.config.interval_seconds  # Reset interval
                
            except Exception as e:
                self._error_count += 1
                self._consecutive_errors += 1
                
                # Log error
                try:
                    from agent.threads.log import log_error
                    log_error(f"loop:{self.config.name}", e, context="background loop")
                except Exception:
                    pass
                
                # Apply backoff
                interval = min(
                    self.config.interval_seconds * (self.config.error_backoff ** self._consecutive_errors),
                    3600  # Cap at 1 hour
                )
                
                # Stop if too many errors
                if self._consecutive_errors >= self.config.max_errors:
                    self._status = LoopStatus.ERROR
                    break


class MemoryLoop(BackgroundLoop):
    """
    Periodically extracts facts from recent conversations.
    
    Processes new conversation turns and extracts identity/philosophy facts
    into temp_memory for user review before consolidation.
    """
    
    def __init__(self, interval: float = 60.0):  # 1 minute
        config = LoopConfig(
            interval_seconds=interval,
            name="memory",
            enabled=True
        )
        super().__init__(config, self._extract)
        self._last_processed_turn_id: Optional[int] = None
    
    def _extract(self) -> None:
        """Extract facts from recent conversation turns."""
        import json
        import re
        import os
        
        # 1. Get recent conversation turns since last_processed_turn_id
        try:
            from data.db import get_connection
            conn = get_connection(readonly=True)
            cur = conn.cursor()
            
            # Get unprocessed turns
            if self._last_processed_turn_id:
                cur.execute("""
                    SELECT ct.id, ct.user_message, ct.assistant_message, c.session_id
                    FROM convo_turns ct
                    JOIN convos c ON ct.convo_id = c.id
                    WHERE ct.id > ?
                    ORDER BY ct.id ASC
                    LIMIT 10
                """, (self._last_processed_turn_id,))
            else:
                # First run - get last 10 turns
                cur.execute("""
                    SELECT ct.id, ct.user_message, ct.assistant_message, c.session_id
                    FROM convo_turns ct
                    JOIN convos c ON ct.convo_id = c.id
                    ORDER BY ct.id DESC
                    LIMIT 10
                """)
            
            turns = cur.fetchall()
            conn.close()
            
            if not turns:
                return  # Nothing to process
            
        except Exception as e:
            print(f"[MemoryLoop] DB error: {e}")
            return
        
        # 2. Extract facts from each turn
        for turn in turns:
            turn_id, user_msg, assistant_msg, session_id = turn
            
            if not user_msg:
                continue
            
            # Build conversation snippet
            convo_text = f"User: {user_msg}"
            if assistant_msg:
                convo_text += f"\nAssistant: {assistant_msg}"
            
            # Extract facts using LLM
            facts = self._extract_facts_from_text(convo_text, session_id)
            
            # 3. Store in temp_memory
            if facts:
                try:
                    from agent.subconscious.temp_memory import add_fact
                    for fact in facts:
                        add_fact(
                            session_id=session_id,
                            text=fact.get("text", ""),
                            source="conversation",
                            metadata={
                                "hier_key": fact.get("key"),
                                "category": fact.get("category", "general"),
                                "confidence": fact.get("confidence", 0.5),
                                "turn_id": turn_id,
                            }
                        )
                except Exception as e:
                    print(f"[MemoryLoop] Failed to store fact: {e}")
            
            # 4. Update last_processed_turn_id
            self._last_processed_turn_id = turn_id
        
        # Log extraction run
        try:
            from agent.threads.log import log_event
            log_event(
                "system:memory_extract",
                "memory_loop",
                f"Processed {len(turns)} turns, extracted facts"
            )
        except:
            pass
    
    def _extract_facts_from_text(self, text: str, session_id: str) -> list:
        """
        Extract facts from conversation text using LLM.
        
        Strategy: Ask for simple Python list, retry until valid.
        
        Returns list of dicts: [{"key": "user.likes.coffee", "text": "User enjoys coffee"}]
        """
        import ast
        import os
        
        # Skip very short messages (likely greetings)
        if len(text) < 30:
            return []
        
        prompt = '''Extract facts from this conversation as a Python list.
Each fact is a dict with "key" and "text".
Keys are hierarchical like: user.preference.coffee, user.project.name, user.relationship.sarah

ONLY output a Python list. No explanation.

Example:
[{"key": "user.preference.language", "text": "User prefers Python"}, {"key": "user.project.taskmaster", "text": "User is building TaskMaster app"}]

If nothing worth remembering, output: []

Conversation:
"""
''' + text + '''
"""

Python list:'''

        try:
            import ollama
            model = os.getenv("AIOS_EXTRACT_MODEL", os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b"))
            
            max_attempts = 3
            for attempt in range(max_attempts):
                try:
                    response = ollama.chat(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        options={"temperature": 0.1}
                    )
                    raw_output = response['message']['content'].strip()
                    
                    # Try to parse as Python literal
                    facts = self._parse_python_list(raw_output)
                    
                    if facts is not None:  # Valid parse (even if empty list)
                        # Basic validation on each fact
                        validated = [f for f in facts if self._validate_fact(f)]
                        return validated
                    
                    # Invalid output - retry with correction prompt
                    if attempt < max_attempts - 1:
                        prompt = f'''Your previous output was not a valid Python list:
{raw_output}

Try again. Output ONLY a Python list like:
[{{"key": "user.x.y", "text": "fact"}}]

Or if no facts: []'''
                        
                except Exception as e:
                    print(f"[MemoryLoop] Attempt {attempt+1} failed: {e}")
                    continue
            
            return []  # All attempts failed
            
        except ImportError:
            print("[MemoryLoop] ollama not installed, skipping extraction")
            return []
        except Exception as e:
            print(f"[MemoryLoop] Extraction error: {e}")
            return []
    
    def _parse_python_list(self, raw: str) -> list:
        """
        Parse LLM output as Python list using ast.literal_eval.
        
        Safer than eval(), handles:
        - Trailing commas
        - Single or double quotes
        - Python dict/list literals
        
        Returns list if valid, None if parsing fails.
        """
        import ast
        
        if not raw:
            return None
        
        raw = raw.strip()
        
        # Extract from markdown code block if present
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        # Handle common LLM quirks
        # Remove leading text before the list
        list_start = raw.find('[')
        if list_start > 0:
            raw = raw[list_start:]
        
        # Find the matching closing bracket
        bracket_count = 0
        end_pos = 0
        for i, char in enumerate(raw):
            if char == '[':
                bracket_count += 1
            elif char == ']':
                bracket_count -= 1
                if bracket_count == 0:
                    end_pos = i + 1
                    break
        
        if end_pos > 0:
            raw = raw[:end_pos]
        
        # Try ast.literal_eval (safe Python literal parsing)
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, list):
                return result
        except (ValueError, SyntaxError):
            pass
        
        # Fallback: try fixing common issues
        try:
            # Replace True/False/None with Python-compatible values
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return result
        except (ValueError, SyntaxError):
            pass
        
        return None  # Couldn't parse
    
    def _validate_fact(self, fact: dict) -> bool:
        """
        Validate a fact dict before storing.
        
        Requires: {"key": "x.y.z", "text": "..."}
        Returns True if fact is valid and worth storing.
        """
        # Must have required fields
        if not isinstance(fact, dict):
            return False
        if not fact.get("text") or not fact.get("key"):
            return False
        
        text = fact.get("text", "")
        key = fact.get("key", "")
        
        # Text must be meaningful (not too short, not too long)
        if len(text) < 10 or len(text) > 500:
            return False
        
        # Key must be a string
        if not isinstance(key, str):
            return False
        
        # Reject obvious garbage
        garbage_patterns = [
            r'^[\[\]\{\}]+$',  # Just brackets
            r'^["\s]+$',       # Just quotes/whitespace
            r'^\[.*\]$',       # Looks like another JSON array
            r'^(ok|yes|no|hi|hello|thanks)\.?$',  # Trivial responses
        ]
        for pattern in garbage_patterns:
            if re.match(pattern, text, re.IGNORECASE):
                return False
        
        # Key should be hierarchical (has at least one dot)
        if "." not in key:
            # Auto-fix: prepend "user."
            fact["key"] = f"user.{key}"
        
        return True


class ConsolidationLoop(BackgroundLoop):
    """
    Periodically runs the consolidation daemon.
    
    On each cycle:
    1. Generate/update thread summaries for embedding-based scoring
    2. Score temp_memory facts and promote high-scoring ones
    3. Decay old/low-weight items
    """
    
    def __init__(self, interval: float = 300.0):  # 5 minutes
        config = LoopConfig(
            interval_seconds=interval,
            name="consolidation",
            enabled=True
        )
        super().__init__(config, self._consolidate)
    
    def _consolidate(self) -> None:
        """Run consolidation - update summaries and promote facts."""
        # Step 1: Update thread summaries for embedding-based scoring
        self._update_thread_summaries()
        
        # Step 2: Promote approved facts (TODO)
        # 1. Get approved facts from temp_memory
        # 2. Score them for relevance/importance
        # 3. Promote high-scoring facts to identity or philosophy thread
        # 4. Mark as consolidated in temp_memory
    
    def _update_thread_summaries(self) -> None:
        """
        Generate summaries for each thread and cache embeddings.
        
        This enables embedding-based thread scoring on wake.
        """
        try:
            from agent.threads.linking_core.scoring import set_thread_summary
            from agent.threads import get_all_threads
            
            for thread in get_all_threads():
                thread_name = getattr(thread, '_name', str(thread))
                
                # Skip linking_core itself
                if thread_name == 'linking_core':
                    continue
                
                # Get thread's introspection to build summary
                try:
                    if hasattr(thread, 'introspect'):
                        # Get L2 level for summary (not too detailed)
                        result = thread.introspect(context_level=2, query="", threshold=5.0)
                        if result and hasattr(result, 'facts') and result.facts:
                            # Take up to 10 most important facts
                            summary_facts = result.facts[:10]
                            summary = ' '.join(summary_facts)
                            
                            if summary:
                                set_thread_summary(thread_name, summary)
                            
                            if summary:
                                set_thread_summary(thread_name, summary)
                except Exception as e:
                    # Debug: print error
                    import sys
                    print(f"Error getting introspect for {thread_name}: {e}", file=sys.stderr)
                    continue
            
            # Log completion
            try:
                from agent.threads.log import log_event
                log_event(
                    "system:consolidation",
                    "consolidation_loop",
                    "Updated thread summaries for embedding scoring"
                )
            except:
                pass
        except Exception as e:
            import sys
            print(f"Consolidation error: {e}", file=sys.stderr)


class SyncLoop(BackgroundLoop):
    """
    Periodically syncs state across threads.
    
    Ensures all threads have consistent view of state,
    persists pending changes, and reconciles conflicts.
    """
    
    def __init__(self, interval: float = 600.0):  # 10 minutes
        config = LoopConfig(
            interval_seconds=interval,
            name="sync",
            enabled=True
        )
        super().__init__(config, self._sync)
    
    def _sync(self) -> None:
        """Sync state across threads."""
        try:
            from agent.subconscious.core import get_core
            
            core = get_core()
            
            # Check all threads for sync needs
            for adapter in core.registry.get_all():
                if hasattr(adapter, 'sync'):
                    adapter.sync()
            
            # Log sync completion
            from agent.threads.log import log_event
            log_event(
                "system:sync",
                "sync_loop",
                f"Synced {core.registry.count()} threads"
            )
        except Exception:
            pass  # Best effort


class HealthLoop(BackgroundLoop):
    """
    Periodically checks health of all threads.
    
    Logs anomalies and can trigger alerts for degraded threads.
    """
    
    def __init__(self, interval: float = 60.0):  # 1 minute
        config = LoopConfig(
            interval_seconds=interval,
            name="health",
            enabled=True
        )
        super().__init__(config, self._check_health)
        self._last_status: Dict[str, str] = {}
    
    def _check_health(self) -> None:
        """Check health of all registered threads."""
        try:
            from agent.subconscious.core import get_core
            from agent.threads.base import ThreadStatus
            
            core = get_core()
            health_reports = core.registry.health_all()
            
            # Check for status changes
            for name, report in health_reports.items():
                current_status = report.status.value
                previous_status = self._last_status.get(name, "unknown")
                
                # Log status changes
                if current_status != previous_status:
                    from agent.threads.log import log_event
                    
                    level = "WARN" if report.status in (ThreadStatus.ERROR, ThreadStatus.DEGRADED) else "INFO"
                    log_event(
                        "system:health",
                        "health_loop",
                        f"Thread '{name}' status: {previous_status} → {current_status}",
                        level=level
                    )
                
                self._last_status[name] = current_status
                
        except Exception:
            pass  # Best effort


class LoopManager:
    """
    Manages all background loops.
    
    Provides unified start/stop and status reporting.
    """
    
    def __init__(self):
        self._loops: List[BackgroundLoop] = []
    
    def add(self, loop: BackgroundLoop) -> None:
        """Add a loop to be managed."""
        self._loops.append(loop)
    
    def start_all(self) -> None:
        """Start all managed loops."""
        for loop in self._loops:
            loop.start()
    
    def stop_all(self) -> None:
        """Stop all managed loops."""
        for loop in self._loops:
            loop.stop()
    
    def get_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all loops."""
        return [loop.stats for loop in self._loops]
    
    def get_loop(self, name: str) -> Optional[BackgroundLoop]:
        """Get a specific loop by name."""
        for loop in self._loops:
            if loop.config.name == name:
                return loop
        return None


def create_default_loops() -> LoopManager:
    """
    Create a LoopManager with all default background loops.
    
    Returns:
        Configured LoopManager ready to start
    """
    manager = LoopManager()
    manager.add(MemoryLoop())       # Extract facts from conversations
    manager.add(ConsolidationLoop()) # Promote approved facts
    manager.add(SyncLoop())          # Sync state across threads
    manager.add(HealthLoop())        # Monitor thread health
    return manager


__all__ = [
    "BackgroundLoop",
    "LoopConfig",
    "LoopStatus",
    "MemoryLoop",
    "ConsolidationLoop",
    "SyncLoop",
    "HealthLoop",
    "LoopManager",
    "create_default_loops",
]
