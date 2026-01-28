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
    
    def _consolidate(self) -> None:
        """Run consolidation - score facts and promote approved ones."""
        # Step 1: Update thread summaries for embedding-based scoring
        self._update_thread_summaries()
        
        # Step 2: Score pending facts and set their status
        self._score_and_triage_pending()
        
        # Step 3: Promote approved facts to long-term memory
        self._promote_approved_facts()
    
    def _score_and_triage_pending(self) -> None:
        """
        Score pending facts and set status based on confidence.
        
        - High confidence → auto-approve
        - Low confidence → pending_review (requires user approval)
        - Duplicate of existing → reject
        """
        try:
            from agent.subconscious.temp_memory import (
                get_all_pending, update_fact_status
            )
            from agent.threads.identity.schema import pull_profile_facts
            from agent.threads.linking_core.scoring import (
                get_embedding, cosine_similarity, keyword_fallback_score
            )
            
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
            
            for fact in pending:
                # Skip already triaged facts
                if fact.status != 'pending':
                    continue
                
                try:
                    confidence = self._calculate_confidence(
                        fact.text,
                        existing_texts,
                        get_embedding,
                        cosine_similarity,
                        keyword_fallback_score
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
        get_embedding,
        cosine_similarity,
        keyword_fallback_score
    ) -> float:
        """
        Calculate confidence score for a fact.
        
        Returns:
            0.0-1.0 for valid facts (higher = more confident)
            -1.0 for duplicates
        """
        if not fact_text:
            return 0.0
        
        # Check for duplicates
        fact_emb = get_embedding(fact_text)
        
        for existing in existing_texts:
            if not existing.strip():
                continue
            
            if fact_emb is not None:
                existing_emb = get_embedding(existing)
                if existing_emb is not None:
                    similarity = cosine_similarity(fact_emb, existing_emb)
                    if similarity >= self.DUPLICATE_THRESHOLD:
                        return -1.0  # Duplicate
            else:
                # Keyword fallback
                similarity = keyword_fallback_score(fact_text, existing)
                if similarity >= self.DUPLICATE_THRESHOLD:
                    return -1.0  # Duplicate
        
        # Calculate confidence based on:
        # 1. Length (very short facts are less trustworthy)
        # 2. Specificity (contains concrete details)
        # 3. Structure (proper hierarchical key)
        
        confidence = 0.5  # Base confidence
        
        # Length factor
        word_count = len(fact_text.split())
        if word_count >= 3:
            confidence += 0.1
        if word_count >= 5:
            confidence += 0.1
        
        # Specificity factor (contains names, numbers, concrete nouns)
        import re
        if re.search(r'\b[A-Z][a-z]+\b', fact_text):  # Capitalized words
            confidence += 0.1
        if re.search(r'\d+', fact_text):  # Numbers
            confidence += 0.05
        
        # Source quality (explicit > conversation > inferred)
        # This would come from fact.source but we don't have it here
        # Could be enhanced later
        
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
                            profile_id="user",
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
        
        Identity: Personal details, preferences, biographical info
        Philosophy: Beliefs, values, principles, worldview
        
        Returns:
            "identity" or "philosophy"
        """
        text_lower = fact_text.lower()
        
        # Philosophy indicators: beliefs, values, principles
        philosophy_signals = [
            'believe', 'belief', 'think that', 'feel that',
            'value', 'values', 'important to me',
            'principle', 'principles',
            'philosophy', 'worldview',
            'should', 'ought', 'must',
            'right', 'wrong', 'good', 'bad', 'evil',
            'fair', 'unfair', 'justice', 'ethical', 'moral',
            'meaning', 'purpose', 'matters',
            'truth', 'honest', 'integrity',
            'freedom', 'liberty', 'autonomy',
            'respect', 'dignity', 'compassion',
            'always try to', 'never want to',
            'my view on', 'my stance on',
        ]
        
        # Identity indicators: personal facts
        identity_signals = [
            'my name', 'i am', "i'm", 'called',
            'i live', 'i work', 'my job', 'my career',
            'i like', 'i love', 'i prefer', 'i enjoy', 'favorite',
            'i have', 'i own',
            'my age', 'years old', 'born',
            'my email', 'my phone', 'contact',
            'my family', 'my wife', 'my husband', 'my kids',
            'i studied', 'my degree', 'my school',
            'my hobby', 'hobbies', 'free time',
        ]
        
        philosophy_score = sum(1 for signal in philosophy_signals if signal in text_lower)
        identity_score = sum(1 for signal in identity_signals if signal in text_lower)
        
        # Philosophy needs stronger signal since identity is default
        if philosophy_score >= 2 or (philosophy_score >= 1 and identity_score == 0):
            return "philosophy"
        
        return "identity"
    
    def _generate_key(self, fact_text: str, destination: str = "identity") -> str:
        """
        Generate a hierarchical key from fact text.
        
        Examples:
            Identity: "User likes Python" → "user.preferences.python"
            Philosophy: "I believe in honesty" → "values.honesty"
        """
        import re
        
        text_lower = fact_text.lower()
        
        if destination == "philosophy":
            # Philosophy categories
            if any(w in text_lower for w in ['believe', 'belief', 'think that']):
                category = "beliefs"
            elif any(w in text_lower for w in ['value', 'important', 'matters']):
                category = "values"
            elif any(w in text_lower for w in ['principle', 'always', 'never']):
                category = "principles"
            elif any(w in text_lower for w in ['should', 'ought', 'right', 'wrong']):
                category = "ethics"
            elif any(w in text_lower for w in ['meaning', 'purpose', 'life']):
                category = "worldview"
            else:
                category = "stance"
            prefix = "philosophy"
        else:
            # Identity categories
            if any(w in text_lower for w in ['name', 'called', 'i am', "i'm"]):
                category = "identity"
            elif any(w in text_lower for w in ['like', 'love', 'prefer', 'enjoy', 'favorite']):
                category = "preferences"
            elif any(w in text_lower for w in ['work', 'job', 'career', 'profession']):
                category = "professional"
            elif any(w in text_lower for w in ['hobby', 'hobbies', 'free time', 'weekend']):
                category = "hobbies"
            elif any(w in text_lower for w in ['live', 'city', 'country', 'from']):
                category = "location"
            else:
                category = "general"
            prefix = "user"
        
        # Extract key words (remove stop words)
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
            # Fallback: use hash of text
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
