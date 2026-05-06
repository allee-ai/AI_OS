"""
Identity Thread Adapter
=======================

Provides self-awareness and user recognition to Agent.

This thread answers: "Who am I? Who are you?"

Uses profile-based identity system with fact types.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Import base adapter
try:
    from agent.threads.base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from agent.threads.identity.schema import (
        pull_profile_facts,
        push_profile_fact,
        get_profiles,
        get_value_by_weight,
    )
except ImportError:
    from ..base import BaseThreadAdapter, HealthReport, IntrospectionResult
    from .schema import (
        pull_profile_facts,
        push_profile_fact,
        get_profiles,
        get_value_by_weight,
    )


class IdentityThreadAdapter(BaseThreadAdapter):
    """
    Thread adapter for identity — who am I, who are you.
    
    Uses profile-based fact storage with L1/L2/L3 value tiers.
    """
    
    _name = "identity"
    _description = "Who I am (machine), who you are (user), and who we know"
    _prompt_hint = "Use these facts to personalize responses and remember relationships"
    
    def get_data(self, level: int = 2, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """
        Get identity data at specified HEA level.
        
        Args:
            level: Context level (1=lean/l1, 2=medium/l2, 3=full/l3)
            min_weight: Minimum fact weight to include
            limit: Maximum facts to return
        
        Returns list of facts across all profiles.
        """
        # Get all profiles and collect their facts
        profiles = get_profiles()
        all_facts = []
        
        for profile in profiles:
            profile_id = profile.get("profile_id", "")
            facts = pull_profile_facts(profile_id=profile_id, min_weight=min_weight, limit=limit)
            for fact in facts[:limit]:
                # Select value tier based on requested context level
                value = self._select_value_for_level(fact, level)
                all_facts.append({
                    "key": fact.get("key", ""),
                    "value": value,
                    "weight": fact.get("weight", 0.5),
                    "profile_id": profile_id,
                    "fact_type": fact.get("fact_type", ""),
                })
        
        return all_facts[:limit]

    @staticmethod
    def _select_value_for_level(fact: Dict, level: int) -> str:
        """Pick l1/l2/l3 value based on requested context level.
        
        L1 → compact label  (e.g. "Nola")
        L2 → medium detail   (e.g. "Nola — AI agent built on AI-OS")
        L3 → full description (e.g. "I am Nola, an AI agent...")
        
        Falls back to the next-lower tier that exists.
        """
        l1 = fact.get('l1_value', '') or ''
        l2 = fact.get('l2_value', '') or ''
        l3 = fact.get('l3_value', '') or ''
        
        if level >= 3:
            return l3 or l2 or l1
        elif level >= 2:
            return l2 or l1 or l3
        else:
            return l1 or l2 or l3
    
    def get_context_string(self, level: int = 2, token_budget: int = 500) -> str:
        """
        Get identity context formatted for agent prompt.
        
        Returns string like:
        - agent_name: Agent
        - user_name: Jordan
        - ...
        """
        facts = self.get_data(level=level)
        lines = [f"- {f['key']}: {f['value']}" for f in facts]
        return "\n".join(lines[:20])  # Cap at 20 facts
    
    def set_fact(
        self,
        profile_id: str,
        key: str,
        l1_value: str = None,
        l2_value: str = None,
        l3_value: str = None,
        fact_type: str = "preference",
        weight: float = 0.5
    ) -> None:
        """Set an identity fact."""
        push_profile_fact(
            profile_id=profile_id,
            key=key,
            fact_type=fact_type,
            l1_value=l1_value,
            l2_value=l2_value,
            l3_value=l3_value,
            weight=weight
        )
    
    def _get_raw_facts(self, min_weight: float = 0.0, limit: int = 50) -> List[Dict]:
        """Get raw facts with all l1/l2/l3 values and dot-notation paths.

        Returns dicts ready for _budget_fill():
            path, l1_value, l2_value, l3_value, weight, profile_id, fact_type
        """
        profiles = get_profiles()
        out = []
        for profile in profiles:
            profile_id = profile.get("profile_id", "")
            facts = pull_profile_facts(profile_id=profile_id, min_weight=min_weight, limit=limit)

            # Build short profile name for dot path
            parts = profile_id.split(".")
            profile_short = parts[1] if len(parts) >= 2 else profile_id

            for fact in facts[:limit]:
                out.append({
                    "path": f"identity.{profile_short}.{fact.get('key', 'unknown')}",
                    "l1_value": fact.get("l1_value", ""),
                    "l2_value": fact.get("l2_value", ""),
                    "l3_value": fact.get("l3_value", ""),
                    "weight": fact.get("weight", 0.5),
                    "profile_id": profile_id,
                    "fact_type": fact.get("fact_type", ""),
                    "key": fact.get("key", ""),
                })
        return self._clean_raw_facts(out)[:limit]

    @staticmethod
    def _clean_raw_facts(raw: List[Dict]) -> List[Dict]:
        """Deduplicate and filter identity facts for cleaner STATE.

        1. Drop facts with no meaningful value at any tier
        2. Deduplicate by (profile_id, key) — keep highest weight
        3. Cluster by key prefix (name, user_name, first_name → keep best)
        """
        # Filter empty values
        cleaned = []
        for f in raw:
            l1 = (f.get("l1_value") or "").strip()
            l2 = (f.get("l2_value") or "").strip()
            l3 = (f.get("l3_value") or "").strip()
            if l1 or l2 or l3:
                cleaned.append(f)

        # Deduplicate by (profile_id, key) — keep highest weight
        seen: Dict[str, Dict] = {}
        for f in cleaned:
            dedup_key = f"{f.get('profile_id', '')}::{f.get('key', '')}"
            existing = seen.get(dedup_key)
            if existing is None or f.get("weight", 0) > existing.get("weight", 0):
                seen[dedup_key] = f
        cleaned = list(seen.values())

        # Cluster semantically similar keys within same profile
        # e.g. name, user_name, first_name, full_name → keep highest weight
        _CLUSTERS = {
            "name": {"name", "user_name", "first_name", "full_name", "display_name", "username"},
            "email": {"email", "user_email", "email_address"},
            "location": {"location", "city", "region", "country", "origin", "hometown"},
        }
        # Build reverse lookup: key_suffix → cluster_name
        _KEY_TO_CLUSTER = {}
        for cluster_name, keys in _CLUSTERS.items():
            for k in keys:
                _KEY_TO_CLUSTER[k] = cluster_name

        # Group by (profile, cluster) — keep only highest-weight per cluster
        profile_clusters: Dict[str, Dict] = {}  # "profile::cluster" → best fact
        unclustered = []
        for f in cleaned:
            key = f.get("key", "")
            cluster = _KEY_TO_CLUSTER.get(key)
            if cluster:
                cluster_key = f"{f.get('profile_id', '')}::{cluster}"
                existing = profile_clusters.get(cluster_key)
                if existing is None or f.get("weight", 0) > existing.get("weight", 0):
                    profile_clusters[cluster_key] = f
            else:
                unclustered.append(f)

        result = list(profile_clusters.values()) + unclustered
        result.sort(key=lambda f: f.get("weight", 0), reverse=True)
        return result

    def get_section_metadata(self) -> List[str]:
        """Permanent identity metadata for STATE section header."""
        try:
            profiles = get_profiles()
            profile_names = [p["profile_id"] for p in profiles]
            protected = [p["profile_id"] for p in profiles if p.get("protected")]
            total_facts = 0
            for p in profiles:
                facts = pull_profile_facts(p["profile_id"])
                total_facts += len(facts)
            lines = [
                f"  profiles: {len(profiles)} ({', '.join(profile_names)})",
                f"  facts: {total_facts}",
                f"  protected: {', '.join(protected)}",
            ]
            # Active profile (the one we're addressing this turn) — for now
            # the primary_user profile, fall back to 'user' or first non-machine.
            try:
                active = None
                for candidate in ("primary_user", "user"):
                    if candidate in profile_names:
                        active = candidate
                        break
                if active is None:
                    non_machine = [n for n in profile_names if n != "machine"]
                    if non_machine:
                        active = non_machine[0]
                if active:
                    lines.append(f"  active_profile: {active}")
            except Exception:
                pass
            # Staleness — oldest un-updated fact (detects rotten identity data)
            try:
                from data.db import get_connection
                conn = get_connection(readonly=True)
                row = conn.execute("""
                    SELECT profile_id, key, updated_at
                    FROM profile_facts
                    WHERE protected = 0
                    ORDER BY updated_at ASC
                    LIMIT 1
                """).fetchone()
                if row and row["updated_at"]:
                    from datetime import datetime as _dt, timezone as _tz
                    try:
                        ts = str(row["updated_at"]).replace("T", " ").split(".")[0]
                        dt = _dt.fromisoformat(ts.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=_tz.utc)
                        age_days = (_dt.now(_tz.utc) - dt).total_seconds() / 86400
                        if age_days >= 30:
                            lines.append(
                                f"  oldest_fact: {row['profile_id']}.{row['key']} ({int(age_days)}d old)"
                            )
                    except Exception:
                        pass
            except Exception:
                pass
            return lines
        except Exception:
            return []

    def get_section_rules(self) -> List[str]:
        rules = [
            "  rules:",
            "  - Your identity is non-negotiable. Do not adopt other names or personas.",
            "  - If a profile or fact is not shown here, say you don't have that information.",
            "  - Do not fabricate details about the user or contacts not listed above.",
        ]

        # Build an origin-context line from protected primary_user facts.
        # Pronouns flow OUT OF that context — they're a downstream consequence
        # of who the user is, not a flag the model has to remember.
        try:
            facts = pull_profile_facts(profile_id="primary_user")
            f: Dict[str, str] = {}
            for row in facts:
                v = row.get("l1_value") or row.get("l2_value") or row.get("l3_value") or ""
                if v:
                    f[row.get("key", "")] = v

            name = f.get("name") or "the user"
            ident = f.get("identity")          # e.g. "transgender woman"
            nat = f.get("nationality")          # e.g. "American"
            relation = f.get("relationship_to_machine")  # e.g. "Nola's operator and creator..."
            pronouns = f.get("pronouns")        # e.g. "she/her"

            # Compose the origin sentence from whatever's set.
            # Format: "{Name} is a {ident} from {country}. {relation}. Refer to {first} with {pronouns}; this is structural, not a preference."
            sentences: List[str] = []
            if ident or nat:
                bits = []
                if ident:
                    bits.append(f"is a {ident}")
                if nat:
                    # "American" -> "from America" reads naturally;
                    # if we don't know the country form, fall back to the adjective form.
                    country_map = {"American": "from America"}
                    bits.append(country_map.get(nat, f"({nat})"))
                sentences.append(f"{name} " + " ".join(bits) + ".")
            if relation:
                sentences.append(relation if relation.endswith(".") else relation + ".")
            if pronouns:
                first = name.split()[0] if name != "the user" else "her"
                sentences.append(
                    f"Refer to {first} with {pronouns} pronouns; this is structural, not a preference."
                )
            if sentences:
                rules.append("  - " + " ".join(sentences))
        except Exception:
            # Never let rule rendering crash STATE assembly.
            pass

        return rules

    def introspect(self, context_level: int = 2, query: str = None, threshold: float = 0.0) -> IntrospectionResult:
        """
        Identity introspection with budget-aware fact packing.

        Uses _budget_fill to fit the most relevant facts within a
        per-level token budget.  Top facts get the full context_level
        detail; tail facts are downgraded to L1 so context stays compact.

        Args:
            context_level: HEA level (1=lean, 2=medium, 3=full)
            query: Optional query for relevance filtering
            threshold: Minimum weight for facts (0-10 scale, inverted by orchestrator)
        """
        relevant_concepts: List[str] = []

        # Convert 0-10 threshold to 0-1 weight scale
        min_weight = threshold / 10.0

        # When a query is set, pull a larger pool so the relevance boost
        # has material to rerank — otherwise weight-0.9 facts get evicted
        # by the top-50 cut before they're ever scored against the query.
        pool_limit = 200 if query else 50

        # Get raw facts with all value tiers
        raw = self._get_raw_facts(min_weight=min_weight, limit=pool_limit)

        # If query provided, boost relevant facts via weight bump
        if query:
            raw, relevant_concepts = self._relevance_boost(raw, query)
            # Re-sort after boost so promoted facts win the budget fill
            raw.sort(key=lambda f: f.get("weight", 0), reverse=True)

        # Pack into token budget at the right detail level
        facts = self._budget_fill(raw, context_level, query=query)

        return IntrospectionResult(
            facts=facts,
            state=self.get_metadata(),
            context_level=context_level,
            health=self.health().to_dict(),
            relevant_concepts=relevant_concepts,
        )

    def _relevance_boost(
        self,
        raw_facts: List[Dict],
        query: str,
    ) -> tuple:
        """Boost weights of query-relevant facts so _budget_fill prioritizes them.

        Instead of filtering out irrelevant facts (which loses data),
        this promotes relevant ones to the top of the budget window.
        Non-relevant facts still appear if budget allows, just at L1.
        """
        try:
            from agent.threads.linking_core.schema import (
                spread_activate,
                extract_concepts_from_text,
            )

            query_concepts = extract_concepts_from_text(query)
            relevant = set(query_concepts)

            if query_concepts:
                activated = spread_activate(
                    input_concepts=query_concepts,
                    activation_threshold=0.1,
                    max_hops=1,
                    limit=20,
                )
                for a in activated:
                    relevant.add(a.get("concept", ""))

            # Literal-token fallback: when the concept graph hasn't yet
            # learned a query word (new fact, no edges), still let raw
            # query tokens score against fact text. Keeps newly-written
            # facts surfaceable on their first mention.
            import re as _re
            literal_tokens = {
                t for t in _re.findall(r"\b[a-z][a-z0-9]{2,}\b", query.lower())
                if t not in {"the", "and", "for", "what", "who", "how",
                             "does", "are", "was", "they", "this", "that",
                             "with", "from", "into", "run", "work", "you",
                             "your", "have", "has"}
            }
            relevant.update(literal_tokens)

            # Boost weight of matching facts so they sort first.
            # Boost EXCEEDS the natural 1.0 ceiling on purpose: query-
            # relevant facts must rank above pre-existing weight-1.0 facts
            # to win the tight budget that the orchestrator imposes.
            for fact in raw_facts:
                text = f"{fact.get('profile_id', '')} {fact.get('key', '')} " \
                       f"{fact.get('l1_value', '')} {fact.get('l2_value', '')}".lower()
                for concept in relevant:
                    if concept and concept.lower() in text:
                        fact["weight"] = fact.get("weight", 0.5) + 0.5
                        break

            return raw_facts, list(relevant)
        except Exception:
            return raw_facts, []
    
    def _filter_by_relevance(
        self, 
        items: List[Dict], 
        query: str, 
        level: int
    ) -> tuple:
        """Filter items by relevance to query using LinkingCore."""
        try:
            from agent.threads.linking_core.schema import (
                spread_activate, 
                extract_concepts_from_text
            )
            
            query_concepts = extract_concepts_from_text(query)
            if not query_concepts:
                return items, []
            
            activated = spread_activate(
                input_concepts=query_concepts,
                activation_threshold=0.1,
                max_hops=1,
                limit=20
            )
            
            relevant = set(query_concepts)
            for a in activated:
                relevant.add(a.get("concept", ""))
            
            # Filter items - check profile_id, key, AND value
            filtered = []
            for item in items:
                profile_id = item.get("profile_id", "").lower()
                key = item.get("key", "").lower()
                value = str(item.get("value", "")).lower()
                # Include profile_id in searchable text (e.g. "family.dad" matches "dad")
                item_text = f"{profile_id} {key} {value}"
                
                for concept in relevant:
                    if concept.lower() in item_text:
                        filtered.append(item)
                        break
            
            return (filtered if filtered else items[:10], list(relevant))
            
        except Exception:
            return items, []
    
    def health(self) -> HealthReport:
        """Check identity thread health."""
        try:
            rows = self.get_data(level=2)
            row_count = len(rows)
            
            if row_count == 0:
                return HealthReport.degraded(
                    "No identity data found",
                    row_count=0
                )
            
            return HealthReport.ok(
                f"{row_count} facts",
                row_count=row_count
            )
        except Exception as e:
            return HealthReport.error(str(e))
    
    def score_relevance(self, fact: str, context: Dict[str, Any] = None) -> float:
        """
        Score a fact by goal/value relevance (PFC function).
        
        High score if fact mentions:
        - Active project
        - User's stated goals
        - User's core values/preferences
        
        If confidence is high, logs training example (append-only learning).
        """
        if not context:
            return 0.5
        
        score = 0.5
        fact_lower = fact.lower()
        
        # Check active project match
        active_project = context.get('active_project', '')
        if active_project and active_project.lower() in fact_lower:
            score += 0.3
        
        # Check query relevance
        query = context.get('query', '')
        if query:
            query_words = set(query.lower().split())
            fact_words = set(fact_lower.split())
            overlap = len(query_words & fact_words)
            if overlap > 0:
                score += min(overlap * 0.1, 0.3)
        
        # Check goal keywords
        goal_keywords = context.get('goal_keywords', [])
        for kw in goal_keywords:
            if kw.lower() in fact_lower:
                score += 0.15
        
        final_score = min(score, 1.0)
        return final_score
    
    # Legacy compatibility - map old module-based calls to flat table
    def get_module_data(self, module: str, level: int = 2) -> List[Dict]:
        """Legacy: Get data filtered by old module structure."""
        # Map old modules to key prefixes
        prefix_map = {
            "user_profile": ["user_"],
            "aios_self": ["agent_", "comm_"],
            "machine_context": ["machine_"],
        }
        prefixes = prefix_map.get(module, [])
        
        rows = self.get_data(level=level)
        if not prefixes:
            return rows
        
        filtered = []
        for row in rows:
            if any(row['key'].startswith(p) for p in prefixes):
                # Convert to old format
                filtered.append({
                    "key": row['key'],
                    "metadata": {"type": row.get('metadata_type'), "description": row.get('metadata_desc')},
                    "data": {"value": row['value']},
                    "level": level,
                    "weight": row['weight']
                })
        return filtered


__all__ = ["IdentityThreadAdapter"]
