import json
import sys
import os
from pathlib import Path
from typing import List
import ollama

from Nola.path_utils import (
    ensure_project_root_on_path,
    ensure_nola_root_on_path,
    warn_if_not_venv,
)

project_root = ensure_project_root_on_path(Path(__file__).resolve())
nola_root = ensure_nola_root_on_path(Path(__file__).resolve())
_venv_warning = warn_if_not_venv(project_root)
if _venv_warning:
    print(f"⚠️  {_venv_warning}")

# Import temp_memory for short-term storage
from Nola.temp_memory import add_fact, get_all_pending, get_stats

# Import log functions from new thread system
try:
    from Nola.threads.log import log_event, set_session
except ImportError:
    log_event = None
    set_session = None

# Import unified event log
try:
    from Nola.threads.schema import log_event as unified_log
except ImportError:
    def unified_log(*args, **kwargs): pass

# Import identity adapter for pushing user facts
try:
    from Nola.threads import get_thread
    _identity_adapter = get_thread("identity")
except ImportError:
    _identity_adapter = None

# New: Use thread DB for dynamic memory
def _get_dynamic_memory_from_db():
    """Read dynamic memory from thread database."""
    try:
        from Nola.threads.schema import pull_from_module
        rows = pull_from_module("identity", "user_profile", level=3)
        for row in rows:
            if row.get("key") == "dynamic_memory":
                return row.get("data_json", {}).get("levels", {
                    "level_1": [], "level_2": [], "level_3": []
                })
    except Exception:
        pass
    return {"level_1": [], "level_2": [], "level_3": []}

def _save_dynamic_memory_to_db(memory_data: dict):
    """Save dynamic memory to thread database."""
    try:
        from Nola.threads.schema import push_to_module
        push_to_module(
            "identity", "user_profile", "dynamic_memory",
            {"type": "memory_structure", "description": "User's dynamic memory levels"},
            {"levels": memory_data},
            level=2
        )
    except Exception as e:
        print(f"Error saving dynamic memory to DB: {e}")

class MemoryService:
    """
    Service for extracting and consolidating memories from conversations.
    
    New Flow (2025-12-27):
        Conversation → _extract_facts() → temp_memory (short-term)
                                                ↓
                            consolidation daemon (periodic)
                                                ↓
                                    score → summarize → user.json (long-term)
    
    Old Flow (deprecated):
        Conversation → _extract_facts() → directly to user.json
    """
    
    def __init__(self, model: str = None, session_id: str = None):
        # Use same model config as agent.py - env var or default to qwen2.5:7b
        self.model = model or os.getenv("NOLA_MODEL_NAME", "qwen2.5:7b")
        self.session_id = session_id or "default_session"
        
        # Set session for logging
        if set_session:
            set_session(self.session_id)
        self._ensure_memory_structure()

    def _ensure_memory_structure(self):
        """Ensure dynamic_memory exists in thread database."""
        try:
            data = _get_dynamic_memory_from_db()
            if not data.get("level_1") and not data.get("level_2") and not data.get("level_3"):
                # Initialize empty structure in DB
                _save_dynamic_memory_to_db({
                    "level_1": [],
                    "level_2": [],
                    "level_3": []
                })
                print("Initialized dynamic_memory in thread database")
        except Exception as e:
            print(f"Error initializing memory structure: {e}")

    async def consolidate(self, user_input: str, agent_response: str):
        """
        Analyze the interaction and extract facts to short-term memory.
        Facts are NOT immediately written to user.json - they go to temp_memory
        and await the consolidation daemon to process them.
        """
        try:
            facts = self._extract_facts(user_input, agent_response)
            if facts:
                # NEW: Add to temp_memory instead of directly to user.json
                self._add_to_temp_memory(facts)
                print(f"🧠 Extracted {len(facts)} facts to short-term memory")
                
                # Log the extraction event
                if log_event:
                    log_event(
                        "memory:extract",
                        "memory_service",
                        f"Extracted {len(facts)} facts",
                        fact_count=len(facts),
                        session_id=self.session_id
                    )
        except Exception as e:
            print(f"Error in memory extraction: {e}")
            if log_event:
                from Nola.threads.log import log_error
                log_error("memory_service", e, "consolidate failed")

    def _extract_facts(self, user_input: str, agent_response: str) -> List[str]:
        """
        Use LLM to extract facts from the interaction.
        """
        prompt = f"""
        Analyze the following interaction between a User and an AI Assistant.
        Extract any new, permanent facts about the User (preferences, biographical info, current projects) or the AI's relationship with the User.
        Do not extract trivial details, temporary context, or things the AI said about itself.
        Focus on what the USER revealed.
        
        Interaction:
        User: {user_input}
        AI: {agent_response}
        
        Return ONLY a JSON list of strings. Example: ["User likes Python", "User lives in NYC"].
        If nothing new is found, return [].
        """
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            result = json.loads(response['response'])
            
            # Handle potential different JSON structures from LLM
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and "facts" in result:
                return result["facts"]
            else:
                return []
                
        except Exception as e:
            print(f"LLM extraction failed: {e}")
            return []

    def _add_to_temp_memory(self, facts: List[str]):
        """
        Add extracted facts to short-term memory (temp_memory).
        Facts will be processed by the consolidation daemon later.
        
        Uses LLM-based fact_extractor for clean key generation.
        """
        from Nola.threads.schema import (
            extract_concepts_from_text,
            record_concept_cooccurrence,
        )
        
        # Try new fact extractor first
        try:
            from Nola.services.fact_extractor import extract_and_store_fact
            USE_LLM_EXTRACTOR = True
        except ImportError:
            USE_LLM_EXTRACTOR = False
        
        all_concepts = []
        
        for fact in facts:
            # Extract concepts for linking (always do this)
            concepts = extract_concepts_from_text(fact)
            all_concepts.extend(concepts)
            
            if USE_LLM_EXTRACTOR:
                # NEW: Use LLM-based extraction and storage
                # This handles key generation, L1/L2/L3, and thread routing
                result = extract_and_store_fact(fact, weight=0.4)  # Lower weight for auto-extracted
                
                if result.get("stored"):
                    print(f"📝 Stored: {result['full_path']}")
                    # Log to unified log
                    unified_log(
                        "memory",
                        f"Learned: {fact[:50]}{'...' if len(fact) > 50 else ''}",
                        {"path": result['full_path'], "l1": result['l1'], "concepts": concepts},
                        source="memory_service",
                        session_id=self.session_id,
                        related_key=result['key']
                    )
                else:
                    # Fallback: just add to temp_memory for later processing
                    add_fact(
                        session_id=self.session_id,
                        text=fact,
                        source="conversation",
                        metadata={"concepts": concepts}
                    )
            else:
                # LEGACY: Add to temp_memory only
                add_fact(
                    session_id=self.session_id,
                    text=fact,
                    source="conversation",
                    metadata={"concepts": concepts}
                )
                print(f"📝 Queued fact for consolidation: {fact[:50]}...")
        
        # Record concept co-occurrence for spread activation
        if len(all_concepts) >= 2:
            self._record_concept_links(all_concepts)
    
    def _record_concept_links(self, concepts: List[str]):
        """
        Record concept co-occurrence for spread activation (Hebbian learning).
        
        When concepts appear together, strengthen their links.
        This powers associative memory:
            - "sarah" + "coffee" together → link strengthens
            - Later "coffee" mentioned → sarah.* activates
        """
        try:
            from Nola.threads.schema import record_concept_cooccurrence
            pairs = record_concept_cooccurrence(concepts, learning_rate=0.1)
            if pairs > 0:
                print(f"🔗 Linked {pairs} concept pairs for spread activation")
        except Exception as e:
            print(f"Concept linking skipped: {e}")
    
    def _record_fact_cooccurrence(self, facts: List[str]):
        """
        Record that these facts appeared together (Hebbian learning).
        'Neurons that fire together, wire together.'
        """
        try:
            from Nola.threads.schema import record_cooccurrence
            # Use first 50 chars of each fact as key
            keys = [f[:50].strip() for f in facts if f.strip()]
            pairs = record_cooccurrence(keys)
            if pairs > 0:
                print(f"🔗 Recorded {pairs} co-occurrence pairs")
        except Exception as e:
            print(f"Co-occurrence recording skipped: {e}")
    
    def score_fact(self, fact_text: str, context: dict = None) -> dict:
        """
        Score a fact for importance using LLM analysis.
        
        Scoring dimensions (1-5 scale):
        - permanence: How lasting is this? (5 = core trait, 1 = momentary state)
        - relevance: How relevant to user's goals/work? (5 = central, 1 = tangential)
        - identity: Does this shape who they are? (5 = defining, 1 = incidental)
        
        Args:
            fact_text: The fact to score
            context: Optional context dict (e.g., {"topic": "work", "recent_facts": [...]})
        
        Returns:
            Dict with scores: {permanence, relevance, identity, total, reasoning}
        """
        context_str = ""
        if context:
            context_str = f"\nContext: {json.dumps(context)}"
        
        prompt = f"""Score this fact about a user on three dimensions (1-5 scale):

FACT: "{fact_text}"{context_str}

SCORING GUIDE:
1. PERMANENCE (1-5): Is this a lasting trait or temporary state?
   - 5: Core personality trait, long-term preference, biographical fact
   - 3: Likely to persist but could change (current job, active project)
   - 1: Momentary feeling, temporary context, one-time event

2. RELEVANCE (1-5): How central to the user's goals and daily life?
   - 5: Directly related to their work, main interests, key relationships
   - 3: Moderately relevant, useful background
   - 1: Tangential, rarely applicable

3. IDENTITY (1-5): Does this define who they are?
   - 5: Core to their self-concept, values, or how they want to be known
   - 3: Part of their story but not defining
   - 1: Incidental detail that doesn't shape their identity

Return JSON only:
{{"permanence": <1-5>, "relevance": <1-5>, "identity": <1-5>, "reasoning": "<brief explanation>"}}
"""
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            result = json.loads(response['response'])
            
            # Ensure all required fields exist
            scores = {
                "permanence": result.get("permanence", 3),
                "relevance": result.get("relevance", 3),
                "identity": result.get("identity", 3),
                "reasoning": result.get("reasoning", "No reasoning provided")
            }
            
            # Calculate weighted total (identity weighted higher)
            scores["total"] = (
                scores["permanence"] * 0.3 +
                scores["relevance"] * 0.3 +
                scores["identity"] * 0.4
            )
            
            return scores
            
        except Exception as e:
            print(f"Fact scoring failed: {e}")
            # Return neutral scores on failure
            return {
                "permanence": 3,
                "relevance": 3,
                "identity": 3,
                "total": 3.0,
                "reasoning": f"Scoring failed: {e}"
            }
    
    def score_facts_batch(self, facts: List[str]) -> List[dict]:
        """
        Score multiple facts at once.
        
        Args:
            facts: List of fact strings to score
        
        Returns:
            List of score dicts with fact text included
        """
        results = []
        for fact in facts:
            score = self.score_fact(fact)
            score["text"] = fact
            results.append(score)
        return results
    
    def get_promotion_candidates(self, threshold: float = 3.5) -> List[dict]:
        """
        Get facts from temp_memory that score high enough for promotion.
        
        Args:
            threshold: Minimum total score for promotion (default 3.5)
        
        Returns:
            List of facts with scores that meet threshold
        """
        from Nola.temp_memory import get_all_pending
        
        pending = get_all_pending()
        candidates = []
        
        for fact in pending:
            score = self.score_fact(fact.text)
            score["fact_id"] = fact.id
            score["text"] = fact.text
            score["session_id"] = fact.session_id
            
            if score["total"] >= threshold:
                candidates.append(score)
        
        # Sort by total score descending
        candidates.sort(key=lambda x: x["total"], reverse=True)
        
        return candidates

    def _update_memory(self, facts: List[str]):
        """
        DEPRECATED: Direct writes are no longer the primary path.
        Use _add_to_temp_memory() instead. This method is kept for manual
        consolidation or testing purposes.
        
        Append new facts to thread database.
        New facts go to level_3 first, then consolidated to lower levels.
        """
        import warnings
        warnings.warn(
            "_update_memory() is deprecated. Facts should go to temp_memory first.",
            DeprecationWarning
        )
        
        data = _get_dynamic_memory_from_db()
        
        # Add to level 3 (full detail) and level 2 (moderate)
        # Level 1 is usually kept minimal manually
        
        if not data:
            data = {"level_1": [], "level_2": [], "level_3": []}
            
        # Simple strategy: Append to L2 and L3
        # In a real system, we might want to summarize or deduplicate
        for fact in facts:
            if fact not in data.get("level_3", []):
                data.setdefault("level_3", []).append(fact)
            if fact not in data.get("level_2", []):
                data.setdefault("level_2", []).append(fact)
        
        # Save to thread database
        _save_dynamic_memory_to_db(data)

    def get_temp_memory_stats(self) -> dict:
        """
        Get statistics about facts in short-term memory.
        
        Returns:
            Dict with pending, consolidated, total counts and session count
        """
        return get_stats()
    
    def get_pending_facts(self) -> List[dict]:
        """
        Get all facts pending consolidation.
        Used for debugging or manual review.
        
        Returns:
            List of fact dicts from temp_memory
        """
        from Nola.temp_memory import get_all_pending
        return [f.to_dict() for f in get_all_pending()]
