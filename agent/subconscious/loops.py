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
            "enabled": self.config.enabled,
            "max_errors": self.config.max_errors,
            "error_backoff": self.config.error_backoff,
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
    
    def __init__(self, interval: float = 60.0, model: str = None):  # 1 minute
        config = LoopConfig(
            interval_seconds=interval,
            name="memory",
            enabled=True
        )
        super().__init__(config, self._extract)
        self._last_processed_turn_id: Optional[int] = self._load_last_turn_id()
        self._model = model  # None = use env/default
    
    @property
    def model(self) -> str:
        """Get the model used for fact extraction."""
        import os
        if self._model:
            return self._model
        return os.getenv("AIOS_EXTRACT_MODEL", os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b"))
    
    @model.setter
    def model(self, value: str) -> None:
        self._model = value
    
    def _load_last_turn_id(self) -> Optional[int]:
        """Load _last_processed_turn_id from DB so it survives restart."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memory_loop_state (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                # Can't create table in readonly — fall through
                cur.execute(
                    "SELECT value FROM memory_loop_state WHERE key = 'last_processed_turn_id'"
                )
                row = cur.fetchone()
                return int(row[0]) if row else None
        except Exception:
            return None
    
    def _save_last_turn_id(self, turn_id: int) -> None:
        """Persist _last_processed_turn_id to DB."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection()) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memory_loop_state (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                conn.execute(
                    "INSERT OR REPLACE INTO memory_loop_state (key, value) VALUES (?, ?)",
                    ("last_processed_turn_id", str(turn_id))
                )
                conn.commit()
        except Exception:
            pass
    
    def get_unprocessed_count(self) -> int:
        """Return the number of conversation turns not yet read by the memory loop."""
        try:
            from data.db import get_connection
            from contextlib import closing
            with closing(get_connection(readonly=True)) as conn:
                cur = conn.cursor()
                if self._last_processed_turn_id:
                    cur.execute(
                        "SELECT COUNT(*) FROM convo_turns WHERE id > ?",
                        (self._last_processed_turn_id,)
                    )
                else:
                    cur.execute("SELECT COUNT(*) FROM convo_turns")
                return cur.fetchone()[0]
        except Exception:
            return 0
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["model"] = self.model
        base["unprocessed_turns"] = self.get_unprocessed_count()
        base["last_processed_turn_id"] = self._last_processed_turn_id
        return base
    
    def _extract(self) -> None:
        """Extract facts from recent conversation turns."""
        import json
        import re
        import os
        from contextlib import closing
        
        # 1. Get recent conversation turns since last_processed_turn_id
        try:
            from data.db import get_connection
            with closing(get_connection(readonly=True)) as conn:
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
            self._save_last_turn_id(turn_id)
        
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
            model = self.model
            
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
    
    Hybrid Approval System:
    - Facts with confidence >= threshold are auto-approved
    - Facts with confidence < threshold require user review
    - Approved facts are promoted to long-term memory
    """
    
    # Confidence threshold for auto-approval (0.0-1.0)
    # Below this requires human review
    AUTO_APPROVE_THRESHOLD = 0.7
    
    # Duplicate similarity threshold - above this, consider it a duplicate
    DUPLICATE_THRESHOLD = 0.85
    
    def __init__(self, interval: float = 300.0):  # 5 minutes
        config = LoopConfig(
            interval_seconds=interval,
            name="consolidation",
            enabled=True
        )
        super().__init__(config, self._consolidate)

    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["auto_approve_threshold"] = self.AUTO_APPROVE_THRESHOLD
        base["duplicate_threshold"] = self.DUPLICATE_THRESHOLD
        return base
    
    def _consolidate(self) -> None:
        """Run consolidation - score facts and promote approved ones."""
        # Step 1: Update thread summaries for embedding-based scoring
        self._update_thread_summaries()
        
        # Step 2: Score pending facts and set their status
        self._score_and_triage_pending()
        
        # Step 3: Promote approved facts to long-term memory
        self._promote_approved_facts()
    
    def _get_linking_core(self):
        """Get or create the LinkingCore adapter for scoring."""
        if not hasattr(self, '_linking_core') or self._linking_core is None:
            try:
                from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
                self._linking_core = LinkingCoreThreadAdapter()
            except Exception:
                self._linking_core = None
        return self._linking_core

    def _score_and_triage_pending(self) -> None:
        """
        Score pending facts using LinkingCore's scoring pipeline.
        
        Uses the same embedding + spread activation + co-occurrence scoring
        that the rest of the system uses, instead of hand-rolled heuristics.
        
        - High confidence → auto-approve
        - Low confidence → pending_review (requires user approval)
        - Duplicate of existing → reject
        """
        try:
            from agent.subconscious.temp_memory import (
                get_all_pending, update_fact_status
            )
            from agent.threads.identity.schema import pull_profile_facts
            
            # Get all pending facts (not yet triaged)
            pending = get_all_pending()
            if not pending:
                return
            
            # Get existing facts for duplicate checking
            existing_facts = pull_profile_facts(limit=500)
            existing_texts = [
                f"{f.get('key', '')} {f.get('l1_value', '')} {f.get('l2_value', '')} {f.get('l3_value', '')}"
                for f in existing_facts
            ]
            existing_texts = [t for t in existing_texts if t.strip()]
            
            linking_core = self._get_linking_core()
            
            for fact in pending:
                # Skip already triaged facts
                if fact.status != 'pending':
                    continue
                
                try:
                    confidence = self._calculate_confidence(
                        fact.text,
                        existing_texts,
                        linking_core
                    )
                    
                    # Determine status based on confidence
                    if confidence < 0:
                        # Negative score means duplicate
                        new_status = 'rejected'
                    elif confidence >= self.AUTO_APPROVE_THRESHOLD:
                        new_status = 'approved'
                    else:
                        new_status = 'pending_review'
                    
                    update_fact_status(fact.id, new_status, abs(confidence))
                    
                except Exception as e:
                    import sys
                    print(f"Error scoring fact {fact.id}: {e}", file=sys.stderr)
                    # On error, mark for review
                    update_fact_status(fact.id, 'pending_review', 0.0)
            
        except Exception as e:
            import sys
            print(f"Error in _score_and_triage_pending: {e}", file=sys.stderr)
    
    def _calculate_confidence(
        self,
        fact_text: str,
        existing_texts: list,
        linking_core=None
    ) -> float:
        """
        Calculate confidence score for a fact using LinkingCore scoring.
        
        Uses the same embedding similarity, co-occurrence, and spread
        activation pipeline as the rest of the system.
        
        Returns:
            0.0-1.0 for valid facts (higher = more confident)
            -1.0 for duplicates
        """
        if not fact_text or not fact_text.strip():
            return 0.0
        
        # --- Duplicate detection via LinkingCore ---
        if existing_texts and linking_core:
            try:
                scored = linking_core.score_relevance(
                    fact_text, existing_texts,
                    use_embeddings=True,
                    use_cooccurrence=False,
                    use_spread_activation=False
                )
                if scored:
                    _, top_similarity = scored[0]
                    if top_similarity >= self.DUPLICATE_THRESHOLD:
                        return -1.0  # Duplicate
            except Exception:
                pass
        
        # --- Quality scoring ---
        # Base confidence from text quality signals
        import re
        confidence = 0.5
        
        word_count = len(fact_text.split())
        if word_count >= 3:
            confidence += 0.1
        if word_count >= 5:
            confidence += 0.1
        
        # Specificity: proper nouns, numbers
        if re.search(r'\b[A-Z][a-z]+\b', fact_text):
            confidence += 0.1
        if re.search(r'\d+', fact_text):
            confidence += 0.05
        
        # Boost from linking core: does this fact connect to existing knowledge?
        if linking_core and existing_texts:
            try:
                scored = linking_core.score_relevance(
                    fact_text, existing_texts[:50],
                    use_embeddings=True,
                    use_cooccurrence=True,
                    use_spread_activation=True
                )
                if scored:
                    # Average relevance to existing knowledge (excluding duplicates)
                    non_dup = [(f, s) for f, s in scored if s < self.DUPLICATE_THRESHOLD]
                    if non_dup:
                        avg_relevance = sum(s for _, s in non_dup[:10]) / min(len(non_dup), 10)
                        # Related-to-existing-knowledge boost (up to +0.15)
                        confidence += min(0.15, avg_relevance * 0.3)
            except Exception:
                pass
        
        return min(1.0, max(0.0, confidence))
    
    def _promote_approved_facts(self) -> None:
        """
        Promote approved facts to long-term memory.
        Routes to identity or philosophy thread based on fact type.
        """
        try:
            from agent.subconscious.temp_memory import (
                get_approved_pending, mark_consolidated
            )
            from agent.threads.identity.schema import (
                push_profile_fact, create_profile, get_profiles,
                create_fact_type, get_fact_types
            )
            from agent.threads.philosophy.schema import (
                push_philosophy_profile_fact
            )
            
            approved = get_approved_pending()
            if not approved:
                return
            
            # Ensure default user profile exists (for identity facts)
            try:
                profiles = get_profiles()
                user_exists = any(p.get('profile_id') == 'user' for p in profiles)
                if not user_exists:
                    create_profile("user", "human", "User")
            except Exception:
                pass
            
            # Ensure "learned" fact type exists
            try:
                fact_types = get_fact_types()
                learned_exists = any(ft.get('fact_type') == 'learned' for ft in fact_types)
                if not learned_exists:
                    create_fact_type("learned", "Auto-learned from conversation", 0.5)
            except Exception:
                pass
            
            identity_count = 0
            philosophy_count = 0
            
            for fact in approved:
                try:
                    # Detect fact type: identity vs philosophy
                    fact_destination = self._classify_fact_destination(fact.text)
                    
                    # Generate key
                    if fact.hier_key:
                        key = fact.hier_key
                    else:
                        key = self._generate_key(fact.text, fact_destination)
                    
                    if fact_destination == "philosophy":
                        # Route to philosophy thread
                        push_philosophy_profile_fact(
                            profile_id="core.values",
                            key=key,
                            l1_value=fact.text[:100],
                            l2_value=fact.text[:250] if len(fact.text) > 100 else None,
                            l3_value=fact.text if len(fact.text) > 250 else None,
                            weight=fact.confidence_score or 0.5
                        )
                        philosophy_count += 1
                    else:
                        # Route to identity thread (default)
                        push_profile_fact(
                            profile_id="primary_user",
                            key=key,
                            fact_type="learned",
                            l1_value=fact.text[:100],
                            l2_value=fact.text[:250] if len(fact.text) > 100 else None,
                            l3_value=fact.text if len(fact.text) > 250 else None,
                            weight=fact.confidence_score or 0.5
                        )
                        identity_count += 1
                    
                    # Mark as consolidated
                    mark_consolidated(fact.id)

                    # Strengthen concept graph around the new fact
                    try:
                        from agent.threads.linking_core.schema import index_key_in_concept_graph
                        index_key_in_concept_graph(key, fact.text)
                    except Exception:
                        pass

                except Exception as e:
                    import sys
                    print(f"Error promoting fact {fact.id}: {e}", file=sys.stderr)
            
            # Log the consolidation
            total = identity_count + philosophy_count
            if total > 0:
                try:
                    from agent.threads.log import log_event
                    log_event(
                        "system:consolidation",
                        "facts_promoted",
                        f"Promoted {total} facts ({identity_count} identity, {philosophy_count} philosophy)"
                    )
                except:
                    pass
                    
        except Exception as e:
            import sys
            print(f"Error in _promote_approved_facts: {e}", file=sys.stderr)
    
    def _classify_fact_destination(self, fact_text: str) -> str:
        """
        Classify whether a fact belongs in identity or philosophy thread.
        
        Uses LinkingCore's score_threads — the same scoring the rest of the
        system uses for context gating. LinkingCore handles its own fallback
        (keyword scoring when embeddings are unavailable).
        
        Identity: Personal details, preferences, biographical info
        Philosophy: Beliefs, values, principles, worldview
        
        Returns:
            "identity" or "philosophy"
        """
        linking_core = self._get_linking_core()
        
        if not linking_core:
            return "identity"  # Safe default if adapter can't load
        
        try:
            scores = linking_core.score_threads(fact_text)
            identity_score = scores.get('identity', 5.0)
            philosophy_score = scores.get('philosophy', 5.0)
            
            # Philosophy needs to clearly win — identity is the safe default
            if philosophy_score > identity_score + 1.0:
                return "philosophy"
            return "identity"
        except Exception:
            return "identity"
    
    def _generate_key(self, fact_text: str, destination: str = "identity") -> str:
        """
        Generate a hierarchical key from fact text.
        
        Uses LinkingCore's concept extraction for the detail portion,
        and score_threads for category detection.
        
        Examples:
            Identity: "User likes Python" → "user.preferences.python"
            Philosophy: "I believe in honesty" → "philosophy.beliefs.honesty"
        """
        text_lower = fact_text.lower()
        
        # Determine category using linking core thread scoring
        linking_core = self._get_linking_core()
        
        if destination == "philosophy":
            prefix = "philosophy"
            categories = {
                "beliefs": "believe belief faith think opinion",
                "values": "value important matters care priority",
                "principles": "principle always never rule guideline",
                "ethics": "should ought right wrong moral ethical",
                "worldview": "meaning purpose life world perspective",
            }
            default_category = "stance"
        else:
            prefix = "user"
            categories = {
                "identity": "name called person who am age born",
                "preferences": "like love prefer enjoy favorite",
                "professional": "work job career profession company role",
                "hobbies": "hobby hobbies free time weekend recreation",
                "location": "live city country from location home",
            }
            default_category = "general"
        
        # Use linking core to find best-matching category
        category = default_category
        if linking_core:
            try:
                scored = linking_core.score_relevance(
                    fact_text,
                    list(categories.values()),
                    use_embeddings=True,
                    use_cooccurrence=False,
                    use_spread_activation=False
                )
                if scored:
                    best_desc = scored[0][0]
                    for name, desc in categories.items():
                        if desc == best_desc:
                            category = name
                            break
            except Exception:
                pass
        
        # Extract key detail words using linking core's concept extraction
        try:
            from agent.threads.linking_core.schema import extract_concepts_from_text
            concepts = extract_concepts_from_text(fact_text)[:3]
            if concepts:
                detail = "_".join(concepts)
            else:
                raise ValueError("no concepts")
        except Exception:
            # Fallback: manual extraction
            import re
            stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                          'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                          'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                          'i', 'me', 'my', 'myself', 'we', 'our', 'you', 'your', 'he',
                          'she', 'it', 'they', 'them', 'their', 'this', 'that', 'these',
                          'those', 'and', 'but', 'or', 'so', 'for', 'to', 'of', 'in',
                          'on', 'at', 'by', 'with', 'about', 'user', 'really', 'very',
                          'believe', 'think', 'feel', 'value', 'important'}
            words = re.findall(r'\b[a-z]+\b', text_lower)
            keywords = [w for w in words if w not in stop_words][:3]
            if keywords:
                detail = "_".join(keywords)
            else:
                import hashlib
                detail = hashlib.md5(fact_text.encode()).hexdigest()[:8]
        
        return f"{prefix}.{category}.{detail}"
    
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


# ─────────────────────────────────────────────────────────────
# Custom Chain-of-Thought Loops
# ─────────────────────────────────────────────────────────────

# Valid sources for custom loops
CUSTOM_LOOP_SOURCES = [
    "convos",        # Conversation turns
    "feeds",         # Feed items
    "temp_memory",   # Pending facts
    "identity",      # Identity thread facts
    "philosophy",    # Philosophy thread facts
    "log",           # Log events
    "workspace",     # Workspace files
]

# Valid targets for custom loop output
CUSTOM_LOOP_TARGETS = [
    "temp_memory",   # Store as temp facts for review
    "log",           # Write to log thread
]


def _ensure_custom_loops_table() -> None:
    """Create custom_loops table if it doesn't exist."""
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS custom_loops (
                    name TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL DEFAULT 'temp_memory',
                    interval_seconds REAL NOT NULL DEFAULT 300,
                    model TEXT,
                    prompt TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            conn.commit()
    except Exception as e:
        print(f"[CustomLoop] Failed to create table: {e}")


def save_custom_loop_config(
    name: str,
    source: str,
    target: str,
    interval: float,
    model: Optional[str],
    prompt: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Save or update a custom loop config in the database."""
    _ensure_custom_loops_table()
    
    if source not in CUSTOM_LOOP_SOURCES:
        raise ValueError(f"Invalid source '{source}'. Must be one of: {CUSTOM_LOOP_SOURCES}")
    if target not in CUSTOM_LOOP_TARGETS:
        raise ValueError(f"Invalid target '{target}'. Must be one of: {CUSTOM_LOOP_TARGETS}")
    if interval < 5:
        raise ValueError("Interval must be >= 5 seconds")
    if not prompt.strip():
        raise ValueError("Prompt cannot be empty")
    if not name.strip():
        raise ValueError("Name cannot be empty")
    
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO custom_loops
                    (name, source, target, interval_seconds, model, prompt, enabled, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """, (name.strip(), source, target, interval, model, prompt.strip(), int(enabled)))
            conn.commit()
        
        return {
            "name": name.strip(),
            "source": source,
            "target": target,
            "interval_seconds": interval,
            "model": model,
            "prompt": prompt.strip(),
            "enabled": enabled,
        }
    except Exception as e:
        raise RuntimeError(f"Failed to save custom loop: {e}")


def get_custom_loop_configs() -> List[Dict[str, Any]]:
    """Get all custom loop configs from the database."""
    _ensure_custom_loops_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection(readonly=True)) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name, source, target, interval_seconds, model, prompt, enabled, created_at, updated_at FROM custom_loops")
            rows = cur.fetchall()
            return [
                {
                    "name": r[0], "source": r[1], "target": r[2],
                    "interval_seconds": r[3], "model": r[4], "prompt": r[5],
                    "enabled": bool(r[6]), "created_at": r[7], "updated_at": r[8],
                }
                for r in rows
            ]
    except Exception:
        return []


def get_custom_loop_config(name: str) -> Optional[Dict[str, Any]]:
    """Get a single custom loop config by name."""
    configs = get_custom_loop_configs()
    for c in configs:
        if c["name"] == name:
            return c
    return None


def delete_custom_loop_config(name: str) -> bool:
    """Delete a custom loop config from the database."""
    _ensure_custom_loops_table()
    try:
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM custom_loops WHERE name = ?", (name,))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        return False


class CustomLoop(BackgroundLoop):
    """
    User-defined chain-of-thought loop.
    
    Reads from a source, passes through an LLM with a custom prompt,
    and writes results to a target.
    
    Sources: convos, feeds, temp_memory, identity, philosophy, log, workspace
    Targets: temp_memory, log
    """
    
    def __init__(
        self,
        name: str,
        source: str,
        target: str = "temp_memory",
        interval: float = 300.0,
        model: Optional[str] = None,
        prompt: str = "",
        enabled: bool = True,
    ):
        config = LoopConfig(
            interval_seconds=interval,
            name=name,
            enabled=enabled,
        )
        super().__init__(config, self._run_chain)
        self.source = source
        self.target = target
        self._model = model
        self.prompt = prompt
    
    @property
    def model(self) -> str:
        """Get the model used for this loop."""
        import os
        if self._model:
            return self._model
        return os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    
    @model.setter
    def model(self, value: str) -> None:
        self._model = value
    
    @property
    def stats(self) -> Dict[str, Any]:
        base = super().stats
        base["source"] = self.source
        base["target"] = self.target
        base["model"] = self.model
        base["prompt_preview"] = self.prompt[:80] + ("..." if len(self.prompt) > 80 else "")
        base["is_custom"] = True
        return base
    
    def to_config_dict(self) -> Dict[str, Any]:
        """Serialize this loop's configuration for API responses."""
        return {
            "name": self.config.name,
            "source": self.source,
            "target": self.target,
            "interval_seconds": self.config.interval_seconds,
            "model": self._model,
            "prompt": self.prompt,
            "enabled": self.config.enabled,
        }
    
    def _read_source(self) -> List[str]:
        """Read content from the configured source."""
        items = []
        try:
            if self.source == "convos":
                from data.db import get_connection
                from contextlib import closing
                with closing(get_connection(readonly=True)) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT user_message, assistant_message
                        FROM convo_turns
                        ORDER BY id DESC LIMIT 10
                    """)
                    for row in cur.fetchall():
                        text = f"User: {row[0]}"
                        if row[1]:
                            text += f"\nAssistant: {row[1]}"
                        items.append(text)
            
            elif self.source == "feeds":
                from data.db import get_connection
                from contextlib import closing
                with closing(get_connection(readonly=True)) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT title, content FROM feed_items
                        ORDER BY created_at DESC LIMIT 10
                    """)
                    for row in cur.fetchall():
                        items.append(f"{row[0]}: {row[1][:200]}" if row[1] else row[0])
            
            elif self.source == "temp_memory":
                from agent.subconscious.temp_memory import get_all_pending
                for fact in get_all_pending()[:20]:
                    items.append(f"[{fact.status}] {fact.text}")
            
            elif self.source == "identity":
                from agent.threads.identity.schema import pull_profile_facts
                facts = pull_profile_facts(limit=20)
                for f in facts:
                    items.append(f"{f.get('key', '')}: {f.get('l1_value', '')}")
            
            elif self.source == "philosophy":
                from agent.threads.philosophy.schema import pull_philosophy_profile_facts
                facts = pull_philosophy_profile_facts(limit=20)
                for f in facts:
                    items.append(f"{f.get('key', '')}: {f.get('l1_value', '')}")
            
            elif self.source == "log":
                from agent.threads.log import get_recent_events
                events = get_recent_events(limit=20)
                for e in events:
                    items.append(f"[{e.get('timestamp', '')}] {e.get('event_type', '')}: {e.get('description', '')}")
            
            elif self.source == "workspace":
                from workspace.schema import list_workspace_files
                files = list_workspace_files()
                for f in files[:10]:
                    items.append(f"{f.get('path', '')}: {f.get('description', '')}")
        
        except Exception as e:
            print(f"[CustomLoop:{self.config.name}] Source read error: {e}")
        
        return items
    
    def _write_target(self, results: List[Dict[str, Any]]) -> int:
        """Write processed results to the configured target. Returns count written."""
        written = 0
        try:
            if self.target == "temp_memory":
                from agent.subconscious.temp_memory import add_fact
                for result in results:
                    add_fact(
                        session_id=f"custom:{self.config.name}",
                        text=result.get("text", ""),
                        source=f"loop:{self.config.name}",
                        metadata={
                            "hier_key": result.get("key", f"custom.{self.config.name}"),
                            "confidence": result.get("confidence", 0.5),
                        }
                    )
                    written += 1
            
            elif self.target == "log":
                from agent.threads.log import log_event
                for result in results:
                    log_event(
                        f"custom:{self.config.name}",
                        "custom_loop",
                        result.get("text", ""),
                    )
                    written += 1
        
        except Exception as e:
            print(f"[CustomLoop:{self.config.name}] Target write error: {e}")
        
        return written
    
    def _run_chain(self) -> None:
        """Execute the chain-of-thought: read source → LLM → write target."""
        # 1. Read from source
        source_items = self._read_source()
        if not source_items:
            return
        
        # 2. Build prompt with source content
        source_text = "\n---\n".join(source_items)
        full_prompt = f"""{self.prompt}

SOURCE DATA:
\"\"\"
{source_text}
\"\"\"

Output a Python list of dicts with "key" and "text" fields.
If nothing worth noting, output: []

Python list:"""
        
        # 3. Call LLM
        try:
            import ollama
            response = ollama.chat(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}],
                options={"temperature": 0.1}
            )
            raw = response["message"]["content"].strip()
            
            # 4. Parse results
            import ast
            results = self._parse_results(raw)
            
            # 5. Write to target
            if results:
                written = self._write_target(results)
                try:
                    from agent.threads.log import log_event
                    log_event(
                        f"custom:{self.config.name}",
                        "custom_loop",
                        f"Processed {len(source_items)} items, wrote {written} results"
                    )
                except Exception:
                    pass
        
        except ImportError:
            print(f"[CustomLoop:{self.config.name}] ollama not installed")
        except Exception as e:
            print(f"[CustomLoop:{self.config.name}] LLM error: {e}")
    
    def _parse_results(self, raw: str) -> List[Dict[str, Any]]:
        """Parse LLM output into list of result dicts."""
        import ast
        
        if not raw:
            return []
        
        raw = raw.strip()
        
        # Extract from code block
        code_match = re.search(r'```(?:python)?\s*([\s\S]*?)```', raw)
        if code_match:
            raw = code_match.group(1).strip()
        
        # Find the list
        list_start = raw.find('[')
        if list_start < 0:
            return []
        raw = raw[list_start:]
        
        # Find matching bracket
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
        
        try:
            result = ast.literal_eval(raw)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict) and r.get("text")]
        except (ValueError, SyntaxError):
            pass
        
        try:
            fixed = raw.replace('true', 'True').replace('false', 'False').replace('null', 'None')
            result = ast.literal_eval(fixed)
            if isinstance(result, list):
                return [r for r in result if isinstance(r, dict) and r.get("text")]
        except (ValueError, SyntaxError):
            pass
        
        return []


class LoopManager:
    """
    Manages all background loops (built-in + custom).
    
    Provides unified start/stop and status reporting.
    """
    
    def __init__(self):
        self._loops: List[BackgroundLoop] = []
    
    def add(self, loop: BackgroundLoop) -> None:
        """Add a loop to be managed."""
        self._loops.append(loop)
    
    def remove(self, name: str) -> bool:
        """Remove and stop a loop by name."""
        for i, loop in enumerate(self._loops):
            if loop.config.name == name:
                loop.stop()
                self._loops.pop(i)
                return True
        return False
    
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
    
    def load_custom_loops(self) -> int:
        """Load custom loops from DB and add them to the manager. Returns count loaded."""
        configs = get_custom_loop_configs()
        loaded = 0
        for cfg in configs:
            if not cfg["enabled"]:
                continue
            # Skip if already loaded
            if self.get_loop(cfg["name"]):
                continue
            loop = CustomLoop(
                name=cfg["name"],
                source=cfg["source"],
                target=cfg["target"],
                interval=cfg["interval_seconds"],
                model=cfg["model"],
                prompt=cfg["prompt"],
                enabled=cfg["enabled"],
            )
            self.add(loop)
            loop.start()
            loaded += 1
        return loaded


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
    
    # Load user-defined custom loops from DB
    try:
        manager.load_custom_loops()
    except Exception as e:
        print(f"⚠️ Failed to load custom loops: {e}")
    
    return manager


__all__ = [
    "BackgroundLoop",
    "LoopConfig",
    "LoopStatus",
    "MemoryLoop",
    "ConsolidationLoop",
    "SyncLoop",
    "HealthLoop",
    "CustomLoop",
    "LoopManager",
    "create_default_loops",
    "CUSTOM_LOOP_SOURCES",
    "CUSTOM_LOOP_TARGETS",
    "save_custom_loop_config",
    "get_custom_loop_configs",
    "get_custom_loop_config",
    "delete_custom_loop_config",
]
