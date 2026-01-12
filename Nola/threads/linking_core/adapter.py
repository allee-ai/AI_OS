"""
Linking Core Thread Adapter
===========================

Provides relevance scoring and concept association to Nola.

This thread answers: "What's connected? What matters right now?"
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
import os

# Import existing relevance module
try:
    from Nola.relevance import score_topic_relevance, embed_text
    HAS_RELEVANCE = True
except ImportError:
    HAS_RELEVANCE = False
    def score_topic_relevance(*args, **kwargs): return {}
    def embed_text(*args, **kwargs): return []

# Training data logging (append-only learning)
try:
    from Nola.training import log_linking_decision
    HAS_TRAINING_LOGGER = True
except ImportError:
    HAS_TRAINING_LOGGER = False
    def log_linking_decision(*args, **kwargs): return False

try:
    from Nola.threads.base import (
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
    
    def introspect(self, context_level: int = 2) -> IntrospectionResult:
        """Return linking/relevance facts for context assembly."""
        facts = self.get_context(context_level)
        
        return IntrospectionResult(
            facts=facts,
            state=self._get_state_summary(),
            context_level=context_level
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
            from Nola.threads.schema import get_cooccurrence_score
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
            from Nola.threads.schema import (
                extract_concepts_from_text,
                spread_activate,
                get_keys_for_concepts,
                log_event
            )
            
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
                
                # Log confident spread activation for training (append-only learning)
                if HAS_TRAINING_LOGGER and activated:
                    top_activation = activated[0]["activation"] if activated else 0
                    if top_activation >= 0.5:  # Only log confident activations
                        activated_concepts = [a["concept"] for a in activated[:5]]
                        log_linking_decision(
                            input_text=input_text,
                            output_text=f"Activated: {', '.join(activated_concepts)}",
                            decision_type="activation",
                            confidence=top_activation,
                            source_concepts=concepts,
                            activated_count=len(activated),
                            facts_retrieved=len(facts)
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
                from Nola.threads.schema import extract_concepts_from_text
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
