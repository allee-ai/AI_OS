"""
Linking Core Thread Adapter
===========================

Provides relevance scoring and concept association to Agent.

This thread answers: "What's connected? What matters right now?"
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import os

# Import existing relevance module
try:
    from agent.relevance import score_topic_relevance, embed_text
    HAS_RELEVANCE = True
except ImportError:
    HAS_RELEVANCE = False
    def score_topic_relevance(*args, **kwargs): return {}
    def embed_text(*args, **kwargs): return []

try:
    from agent.threads.base import (
        ThreadInterface,
        HealthReport,
        IntrospectionResult,
        ThreadStatus,
        BaseThreadAdapter,
    )
except ImportError:
    from dataclasses import dataclass, field
    from enum import Enum
    
    class ThreadStatus(Enum):
        OK = "ok"
        DEGRADED = "degraded"
        ERROR = "error"
    
    @dataclass
    class HealthReport:
        status: ThreadStatus
        message: str = ""
        details: Dict[str, Any] = field(default_factory=dict)
        
        @classmethod
        def ok(cls, msg="", **d): return cls(ThreadStatus.OK, msg, d)
        @classmethod
        def error(cls, msg, **d): return cls(ThreadStatus.ERROR, msg, d)
    
    @dataclass
    class IntrospectionResult:
        facts: List[str] = field(default_factory=list)
        state: Dict[str, Any] = field(default_factory=dict)
        context_level: int = 2

    class BaseThreadAdapter:
        pass

class LinkingCoreThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for relevance scoring and concept association.
    
    Responsibilities:
    - Score facts by relevance to current input
    - Maintain concept embeddings
    - Track topic connections
    """
    
    _name = "linking_core"
    _description = "Relevance scoring and concept association"
    
    def __init__(self):
        self._embedding_cache: Dict[str, List[float]] = {}
        self._last_scores: Dict[str, float] = {}
        self._ollama_available: Optional[bool] = None
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def description(self) -> str:
        return self._description
    
    @property
    def purpose(self) -> str:
        return "Relevance scoring and concept association"
    
    def health(self) -> HealthReport:
        """
        Check linking core health.
        
        Linking Core is healthy if the README exists (it documents the algorithms).
        Ollama availability is a bonus for runtime scoring, not required.
        """
        from pathlib import Path
        readme_path = Path(__file__).parent / "README.md"
        
        if readme_path.exists():
            # Check Ollama as optional enhancement
            if self._ollama_available is None:
                self._ollama_available = self._check_ollama()
            
            if self._ollama_available:
                return HealthReport.ok(
                    "Algorithms documented, embeddings available",
                    readme=True,
                    embedding_model="nomic-embed-text",
                    cache_size=len(self._embedding_cache)
                )
            else:
                return HealthReport.ok(
                    "Algorithms documented",
                    readme=True,
                    embedding_model=None
                )
        
        return HealthReport(
            status=ThreadStatus.DEGRADED,
            message="README.md missing - algorithms undocumented",
            details={"readme": False}
        )
    
    def introspect(self, context_level: int = 2, query: str = None) -> IntrospectionResult:
        """Return linking/relevance facts for context assembly."""
        facts = self.get_context(context_level)
        
        # If query provided, add relevant concepts
        relevant_concepts = []
        if query:
            try:
                from .schema import extract_concepts_from_text, spread_activate
                query_concepts = extract_concepts_from_text(query)
                if query_concepts:
                    activated = spread_activate(query_concepts, activation_threshold=0.1, max_hops=1, limit=10)
                    relevant_concepts = [a.get('concept', '') for a in activated]
            except Exception:
                pass
        
        return IntrospectionResult(
            facts=facts,
            state=self._get_state_summary(),
            context_level=context_level,
            relevant_concepts=relevant_concepts,
        )
    
    def get_context(self, level: int) -> List[str]:
        """
        Get relevance-related facts.
        
        Note: This thread doesn't generate facts about content,
        it SCORES facts from other threads. Its context output
        is about the scoring itself.
        
        Level 1: No relevance facts (scoring is implicit)
        Level 2: Summary of relevance state
        Level 3: Detailed scoring breakdown
        """
        facts = []
        
        if level >= 2:
            if self._last_scores:
                top_topics = sorted(
                    self._last_scores.items(), 
                    key=lambda x: x[1], 
                    reverse=True
                )[:3]
                if top_topics:
                    topics_str = ", ".join(f"{t[0]} ({t[1]:.2f})" for t in top_topics)
                    facts.append(f"Top relevant topics: {topics_str}")
        
        if level >= 3:
            facts.append(f"Embedding cache size: {len(self._embedding_cache)} entries")
            if self._ollama_available:
                facts.append("Embedding model: nomic-embed-text (active)")
        
        return facts
    
    def score_facts(
        self, 
        input_text: str, 
        facts: List[str],
        top_k: int = 10,
        context_keys: List[str] = None
    ) -> List[Tuple[str, float]]:
        """
        Score facts by relevance to input text.
        
        Args:
            input_text: The user's message or query
            facts: List of facts to score
            top_k: Number of top facts to return
            context_keys: Optional list of keys from current context
                         (used for co-occurrence boosting)
        
        Returns:
            List of (fact, score) tuples sorted by score descending
        """
        if not facts:
            return []
        
        if not self._ollama_available:
            # Fallback: keyword matching
            return self._keyword_score(input_text, facts, top_k)
        
        # Embed input
        input_emb = self._embed(input_text)
        if not input_emb:
            return self._keyword_score(input_text, facts, top_k)
        
        # Score each fact
        scored = []
        for fact in facts:
            fact_emb = self._embed(fact)
            if fact_emb:
                base_score = self._cosine_similarity(input_emb, fact_emb)
                
                # Apply co-occurrence boost (Hebbian learning)
                cooccur_boost = self._get_cooccurrence_boost(fact, context_keys)
                final_score = base_score * (1 + cooccur_boost)
                
                scored.append((fact, final_score))
            else:
                scored.append((fact, 0.0))
        
        # Sort and return top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    
    def _get_cooccurrence_boost(self, fact: str, context_keys: List[str] = None) -> float:
        """
        Get co-occurrence boost for a fact based on context.
        
        Returns 0.0 - 0.3 boost based on how often this fact
        has appeared with current context in past conversations.
        """
        if not context_keys:
            return 0.0
        
        try:
            from agent.threads.linking_core.schema import get_cooccurrence_score
            # Use first 50 chars as key (matching recording)
            fact_key = fact[:50].strip()
            return get_cooccurrence_score(fact_key, context_keys)
        except Exception:
            return 0.0
    
    def activate_memories(
        self,
        input_text: str,
        max_hops: int = 1,
        activation_threshold: float = 0.1,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Use spread activation to find relevant memories.
        
        This is the key method for associative memory:
        1. Extract concepts from input ("Sarah mentioned coffee")
        2. Spread activation finds linked concepts (sarah → sarah.*, coffee → sarah)
        3. Retrieve facts with matching keys
        
        Args:
            input_text: User's message
            max_hops: How many hops in the concept graph
            activation_threshold: Minimum activation to keep
            limit: Max facts to return
        
        Returns:
            List of {fact_key, fact_text, final_score, combined_score, activated_by}
        """
        try:
            from agent.threads.linking_core.schema import (
                extract_concepts_from_text,
                spread_activate,
                get_keys_for_concepts,
            )
            from agent.threads.log import log_event
            
            # Step 1: Extract concepts from input
            concepts = extract_concepts_from_text(input_text)
            if not concepts:
                return []
            
            # Step 2: Spread activation to find related concepts
            activated = spread_activate(
                concepts, 
                activation_threshold=activation_threshold,
                max_hops=max_hops,
                limit=50
            )
            
            # Include original concepts with full activation
            all_activated = [{"concept": c, "activation": 1.0, "path": [c]} for c in concepts]
            all_activated.extend(activated)
            
            # Step 3: Get facts for activated concepts
            facts = get_keys_for_concepts(all_activated, limit=limit)
            
            # Log memory retrieval
            if facts:
                log_event(
                    "memory",
                    f"Retrieved {len(facts)} memories for: {', '.join(concepts[:3])}",
                    {
                        "query_concepts": concepts,
                        "facts_retrieved": len(facts),
                        "top_keys": [f.get("fact_key", "") for f in facts[:3]]
                    }
                )
            
            return facts
            
        except Exception as e:
            print(f"Spread activation failed: {e}")
            return []
    
    def get_associative_context(
        self, 
        input_text: str,
        existing_facts: List[str] = None,
        top_k: int = 15
    ) -> List[str]:
        """
        Get context using both embedding similarity AND spread activation.
        
        This combines:
        1. Traditional embedding-based relevance
        2. Spread activation from concept links
        
        Args:
            input_text: User's message
            existing_facts: Facts already collected from threads
            top_k: Number of facts to return
        
        Returns:
            Combined, de-duplicated list of relevant facts
        """
        results = []
        seen_facts = set()
        
        # 1. Spread activation memories (associative)
        activated = self.activate_memories(input_text, limit=top_k)
        for item in activated:
            fact_text = item.get("fact_text", "")
            if fact_text and fact_text not in seen_facts:
                seen_facts.add(fact_text)
                results.append({
                    "text": fact_text,
                    "score": item.get("combined_score", 0.5),
                    "source": "spread_activation",
                    "key": item.get("fact_key", "")
                })
        
        # 2. Embedding-based scoring of existing facts
        if existing_facts:
            # Extract concept keys for co-occurrence boost
            try:
                from agent.threads.linking_core.schema import extract_concepts_from_text
                context_keys = extract_concepts_from_text(input_text)
            except:
                context_keys = []
            
            scored = self.score_facts(
                input_text, 
                existing_facts,
                top_k=top_k,
                context_keys=context_keys
            )
            
            for fact, score in scored:
                if fact not in seen_facts:
                    seen_facts.add(fact)
                    results.append({
                        "text": fact,
                        "score": score,
                        "source": "embedding",
                        "key": ""
                    })
        
        # Sort by score and return texts
        results.sort(key=lambda x: x["score"], reverse=True)
        return [r["text"] for r in results[:top_k]]
    
    def score_threads(self, stimuli: str) -> Dict[str, float]:
        """
        Score all threads for relevance to stimuli.
        
        Returns scores (0-10 scale) for three-tier context gating:
          - 0-3.5: Tier 1 (metadata only)
          - 3.5-7: Tier 2 (profile metadata)
          - 7-10: Tier 3 (full facts with L1/L2/L3)
        
        Uses embedding similarity when thread summaries are available,
        falls back to keyword scoring otherwise.
        
        Called by reflex thread or subconscious when needed.
        Does NOT decide when to run - that's reflex's job.
        
        Args:
            stimuli: Input text to score against
        
        Returns:
            Dict mapping thread_name -> relevance_score (0-10)
        """
        # Try embedding-based scoring first (populated during consolidation)
        try:
            from agent.threads.linking_core.scoring import score_threads_by_embedding
            emb_scores = score_threads_by_embedding(stimuli)
            if emb_scores:
                # Merge with keyword scores (70% embedding, 30% keyword)
                keyword_scores = self._keyword_score_threads(stimuli)
                scores = {}
                for thread in set(emb_scores.keys()) | set(keyword_scores.keys()):
                    e = emb_scores.get(thread, 5.0)
                    k = keyword_scores.get(thread, 5.0)
                    scores[thread] = 0.7 * e + 0.3 * k
                self._last_scores = scores
                return scores
        except Exception:
            pass
        
        # Fall back to pure keyword scoring
        scores = self._keyword_score_threads(stimuli)
        self._last_scores = scores
        return scores
    
    def _keyword_score_threads(self, stimuli: str) -> Dict[str, float]:
        """Keyword-based thread scoring (fallback)."""
        stimuli_lower = stimuli.lower()
        scores = {}
        
        # Get all threads
        try:
            from agent.threads import get_all_threads
            threads = get_all_threads()
        except:
            return {}
        
        # Score each thread based on keywords
        for thread in threads:
            thread_name = getattr(thread, '_name', str(thread))
            
            if thread_name == 'identity':
                # Identity: Always medium-high (core profile context)
                base = 7.0
                if any(kw in stimuli_lower for kw in ['who am', 'who are you', 'tell me about', 'yourself']):
                    scores[thread_name] = 9.0
                elif any(kw in stimuli_lower for kw in ['who', 'me', 'my ', 'i am', 'you are']):
                    scores[thread_name] = 8.0
                else:
                    scores[thread_name] = base
            
            elif thread_name == 'log':
                # Log: Temporal/debugging keywords
                if any(kw in stimuli_lower for kw in ['when', 'recent', 'earlier', 'yesterday', 'last', 'history']):
                    scores[thread_name] = 9.0
                elif any(kw in stimuli_lower for kw in ['debug', 'error', 'problem', 'what happened']):
                    scores[thread_name] = 8.0
                elif any(kw in stimuli_lower for kw in ['time', 'today', 'now']):
                    scores[thread_name] = 7.0
                else:
                    scores[thread_name] = 5.0
            
            elif thread_name == 'philosophy':
                # Philosophy: Values/reasoning keywords
                if any(kw in stimuli_lower for kw in ['why should', 'believe', 'value', 'ethics', 'principle']):
                    scores[thread_name] = 9.0
                elif any(kw in stimuli_lower for kw in ['why', 'think', 'feel', 'opinion']):
                    scores[thread_name] = 7.0
                else:
                    scores[thread_name] = 3.0
            
            elif thread_name == 'form':
                # Form: Action/tool keywords
                if any(kw in stimuli_lower for kw in ['create', 'make', 'build', 'write', 'run', 'execute']):
                    scores[thread_name] = 8.0
                elif any(kw in stimuli_lower for kw in ['how to', 'can you', 'help me']):
                    scores[thread_name] = 7.0
                else:
                    scores[thread_name] = 4.0
            
            elif thread_name == 'reflex':
                # Reflex: Pattern/habit keywords
                if any(kw in stimuli_lower for kw in ['usually', 'always', 'often', 'pattern', 'habit']):
                    scores[thread_name] = 7.0
                else:
                    scores[thread_name] = 3.0
            
            elif thread_name == 'linking_core':
                # Linking core: Doesn't produce facts, just metadata
                scores[thread_name] = 2.0
            
            else:
                scores[thread_name] = 5.0
        
        self._last_scores = scores
        return scores
    
    def score_relevance(
        self,
        stimuli: str,
        facts: List[str],
        context_keys: List[str] = None,
        use_embeddings: bool = True,
        use_cooccurrence: bool = True,
        use_spread_activation: bool = True
    ) -> List[Tuple[str, float]]:
        """
        Comprehensive relevance scoring using multiple techniques.
        
        This is the CORE SCORING FUNCTION for consolidation, context assembly,
        and any time we need to rank facts by relevance.
        
        Combines:
        1. Embedding similarity (semantic matching)
        2. Co-occurrence scoring (concepts appearing together)
        3. Spread activation (concept graph traversal)
        4. Keyword matching (fallback)
        
        Used by:
        - Consolidation: Score facts for compression
        - Context assembly: Rank facts for inclusion
        - Memory retrieval: Find relevant memories
        
        Args:
            stimuli: Input text to score against
            facts: List of fact texts to score
            context_keys: Optional list of known concept keys for co-occurrence boost
            use_embeddings: Use embedding similarity (requires Ollama)
            use_cooccurrence: Boost facts with co-occurring concepts
            use_spread_activation: Use concept graph for activation spreading
        
        Returns:
            List of (fact, score) tuples sorted by score descending
        """
        if not facts:
            return []
        
        # Extract concepts from stimuli for mapping
        try:
            from agent.threads.linking_core.schema import extract_concepts_from_text, get_cooccurrence_score
            input_concepts = extract_concepts_from_text(stimuli)
        except:
            input_concepts = []
            use_cooccurrence = False
            use_spread_activation = False
        
        scored = []
        
        for fact in facts:
            total_score = 0.0
            components = {}
            
            # 1. Embedding similarity (if available)
            if use_embeddings and HAS_RELEVANCE:
                try:
                    input_emb = self._embed(stimuli)
                    fact_emb = self._embed(fact)
                    if input_emb and fact_emb:
                        sim = self._cosine_similarity(input_emb, fact_emb)
                        components['embedding'] = sim
                        total_score += sim * 0.5  # 50% weight
                except:
                    pass
            
            # 2. Co-occurrence scoring (concepts that appear together)
            if use_cooccurrence and context_keys:
                try:
                    # Extract concepts from this fact
                    fact_concepts = extract_concepts_from_text(fact)
                    if fact_concepts and input_concepts:
                        # Average co-occurrence score across fact concepts
                        cooccur_scores = []
                        for fact_concept in fact_concepts[:3]:  # Top 3 concepts
                            score = get_cooccurrence_score(fact_concept, input_concepts)
                            if score > 0:
                                cooccur_scores.append(score)
                        
                        if cooccur_scores:
                            avg_cooccur = sum(cooccur_scores) / len(cooccur_scores)
                            components['cooccurrence'] = avg_cooccur
                            total_score += avg_cooccur * 0.3  # 30% weight
                except:
                    pass
            
            # 3. Spread activation (concept graph)
            if use_spread_activation and input_concepts:
                try:
                    from agent.threads.linking_core.schema import spread_activate
                    # Activate concepts from input
                    activated = spread_activate(input_concepts, activation_threshold=0.1, max_hops=1, limit=20)
                    activated_concepts = {a['concept']: a['activation'] for a in activated}
                    
                    # Check if fact concepts are in activated set
                    fact_concepts = extract_concepts_from_text(fact)
                    activation_scores = [activated_concepts.get(c, 0) for c in fact_concepts]
                    if activation_scores:
                        max_activation = max(activation_scores)
                        components['activation'] = max_activation
                        total_score += max_activation * 0.2  # 20% weight
                except:
                    pass
            
            # 4. Keyword matching (fallback/always-on)
            input_words = set(stimuli.lower().split())
            fact_words = set(fact.lower().split())
            overlap = len(input_words & fact_words)
            keyword_score = overlap / max(len(input_words), 1)
            components['keyword'] = keyword_score
            
            # If no other methods worked, keyword is 100% weight
            if total_score == 0:
                total_score = keyword_score
            else:
                total_score += keyword_score * 0.1  # 10% weight as tie-breaker
            
            scored.append((fact, total_score, components))
        
        # Sort by total score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Return (fact, score) without components for cleaner API
        return [(fact, score) for fact, score, _ in scored]
    
    def score_topics(self, input_text: str, topics: Dict[str, Any]) -> Dict[str, float]:
        """
        Score topic keys by relevance to input.
        
        This is used by identity adapter to rank which identity
        sections are most relevant to the current conversation.
        """
        if HAS_RELEVANCE:
            try:
                scores = score_topic_relevance(input_text, topics)
                self._last_scores = scores
                return scores
            except Exception:
                pass
        
        # Fallback: uniform scores
        return {k: 0.5 for k in topics.keys()}
    
    def get_metadata(self) -> Dict[str, Any]:
        """Return thread metadata for subconscious."""
        return {
            "name": self.name,
            "purpose": self.purpose,
            "status": "healthy" if self._ollama_available else "degraded",
            "last_sync": datetime.now(timezone.utc).isoformat(),
            "module_count": 3,
            "details": {
                "has_relevance": HAS_RELEVANCE,
                "ollama_available": self._ollama_available,
                "cache_size": len(self._embedding_cache),
                "modules": ["relevance", "embeddings", "topic_graph"]
            }
        }
    
    def _embed(self, text: str) -> Optional[List[float]]:
        """Get embedding for text, with caching."""
        if text in self._embedding_cache:
            return self._embedding_cache[text]
        
        if HAS_RELEVANCE:
            try:
                embedding = embed_text(text)
                if embedding:
                    self._embedding_cache[text] = embedding
                    return embedding
            except Exception:
                pass
        
        return None
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
    
    def _keyword_score(
        self, 
        input_text: str, 
        facts: List[str], 
        top_k: int
    ) -> List[Tuple[str, float]]:
        """Fallback keyword-based scoring."""
        input_words = set(input_text.lower().split())
        
        scored = []
        for fact in facts:
            fact_words = set(fact.lower().split())
            overlap = len(input_words & fact_words)
            score = overlap / max(len(input_words), 1)
            scored.append((fact, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
    
    def _check_ollama(self) -> bool:
        """Check if Ollama embedding model is available."""
        try:
            import ollama
            # Try to embed a test string
            response = ollama.embeddings(model="nomic-embed-text", prompt="test")
            return "embedding" in response
        except Exception:
            return False
    
    def _get_state_summary(self) -> Dict[str, Any]:
        """Get raw state for debugging."""
        return {
            "has_relevance": HAS_RELEVANCE,
            "ollama_available": self._ollama_available,
            "cache_size": len(self._embedding_cache),
            "last_scores": self._last_scores
        }


__all__ = ["LinkingCoreThreadAdapter"]
