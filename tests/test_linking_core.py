"""
Linking Core Tests
==================
Unit tests for the concept graph, Hebbian learning, spread activation,
decay, scoring, and thread keyword scoring.

~25 tests covering the attention mechanism.
"""

import os
import pytest
import tempfile
import sqlite3

# Force test DB
os.environ.setdefault("AIOS_DB_PATH", os.path.join(tempfile.mkdtemp(), "test_linking.db"))


# ─────────────────────────────────────────────────────────────
# Hebbian Learning
# ─────────────────────────────────────────────────────────────

class TestHebbianLearning:
    """Test link_concepts (Hebbian update rule)."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_new_link_starts_at_learning_rate(self):
        from agent.threads.linking_core.schema import link_concepts
        strength = link_concepts("coffee", "morning", learning_rate=0.1)
        assert strength == pytest.approx(0.1)

    def test_repeated_firing_increases_strength(self):
        from agent.threads.linking_core.schema import link_concepts
        s1 = link_concepts("coffee", "morning", learning_rate=0.1)
        s2 = link_concepts("coffee", "morning", learning_rate=0.1)
        s3 = link_concepts("coffee", "morning", learning_rate=0.1)
        assert s1 < s2 < s3

    def test_strength_approaches_but_never_exceeds_one(self):
        from agent.threads.linking_core.schema import link_concepts
        s = 0
        for _ in range(100):
            s = link_concepts("a", "b", learning_rate=0.3)
        assert s <= 1.0
        assert s > 0.95  # should be very close to 1.0

    def test_canonical_ordering(self):
        """link_concepts(a,b) and link_concepts(b,a) update the same row."""
        from agent.threads.linking_core.schema import link_concepts, get_links_for_concept
        link_concepts("zebra", "apple", learning_rate=0.2)
        link_concepts("apple", "zebra", learning_rate=0.2)
        links = get_links_for_concept("apple")
        # Should be exactly one link, fired twice
        zebra_links = [l for l in links if l["concept"] == "zebra"]
        assert len(zebra_links) == 1

    def test_different_pairs_independent(self):
        from agent.threads.linking_core.schema import link_concepts
        s1 = link_concepts("cat", "dog", learning_rate=0.1)
        s2 = link_concepts("sun", "moon", learning_rate=0.5)
        assert s1 == pytest.approx(0.1)
        assert s2 == pytest.approx(0.5)


# ─────────────────────────────────────────────────────────────
# Spread Activation
# ─────────────────────────────────────────────────────────────

class TestSpreadActivation:
    """Test spread_activate graph traversal."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_single_hop(self):
        from agent.threads.linking_core.schema import link_concepts, spread_activate
        link_concepts("sarah", "coffee", learning_rate=0.8)
        results = spread_activate(["sarah"], activation_threshold=0.1, max_hops=1)
        concepts = [r["concept"] for r in results]
        assert "coffee" in concepts

    def test_multi_hop(self):
        from agent.threads.linking_core.schema import link_concepts, spread_activate
        link_concepts("sarah", "coffee", learning_rate=0.9)
        link_concepts("coffee", "morning", learning_rate=0.9)
        results = spread_activate(["sarah"], activation_threshold=0.1, max_hops=2)
        concepts = [r["concept"] for r in results]
        assert "coffee" in concepts
        assert "morning" in concepts

    def test_activation_diminishes_per_hop(self):
        from agent.threads.linking_core.schema import link_concepts, spread_activate
        link_concepts("a", "b", learning_rate=0.9)
        link_concepts("b", "c", learning_rate=0.9)
        results = spread_activate(["a"], activation_threshold=0.01, max_hops=2)
        by_concept = {r["concept"]: r["activation"] for r in results}
        # b (1 hop) should have higher activation than c (2 hops)
        assert by_concept.get("b", 0) > by_concept.get("c", 0)

    def test_empty_seed_returns_empty(self):
        from agent.threads.linking_core.schema import spread_activate
        results = spread_activate([], activation_threshold=0.1, max_hops=1)
        assert results == []

    def test_unlinked_concept_returns_empty(self):
        from agent.threads.linking_core.schema import spread_activate
        results = spread_activate(["nonexistent_xyz"], activation_threshold=0.1, max_hops=1)
        assert results == []

    def test_circular_graph_no_infinite_loop(self):
        from agent.threads.linking_core.schema import link_concepts, spread_activate
        link_concepts("x", "y", learning_rate=0.8)
        link_concepts("y", "z", learning_rate=0.8)
        link_concepts("z", "x", learning_rate=0.8)
        # Should not hang
        results = spread_activate(["x"], activation_threshold=0.01, max_hops=3)
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────
# Decay
# ─────────────────────────────────────────────────────────────

class TestDecay:
    """Test decay_concept_links."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_decay_reduces_strength(self):
        from agent.threads.linking_core.schema import link_concepts, decay_concept_links
        from data.db import get_connection
        from contextlib import closing
        link_concepts("a", "b", learning_rate=0.5)
        decay_concept_links(decay_rate=0.5, min_strength=0.01)
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT strength FROM concept_links WHERE concept_a='a' AND concept_b='b'"
            ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(0.25)  # 0.5 * 0.5

    def test_weak_links_pruned(self):
        from agent.threads.linking_core.schema import link_concepts, decay_concept_links
        from data.db import get_connection
        from contextlib import closing
        link_concepts("a", "b", learning_rate=0.04)  # starts at 0.04
        pruned = decay_concept_links(decay_rate=0.5, min_strength=0.05)
        assert pruned >= 1
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT strength FROM concept_links WHERE concept_a='a' AND concept_b='b'"
            ).fetchone()
        assert row is None  # pruned

    def test_strong_links_survive(self):
        from agent.threads.linking_core.schema import link_concepts, decay_concept_links
        from data.db import get_connection
        from contextlib import closing
        link_concepts("a", "b", learning_rate=0.9)
        decay_concept_links(decay_rate=0.95, min_strength=0.05)
        with closing(get_connection(readonly=True)) as conn:
            row = conn.execute(
                "SELECT strength FROM concept_links WHERE concept_a='a' AND concept_b='b'"
            ).fetchone()
        assert row is not None
        assert row[0] > 0.8


# ─────────────────────────────────────────────────────────────
# Consolidation (SHORT → LONG potentiation)
# ─────────────────────────────────────────────────────────────

class TestConsolidation:
    """Test consolidate_links SHORT→LONG promotion."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_promotion_after_enough_fires(self):
        from agent.threads.linking_core.schema import link_concepts, consolidate_links
        for _ in range(10):
            link_concepts("dad", "fishing", learning_rate=0.15)
        result = consolidate_links(fire_threshold=5, strength_threshold=0.3)
        assert result["promoted"] >= 1
        assert result["total_long"] >= 1

    def test_weak_links_not_promoted(self):
        from agent.threads.linking_core.schema import link_concepts, consolidate_links
        link_concepts("x", "y", learning_rate=0.01)  # very weak
        result = consolidate_links(fire_threshold=5, strength_threshold=0.3)
        assert result["promoted"] == 0

    def test_potentiation_stats(self):
        from agent.threads.linking_core.schema import link_concepts, consolidate_links, get_potentiation_stats
        for _ in range(10):
            link_concepts("a", "b", learning_rate=0.2)
        link_concepts("c", "d", learning_rate=0.1)
        consolidate_links(fire_threshold=5, strength_threshold=0.3)
        stats = get_potentiation_stats()
        assert "SHORT" in stats
        assert "LONG" in stats


# ─────────────────────────────────────────────────────────────
# Concept Extraction
# ─────────────────────────────────────────────────────────────

class TestConceptExtraction:
    """Test extract_concepts_from_text."""

    def test_extracts_names(self):
        from agent.threads.linking_core.schema import extract_concepts_from_text
        concepts = extract_concepts_from_text("Did Sarah mention coffee?")
        assert "sarah" in concepts

    def test_extracts_content_words(self):
        from agent.threads.linking_core.schema import extract_concepts_from_text
        concepts = extract_concepts_from_text("architecture and deployment patterns")
        assert "architecture" in concepts
        assert "deployment" in concepts
        assert "patterns" in concepts

    def test_filters_stop_words(self):
        from agent.threads.linking_core.schema import extract_concepts_from_text
        concepts = extract_concepts_from_text("the is a an with for and but")
        assert len(concepts) == 0

    def test_extracts_from_value(self):
        from agent.threads.linking_core.schema import extract_concepts_from_value
        concepts = extract_concepts_from_value("Sarah works at Blue Bottle Coffee")
        assert "sarah" in concepts
        assert "coffee" in concepts


# ─────────────────────────────────────────────────────────────
# Concept CRUD
# ─────────────────────────────────────────────────────────────

class TestConceptCRUD:
    """Test concept and link CRUD operations."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_create_link(self):
        from agent.threads.linking_core.schema import create_link, get_links_for_concept
        create_link("a", "b", strength=0.7)
        links = get_links_for_concept("a")
        assert len(links) == 1
        assert links[0]["concept"] == "b"
        assert links[0]["strength"] == pytest.approx(0.7)

    def test_get_all_links(self):
        from agent.threads.linking_core.schema import create_link, get_all_links
        create_link("a", "b", strength=0.5)
        create_link("c", "d", strength=0.6)
        links = get_all_links()
        assert len(links) >= 2

    def test_delete_link(self):
        from agent.threads.linking_core.schema import create_link, delete_link, get_links_for_concept
        create_link("a", "b", strength=0.5)
        deleted = delete_link("a", "b")
        assert deleted is True
        links = get_links_for_concept("a")
        assert len(links) == 0

    def test_update_strength(self):
        from agent.threads.linking_core.schema import create_link, update_link_strength, get_links_for_concept
        create_link("a", "b", strength=0.3)
        update_link_strength("a", "b", 0.9)
        links = get_links_for_concept("a")
        assert links[0]["strength"] == pytest.approx(0.9)

    def test_get_concepts(self):
        from agent.threads.linking_core.schema import create_link, get_concepts
        create_link("hello", "world", strength=0.5)
        concepts = get_concepts()
        names = [c["concept"] for c in concepts]
        assert "hello" in names
        assert "world" in names


# ─────────────────────────────────────────────────────────────
# Co-occurrence
# ─────────────────────────────────────────────────────────────

class TestCooccurrence:
    """Test co-occurrence recording and scoring."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_cooccurrence_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            try:
                conn.execute("DELETE FROM key_cooccurrence")
            except:
                pass
            conn.commit()
        init_cooccurrence_table()

    def test_record_and_score(self):
        from agent.threads.linking_core.schema import record_cooccurrence, get_cooccurrence_score
        for _ in range(5):
            record_cooccurrence("identity.user", "coffee")
        score = get_cooccurrence_score("identity.user", ["coffee"])
        assert score > 0

    def test_no_cooccurrence_zero_score(self):
        from agent.threads.linking_core.schema import get_cooccurrence_score
        score = get_cooccurrence_score("never_seen", ["also_never"])
        assert score == 0.0

    def test_record_concept_cooccurrence(self):
        from agent.threads.linking_core.schema import record_concept_cooccurrence, get_links_for_concept
        count = record_concept_cooccurrence(["sarah", "coffee", "morning"], learning_rate=0.2)
        assert count == 3  # 3 pairs: sarah-coffee, sarah-morning, coffee-morning
        links = get_links_for_concept("sarah")
        assert len(links) >= 2


# ─────────────────────────────────────────────────────────────
# Thread Keyword Scoring
# ─────────────────────────────────────────────────────────────

class TestKeywordScoreThreads:
    """Test _keyword_score_threads — the attention mechanism fallback."""

    def setup_method(self):
        from agent.threads.linking_core.adapter import LinkingCoreThreadAdapter
        self.adapter = LinkingCoreThreadAdapter()

    def test_identity_keywords_boost(self):
        scores = self.adapter._keyword_score_threads("who am I")
        assert scores.get("identity", 0) >= 9.0

    def test_log_temporal_keywords_boost(self):
        scores = self.adapter._keyword_score_threads("what happened yesterday")
        assert scores.get("log", 0) >= 9.0

    def test_log_default_when_no_temporal(self):
        scores = self.adapter._keyword_score_threads("tell me about architecture")
        assert scores.get("log", 0) == 5.0

    def test_philosophy_values_boost(self):
        scores = self.adapter._keyword_score_threads("why should I believe that")
        assert scores.get("philosophy", 0) >= 9.0

    def test_form_action_boost(self):
        scores = self.adapter._keyword_score_threads("create a new file")
        assert scores.get("form", 0) >= 8.0

    def test_linking_core_always_low(self):
        scores = self.adapter._keyword_score_threads("anything at all")
        assert scores.get("linking_core", 0) <= 3.0

    def test_date_reference_boosts_log(self):
        """Date patterns like 'dec 30th' should boost log to 9.0."""
        scores = self.adapter._keyword_score_threads("what did I do dec 30th")
        assert scores.get("log", 0) >= 9.0

    def test_date_slash_format_boosts_log(self):
        scores = self.adapter._keyword_score_threads("check 12/30/2025")
        assert scores.get("log", 0) >= 9.0

    def test_date_iso_format_boosts_log(self):
        scores = self.adapter._keyword_score_threads("events on 2025-12-30")
        assert scores.get("log", 0) >= 9.0

    def test_month_name_boosts_log(self):
        scores = self.adapter._keyword_score_threads("what happened in January")
        assert scores.get("log", 0) >= 9.0


# ─────────────────────────────────────────────────────────────
# Graph Stats & Indexing
# ─────────────────────────────────────────────────────────────

class TestGraphStats:
    """Test graph statistics and indexing."""

    def setup_method(self):
        from agent.threads.linking_core.schema import init_concept_links_table
        from data.db import get_connection
        from contextlib import closing
        with closing(get_connection()) as conn:
            conn.execute("DELETE FROM concept_links")
            conn.commit()
        init_concept_links_table()

    def test_stats_returns_counts(self):
        from agent.threads.linking_core.schema import create_link, get_stats
        create_link("a", "b", strength=0.5)
        create_link("b", "c", strength=0.6)
        stats = get_stats()
        assert stats["link_count"] == 2
        assert stats["concept_count"] == 3

    def test_index_key_creates_links(self):
        from agent.threads.linking_core.schema import index_key_in_concept_graph, get_links_for_concept
        count = index_key_in_concept_graph("identity.user.name", "Jordan", learning_rate=0.2)
        assert count > 0
        # Should have hierarchy links: identity→identity.user, identity.user→identity.user.name
        links = get_links_for_concept("identity.user")
        assert len(links) >= 1

    def test_graph_data_for_visualization(self):
        from agent.threads.linking_core.schema import create_link, get_graph_data
        create_link("x", "y", strength=0.7)
        create_link("y", "z", strength=0.6)
        data = get_graph_data()
        assert "nodes" in data
        assert "links" in data
        assert data["node_count"] >= 2


# ─────────────────────────────────────────────────────────────
# Scoring Functions (pure)
# ─────────────────────────────────────────────────────────────

class TestScoringFunctions:
    """Test the pure scoring functions in scoring.py."""

    def test_keyword_fallback_exact_match(self):
        from agent.threads.linking_core.scoring import keyword_fallback_score
        score = keyword_fallback_score("hello world", "hello world today")
        assert score > 0.5

    def test_keyword_fallback_no_overlap(self):
        from agent.threads.linking_core.scoring import keyword_fallback_score
        score = keyword_fallback_score("apple banana", "car truck")
        assert score == 0.0

    def test_keyword_fallback_empty(self):
        from agent.threads.linking_core.scoring import keyword_fallback_score
        assert keyword_fallback_score("", "hello") == 0.0
        assert keyword_fallback_score("hello", "") == 0.0

    def test_cache_stats(self):
        from agent.threads.linking_core.scoring import cache_stats
        stats = cache_stats()
        assert "size" in stats
        assert "ollama_available" in stats

    def test_clear_cache(self):
        from agent.threads.linking_core.scoring import clear_cache
        count = clear_cache()
        assert isinstance(count, int)
