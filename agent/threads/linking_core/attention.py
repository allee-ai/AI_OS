"""
Graph attention over the concept connectome — for STATE shaping.

This is matrix attention, not BFS graph-walk. Where `spread_activate` walks edges
hop by hop, this multiplies a query activation vector against the full
(num_heads, V, V) attention bias tensor and returns per-head salience.

The 6 heads have learned semantics (identity / log / form / philosophy / reflex
/ association). Per-head output tells the orchestrator which threads should
dominate STATE for THIS query — that's elasticity driven by a learned attention
prior, not heuristic budget allocation.

Pipeline:
    query string + extracted concepts
        → encode_query() → (V,) sparse activation vector
        → attend(qv, steps=k) → (num_heads, V) per-head salience
        → head_priorities() → {thread_name: weight} for STATE budget allocation
        → top_concepts_per_head() → which concepts to materialize as facts

The npy assets are produced by research/hebbian_attention/graph_to_matrix.py
and refreshed by a nightly loop (TODO).

Usage:
    from agent.threads.linking_core.attention import get_graph_attention
    ga = get_graph_attention()  # cached singleton, lazy-loaded
    if ga.available:
        priorities = ga.shape_state(query="should i go to bed?",
                                     extracted_concepts=["sleep", "schedule"])
        # priorities = {"identity": 0.12, "log": 0.41, "form": 0.04,
        #               "philosophy": 0.08, "reflex": 0.21, "association": 0.14}
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Tuple

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATA_DIR = REPO_ROOT / "research" / "hebbian_attention" / "data"

# Head index → thread name. Order MUST match graph_to_matrix.py.
HEAD_TO_THREAD: Tuple[str, ...] = (
    "identity",      # head 0
    "log",           # head 1
    "form",          # head 2
    "philosophy",    # head 3
    "reflex",        # head 4
    "association",   # head 5 — generic, weights "linking_core" itself
)

logger = logging.getLogger(__name__)


@dataclass
class GraphAttentionResult:
    """Output of a single attention pass."""
    head_priorities: Dict[str, float]
    top_concepts_per_head: Dict[str, List[Tuple[str, float]]]
    query_concept_count: int  # how many concepts hit the vocab
    iterations: int
    elapsed_ms: float


class GraphAttention:
    """Loads the concept-graph attention tensor and runs query-time attention.

    Lazy-loaded singleton via :func:`get_graph_attention`.
    """

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
        self.bias: Optional[np.ndarray] = None  # (num_heads, V, V)
        self.position: Optional[np.ndarray] = None  # (V,)
        self.vocab: List[str] = []
        self.concept_to_idx: Dict[str, int] = {}
        self.num_heads: int = 0
        self.vocab_size: int = 0
        self.available: bool = False
        self._load_attempted = False

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True

        bias_path = self.data_dir / "attention_bias.npy"
        vocab_path = self.data_dir / "vocab.json"
        pos_path = self.data_dir / "position_encoding.npy"

        if not bias_path.exists() or not vocab_path.exists():
            logger.info(
                "graph_attention: assets missing in %s — falling back to spread_activate",
                self.data_dir,
            )
            return

        try:
            self.bias = np.load(str(bias_path))
            raw = json.loads(vocab_path.read_text())
            # vocab.json may be either a flat list of concepts (legacy) or
            # {"concept_to_idx": {...}, "vocab_size": N} (current).
            if isinstance(raw, dict) and "concept_to_idx" in raw:
                self.concept_to_idx = dict(raw["concept_to_idx"])
                # Build vocab list ordered by index for fast int → concept lookup
                ordered = sorted(self.concept_to_idx.items(), key=lambda kv: kv[1])
                self.vocab = [c for c, _ in ordered]
            elif isinstance(raw, list):
                self.vocab = list(raw)
                self.concept_to_idx = {c: i for i, c in enumerate(self.vocab)}
            else:
                raise ValueError(f"unexpected vocab.json shape: {type(raw)}")
            self.num_heads, self.vocab_size, _ = self.bias.shape
            if pos_path.exists():
                self.position = np.load(str(pos_path))
            self.available = True
            logger.info(
                "graph_attention: loaded %d heads, vocab=%d, position=%s",
                self.num_heads,
                self.vocab_size,
                "present" if self.position is not None else "absent",
            )
        except Exception as e:
            logger.warning("graph_attention: failed to load assets: %s", e)
            self.available = False

    # ── encoding ──────────────────────────────────────────────────────

    def encode_query(
        self,
        query: str,
        extracted_concepts: Optional[List[str]] = None,
    ) -> np.ndarray:
        """Convert a query + extracted concepts into a (V,) activation vector.

        Direct concept matches → 1.0
        Substring/prefix matches → 0.5 (capped at 1.0 if also direct)
        Hierarchical parent matches (`identity` activates `identity.user.*`) → 0.3

        Returns zero vector if not loaded.
        """
        self._load()
        if not self.available:
            return np.zeros(0, dtype=np.float32)

        qv = np.zeros(self.vocab_size, dtype=np.float32)
        seeds = list(extracted_concepts or [])

        # Direct hits from extracted concepts
        for c in seeds:
            if c in self.concept_to_idx:
                qv[self.concept_to_idx[c]] = 1.0

        # Tokenize the query for partial matching
        q_lower = query.lower()
        q_tokens = {t for t in q_lower.replace(".", " ").split() if len(t) > 2}

        for concept, idx in self.concept_to_idx.items():
            if qv[idx] >= 1.0:
                continue
            cl = concept.lower()
            # Whole-concept appears in query
            if cl in q_lower and len(cl) > 3:
                qv[idx] = max(qv[idx], 0.5)
                continue
            # Concept token overlaps with query tokens
            c_tokens = set(cl.replace(".", " ").replace("_", " ").split())
            if q_tokens & c_tokens:
                qv[idx] = max(qv[idx], 0.3)

        # Hierarchical: if `identity` is seeded, also activate `identity.*`
        for c in seeds:
            for concept, idx in self.concept_to_idx.items():
                if concept.startswith(c + ".") and qv[idx] < 0.3:
                    qv[idx] = 0.3

        return qv

    # ── attention pass ────────────────────────────────────────────────

    def attend(
        self,
        qv: np.ndarray,
        steps: int = 2,
        temperature: float = 1.0,
        decay: float = 0.6,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Iterate matrix attention over the graph.

        For each head h, repeat `steps` times:
            qv_h_next = decay * qv_h + (1 - decay) * normalize(bias_h @ qv_h)

        Per-head accumulator preserves the original query while letting it
        diffuse through the graph.

        Returns:
            (head_state, propagated_only)
            - head_state: (num_heads, V) — full per-head activation including seed residual
            - propagated_only: (num_heads, V) — only the diffused mass (seed subtracted)
              Use this for head_priorities so seed-equality doesn't dominate.
        """
        self._load()
        if not self.available or qv.size == 0:
            return np.zeros((0, 0), dtype=np.float32), np.zeros((0, 0), dtype=np.float32)

        # Per-head working copies
        head_state = np.tile(qv[None, :], (self.num_heads, 1))
        seed_residual = np.tile(qv[None, :], (self.num_heads, 1))

        for _ in range(steps):
            propagated = np.einsum("hij,hj->hi", self.bias, head_state)
            norms = np.maximum(propagated.sum(axis=1, keepdims=True), 1e-8)
            propagated = propagated / norms
            if temperature != 1.0:
                propagated = propagated ** (1.0 / temperature)
                norms = np.maximum(propagated.sum(axis=1, keepdims=True), 1e-8)
                propagated = propagated / norms
            head_state = decay * head_state + (1.0 - decay) * propagated
            # Track seed residual separately so we can subtract it out
            seed_residual = decay * seed_residual

        propagated_only = np.maximum(head_state - seed_residual, 0.0)
        return head_state, propagated_only

    # ── post-processing ───────────────────────────────────────────────

    def head_priorities(self, head_state: np.ndarray) -> Dict[str, float]:
        """Sum each head's activation, normalize across heads, return as
        thread-name → weight."""
        if head_state.size == 0:
            return {name: 0.0 for name in HEAD_TO_THREAD}

        head_totals = head_state.sum(axis=1)
        total = max(head_totals.sum(), 1e-8)
        normalized = head_totals / total

        return {
            HEAD_TO_THREAD[h]: float(normalized[h])
            for h in range(min(self.num_heads, len(HEAD_TO_THREAD)))
        }

    def top_concepts_per_head(
        self,
        head_state: np.ndarray,
        k: int = 10,
        min_activation: float = 1e-4,
    ) -> Dict[str, List[Tuple[str, float]]]:
        """Top-k concepts per head with their activations."""
        result: Dict[str, List[Tuple[str, float]]] = {}
        if head_state.size == 0:
            return result

        for h in range(min(self.num_heads, len(HEAD_TO_THREAD))):
            row = head_state[h]
            top_idx = np.argpartition(-row, min(k, row.size - 1))[:k]
            top_idx = top_idx[np.argsort(-row[top_idx])]
            entries = [
                (self.vocab[i], float(row[i]))
                for i in top_idx
                if row[i] >= min_activation
            ]
            result[HEAD_TO_THREAD[h]] = entries
        return result

    # ── one-shot convenience ──────────────────────────────────────────

    def shape_state(
        self,
        query: str,
        extracted_concepts: Optional[List[str]] = None,
        steps: int = 2,
        top_k: int = 10,
    ) -> GraphAttentionResult:
        """Full pipeline: encode → attend → priorities + top concepts.

        Priorities are computed from the *propagated* component (seed mass
        subtracted) so head differentiation isn't washed out by the seeds
        being equally present across all heads.
        """
        import time
        t0 = time.perf_counter()

        qv = self.encode_query(query, extracted_concepts)
        head_state, propagated = self.attend(qv, steps=steps)
        # Priorities from propagated (delta) — this is the head-specific signal
        priorities = self.head_priorities(propagated)
        # Top concepts from full head_state — surfaces both seed and spread
        top = self.top_concepts_per_head(head_state, k=top_k)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return GraphAttentionResult(
            head_priorities=priorities,
            top_concepts_per_head=top,
            query_concept_count=int((qv >= 0.5).sum()) if qv.size else 0,
            iterations=steps,
            elapsed_ms=elapsed_ms,
        )


# ── singleton ─────────────────────────────────────────────────────────

_INSTANCE: Optional[GraphAttention] = None
_LOCK = Lock()


def get_graph_attention(data_dir: Optional[Path] = None) -> GraphAttention:
    """Cached singleton accessor."""
    global _INSTANCE
    with _LOCK:
        if _INSTANCE is None:
            _INSTANCE = GraphAttention(data_dir=data_dir)
            _INSTANCE._load()
    return _INSTANCE


def reload_graph_attention() -> GraphAttention:
    """Force reload — call after rebuilding the .npy assets."""
    global _INSTANCE
    with _LOCK:
        _INSTANCE = GraphAttention()
        _INSTANCE._load()
    return _INSTANCE
