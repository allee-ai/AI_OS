"""
Consolidation Loop
==================
Scores temp_memory facts and promotes high-scoring ones to long-term memory.
"""

import re
from typing import Dict, Any, Optional

from .base import BackgroundLoop, LoopConfig


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
    AUTO_APPROVE_THRESHOLD = 0.7
    
    # Duplicate similarity threshold
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
        self._update_thread_summaries()
        self._summarize_unsummarized_conversations()
        self._score_and_triage_pending()
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

    def _summarize_unsummarized_conversations(self) -> None:
        """Batch-summarize conversations that lack a summary."""
        try:
            from workspace.summarizer import batch_summarize_conversations
            count = batch_summarize_conversations(limit=5)
            if count > 0:
                import sys
                print(f"[Consolidation] Summarized {count} conversations", file=sys.stderr)
        except Exception as e:
            import sys
            print(f"[Consolidation] Convo summarization failed: {e}", file=sys.stderr)

    def _score_and_triage_pending(self) -> None:
        """Score pending facts using LinkingCore's scoring pipeline."""
        try:
            from agent.subconscious.temp_memory import (
                get_all_pending, update_fact_status
            )
            from agent.threads.identity.schema import pull_profile_facts
            
            pending = get_all_pending()
            if not pending:
                return
            
            existing_facts = pull_profile_facts(limit=500)
            existing_texts = [
                f"{f.get('key', '')} {f.get('l1_value', '')} {f.get('l2_value', '')} {f.get('l3_value', '')}"
                for f in existing_facts
            ]
            existing_texts = [t for t in existing_texts if t.strip()]
            
            linking_core = self._get_linking_core()
            
            for fact in pending:
                if fact.status != 'pending':
                    continue
                
                try:
                    confidence = self._calculate_confidence(
                        fact.text,
                        existing_texts,
                        linking_core
                    )
                    
                    if confidence < 0:
                        new_status = 'rejected'
                    elif confidence >= self.AUTO_APPROVE_THRESHOLD:
                        new_status = 'approved'
                    else:
                        new_status = 'pending_review'
                    
                    update_fact_status(fact.id, new_status, abs(confidence))
                    
                except Exception as e:
                    import sys
                    print(f"Error scoring fact {fact.id}: {e}", file=sys.stderr)
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
        
        Returns:
            0.0-1.0 for valid facts (higher = more confident)
            -1.0 for duplicates
        """
        if not fact_text or not fact_text.strip():
            return 0.0
        
        # Duplicate detection via LinkingCore
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
                        return -1.0
            except Exception:
                pass
        
        # Quality scoring
        confidence = 0.5
        
        word_count = len(fact_text.split())
        if word_count >= 3:
            confidence += 0.1
        if word_count >= 5:
            confidence += 0.1
        
        if re.search(r'\b[A-Z][a-z]+\b', fact_text):
            confidence += 0.1
        if re.search(r'\d+', fact_text):
            confidence += 0.05
        
        # Boost from linking core
        if linking_core and existing_texts:
            try:
                scored = linking_core.score_relevance(
                    fact_text, existing_texts[:50],
                    use_embeddings=True,
                    use_cooccurrence=True,
                    use_spread_activation=True
                )
                if scored:
                    non_dup = [(f, s) for f, s in scored if s < self.DUPLICATE_THRESHOLD]
                    if non_dup:
                        avg_relevance = sum(s for _, s in non_dup[:10]) / min(len(non_dup), 10)
                        confidence += min(0.15, avg_relevance * 0.3)
            except Exception:
                pass
        
        return min(1.0, max(0.0, confidence))
    
    def _promote_approved_facts(self) -> None:
        """Promote approved facts to long-term memory."""
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
            
            # Ensure default user profile exists
            try:
                profiles = get_profiles()
                user_exists = any(p.get('profile_id') == 'primary_user' for p in profiles)
                if not user_exists:
                    create_profile("primary_user", "human", "User")
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
                    fact_destination = self._classify_fact_destination(fact.text)
                    
                    if fact.hier_key:
                        key = fact.hier_key.rsplit(".", 1)[-1]
                    else:
                        key = self._generate_key(fact.text, fact_destination)
                    
                    if fact_destination == "philosophy":
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
                    
                    mark_consolidated(fact.id)

                    try:
                        from agent.threads.linking_core.schema import index_key_in_concept_graph
                        index_key_in_concept_graph(key, fact.text)
                    except Exception:
                        pass

                except Exception as e:
                    import sys
                    print(f"Error promoting fact {fact.id}: {e}", file=sys.stderr)
            
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
        """Classify whether a fact belongs in identity or philosophy thread."""
        linking_core = self._get_linking_core()
        
        if not linking_core:
            return "identity"
        
        try:
            scores = linking_core.score_threads(fact_text)
            identity_score = scores.get('identity', 5.0)
            philosophy_score = scores.get('philosophy', 5.0)
            
            if philosophy_score > identity_score + 1.0:
                return "philosophy"
            return "identity"
        except Exception:
            return "identity"
    
    def _generate_key(self, fact_text: str, destination: str = "identity") -> str:
        """Generate a key from fact text."""
        text_lower = fact_text.lower()
        
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
        
        try:
            from agent.threads.linking_core.schema import extract_concepts_from_text
            concepts = extract_concepts_from_text(fact_text)[:3]
            if concepts:
                detail = "_".join(concepts)
            else:
                raise ValueError("no concepts")
        except Exception:
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
        
        return detail
    
    def _update_thread_summaries(self) -> None:
        """Generate summaries for each thread and cache embeddings."""
        try:
            from agent.threads.linking_core.scoring import set_thread_summary
            from agent.threads import get_all_threads
            
            for thread in get_all_threads():
                thread_name = getattr(thread, '_name', str(thread))
                
                if thread_name == 'linking_core':
                    continue
                
                try:
                    if hasattr(thread, 'introspect'):
                        result = thread.introspect(context_level=2, query="", threshold=5.0)
                        if result and hasattr(result, 'facts') and result.facts:
                            summary_facts = result.facts[:10]
                            summary = ' '.join(summary_facts)
                            
                            if summary:
                                set_thread_summary(thread_name, summary)
                except Exception as e:
                    import sys
                    print(f"Error getting introspect for {thread_name}: {e}", file=sys.stderr)
                    continue
            
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
