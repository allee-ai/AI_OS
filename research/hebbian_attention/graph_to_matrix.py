"""
graph_to_matrix.py — Convert concept_links into sparse attention tensors.

This is the bridge between AI_OS's Hebbian concept graph (SQLite)
and a trainable transformer attention matrix (PyTorch/MLX).

The core idea: concept_links IS an attention matrix stored on disk.
Each (concept_a, concept_b, strength) row is a learned attention weight.
We convert this into formats usable for model initialization.

Output formats:
  1. Sparse adjacency matrix (COO format) — for attention bias initialization
  2. Concept vocabulary + embeddings — for the embedding layer
  3. Degree-weighted position encodings — graph distance from identity node
"""

import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, deque

# Try torch, fall back gracefully
try:
    import torch
    import torch.sparse
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

# Try MLX for Apple Silicon native
try:
    import mlx.core as mx
    HAS_MLX = True
except ImportError:
    HAS_MLX = False


# ─────────────────────────────────────────────────────────────
# 1. Load graph from SQLite
# ─────────────────────────────────────────────────────────────

def load_concept_graph(
    db_path: str = "data/db/state.db",
    min_strength: float = 0.1,
    potentiation: Optional[str] = None,
    min_fire_count: int = 1,
) -> Tuple[List[str], Dict[str, int], List[Tuple[int, int, float]]]:
    """
    Load concept graph from state.db.

    Args:
        db_path: Path to SQLite database
        min_strength: Minimum link strength to include
        potentiation: Filter by potentiation ('LONG', 'SHORT', or None for all)
        min_fire_count: Minimum fire count to include

    Returns:
        (vocab, concept_to_idx, edges)
        - vocab: List of concept strings, index = token id
        - concept_to_idx: Reverse lookup
        - edges: List of (src_idx, dst_idx, strength)
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Build query with filters
    conditions = ["strength >= ?"]
    params: list = [min_strength]

    if potentiation:
        conditions.append("potentiation = ?")
        params.append(potentiation)

    if min_fire_count > 1:
        conditions.append("fire_count >= ?")
        params.append(min_fire_count)

    where = " AND ".join(conditions)

    # Get all concepts that participate in filtered edges
    cur.execute(f"""
        SELECT DISTINCT c FROM (
            SELECT concept_a AS c FROM concept_links WHERE {where}
            UNION
            SELECT concept_b AS c FROM concept_links WHERE {where}
        ) ORDER BY c
    """, params + params)

    vocab = [row[0] for row in cur.fetchall()]
    concept_to_idx = {c: i for i, c in enumerate(vocab)}

    # Load edges
    cur.execute(f"""
        SELECT concept_a, concept_b, strength
        FROM concept_links
        WHERE {where}
    """, params)

    edges = []
    for a, b, s in cur.fetchall():
        if a in concept_to_idx and b in concept_to_idx:
            i, j = concept_to_idx[a], concept_to_idx[b]
            edges.append((i, j, s))
            edges.append((j, i, s))  # Undirected graph → symmetric matrix

    conn.close()

    return vocab, concept_to_idx, edges


# ─────────────────────────────────────────────────────────────
# 2. Build sparse adjacency matrix
# ─────────────────────────────────────────────────────────────

def build_adjacency_matrix_numpy(
    vocab_size: int,
    edges: List[Tuple[int, int, float]],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Build sparse adjacency in COO format (numpy arrays).

    Returns:
        (row_indices, col_indices, values) — all numpy arrays
    """
    if not edges:
        return np.array([], dtype=np.int64), np.array([], dtype=np.int64), np.array([], dtype=np.float32)

    rows = np.array([e[0] for e in edges], dtype=np.int64)
    cols = np.array([e[1] for e in edges], dtype=np.int64)
    vals = np.array([e[2] for e in edges], dtype=np.float32)

    return rows, cols, vals


def build_adjacency_torch(
    vocab_size: int,
    edges: List[Tuple[int, int, float]],
) -> "torch.Tensor":
    """
    Build sparse adjacency matrix as a PyTorch sparse COO tensor.

    This can be added directly to attention logits as a bias:
        attn_weights = Q @ K^T / sqrt(d_k) + adjacency_bias
    """
    if not HAS_TORCH:
        raise ImportError("PyTorch not available")

    rows, cols, vals = build_adjacency_matrix_numpy(vocab_size, edges)

    indices = torch.stack([
        torch.from_numpy(rows),
        torch.from_numpy(cols),
    ])
    values = torch.from_numpy(vals)

    return torch.sparse_coo_tensor(
        indices, values, size=(vocab_size, vocab_size)
    ).coalesce()


def build_adjacency_mlx(
    vocab_size: int,
    edges: List[Tuple[int, int, float]],
) -> Any:
    """
    Build adjacency data for MLX (Apple Silicon native).

    MLX doesn't have native sparse ops yet, so we return
    a dense array for small graphs or components for manual sparse ops.
    """
    if not HAS_MLX:
        raise ImportError("MLX not available")

    # For graphs < 8K concepts, dense is fine on M-series chips
    if vocab_size <= 8192:
        dense = np.zeros((vocab_size, vocab_size), dtype=np.float32)
        for i, j, v in edges:
            dense[i][j] = v
        return mx.array(dense)
    else:
        # Return components for manual sparse matmul
        rows, cols, vals = build_adjacency_matrix_numpy(vocab_size, edges)
        return {
            "rows": mx.array(rows),
            "cols": mx.array(cols),
            "values": mx.array(vals),
            "shape": (vocab_size, vocab_size),
        }


# ─────────────────────────────────────────────────────────────
# 3. Attention bias from graph (the key innovation)
# ─────────────────────────────────────────────────────────────

def graph_to_attention_bias(
    vocab_size: int,
    edges: List[Tuple[int, int, float]],
    num_heads: int = 6,
    scale: float = 2.0,
) -> np.ndarray:
    """
    Convert concept graph into multi-head attention bias.

    Each head gets a different view of the graph:
      Head 0 (Identity):    Boost links involving identity.* concepts
      Head 1 (Log):         Boost links by recency (fire_count as proxy)
      Head 2 (Form):        Boost links involving form.* concepts
      Head 3 (Philosophy):  Boost links involving philosophy.* concepts
      Head 4 (Reflex):      Boost high-strength links (fast associations)
      Head 5 (Association): Raw graph structure (cooccurrence)

    Args:
        vocab_size: Number of concepts
        edges: List of (src, dst, strength)
        num_heads: Number of attention heads (default 6 = cognitive dimensions)
        scale: Multiply graph strengths for attention logit scale

    Returns:
        np.ndarray of shape (num_heads, vocab_size, vocab_size)
    """
    bias = np.zeros((num_heads, vocab_size, vocab_size), dtype=np.float32)

    for i, j, strength in edges:
        # Head 5: Raw association (all edges)
        bias[5, i, j] = strength * scale

        # Head 4: Reflex — only strong links (fast path)
        if strength > 0.7:
            bias[4, i, j] = strength * scale * 1.5

    return bias


def graph_to_attention_bias_with_vocab(
    vocab: List[str],
    concept_to_idx: Dict[str, int],
    edges: List[Tuple[int, int, float]],
    num_heads: int = 6,
    scale: float = 2.0,
) -> np.ndarray:
    """
    Full attention bias using concept names for head-specific routing.

    This version uses the actual concept names to determine which head
    should attend to which links — mapping thread types to heads.
    """
    n = len(vocab)
    bias = np.zeros((num_heads, n, n), dtype=np.float32)

    # Classify concepts by thread
    identity_idx = set()
    form_idx = set()
    philosophy_idx = set()

    for concept, idx in concept_to_idx.items():
        cl = concept.lower()
        if any(cl.startswith(p) for p in ["identity", "user", "name", "self"]):
            identity_idx.add(idx)
        if any(cl.startswith(p) for p in ["form", "tool", "capability", "system"]):
            form_idx.add(idx)
        if any(cl.startswith(p) for p in ["philosophy", "value", "belief", "ethic"]):
            philosophy_idx.add(idx)

    for i, j, strength in edges:
        scaled = strength * scale

        # Head 0: Identity — links touching identity concepts
        if i in identity_idx or j in identity_idx:
            bias[0, i, j] = scaled * 1.2

        # Head 1: Log — all links (temporal proxy via strength as recency)
        bias[1, i, j] = scaled * 0.8

        # Head 2: Form — links touching form/tool concepts
        if i in form_idx or j in form_idx:
            bias[2, i, j] = scaled * 1.2

        # Head 3: Philosophy — links touching value/belief concepts
        if i in philosophy_idx or j in philosophy_idx:
            bias[3, i, j] = scaled * 1.2

        # Head 4: Reflex — only strong links
        if strength > 0.7:
            bias[4, i, j] = scaled * 1.5

        # Head 5: Association — raw structure
        bias[5, i, j] = scaled

    return bias


# ─────────────────────────────────────────────────────────────
# 4. Graph-distance position encoding
# ─────────────────────────────────────────────────────────────

def compute_identity_distance(
    vocab: List[str],
    concept_to_idx: Dict[str, int],
    edges: List[Tuple[int, int, float]],
    identity_anchors: Optional[List[str]] = None,
    max_distance: int = 20,
) -> np.ndarray:
    """
    Compute BFS distance from identity node(s) for position encoding.

    In the 3D visualization, position = graph distance from identity.
    We use the same principle for positional encoding: concepts close
    to identity get similar position encodings.

    Returns:
        np.ndarray of shape (vocab_size,) with distance values.
        Unreachable concepts get max_distance.
    """
    n = len(vocab)
    distances = np.full(n, max_distance, dtype=np.float32)

    # Find identity anchor nodes
    if identity_anchors is None:
        identity_anchors = ["name.agent", "identity", "self", "name"]

    start_nodes = set()
    for anchor in identity_anchors:
        if anchor in concept_to_idx:
            start_nodes.add(concept_to_idx[anchor])
        # Also check partial matches
        for concept, idx in concept_to_idx.items():
            if concept.startswith(anchor + ".") or concept == anchor:
                start_nodes.add(idx)

    if not start_nodes:
        # Fallback: use highest-degree node as center
        degree = defaultdict(int)
        for i, j, _ in edges:
            degree[i] += 1
            degree[j] += 1
        if degree:
            start_nodes = {max(degree, key=degree.get)}

    # Build adjacency list for BFS
    adj: Dict[int, List[int]] = defaultdict(list)
    for i, j, _ in edges:
        adj[i].append(j)
        adj[j].append(i)

    # BFS from all identity anchors simultaneously
    queue: deque = deque()
    for node in start_nodes:
        distances[node] = 0
        queue.append((node, 0))

    visited = set(start_nodes)
    while queue:
        node, dist = queue.popleft()
        if dist >= max_distance:
            continue
        for neighbor in adj[node]:
            if neighbor not in visited:
                visited.add(neighbor)
                distances[neighbor] = dist + 1
                queue.append((neighbor, dist + 1))

    return distances


# ─────────────────────────────────────────────────────────────
# 5. Export utilities
# ─────────────────────────────────────────────────────────────

def export_graph_data(
    db_path: str = "data/db/state.db",
    output_dir: str = "research/hebbian_attention/data",
    min_strength: float = 0.1,
    potentiation: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full export pipeline: load graph, compute all matrices, save to disk.

    Produces:
      - vocab.json: concept vocabulary mapping
      - adjacency.npz: sparse adjacency matrix (COO)
      - attention_bias.npy: (6, V, V) multi-head attention bias
      - position_encoding.npy: (V,) identity-distance encoding
      - graph_stats.json: summary statistics
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Load
    vocab, c2i, edges = load_concept_graph(
        db_path, min_strength=min_strength, potentiation=potentiation
    )
    n = len(vocab)

    print(f"Loaded graph: {n} concepts, {len(edges)} directed edges")

    # Vocab
    with open(out / "vocab.json", "w") as f:
        json.dump({"concept_to_idx": c2i, "vocab_size": n}, f, indent=2)

    # Sparse adjacency
    rows, cols, vals = build_adjacency_matrix_numpy(n, edges)
    np.savez(out / "adjacency.npz", rows=rows, cols=cols, values=vals, shape=np.array([n, n]))
    print(f"Adjacency: {len(rows)} nonzero entries, density={len(rows)/(n*n):.6f}")

    # Multi-head attention bias
    attn_bias = graph_to_attention_bias_with_vocab(vocab, c2i, edges)
    np.save(out / "attention_bias.npy", attn_bias)
    print(f"Attention bias: shape={attn_bias.shape}")
    for h in range(attn_bias.shape[0]):
        nonzero = np.count_nonzero(attn_bias[h])
        print(f"  Head {h}: {nonzero} nonzero entries")

    # Position encoding (identity distance)
    pos = compute_identity_distance(vocab, c2i, edges)
    np.save(out / "position_encoding.npy", pos)
    reachable = np.sum(pos < 20)
    print(f"Position encoding: {reachable}/{n} concepts reachable from identity")

    # Stats
    stats = {
        "vocab_size": n,
        "total_edges": len(edges),
        "density": len(edges) / (n * n) if n > 0 else 0,
        "avg_strength": float(np.mean(vals)) if len(vals) > 0 else 0,
        "reachable_from_identity": int(reachable),
        "head_nonzero": {
            f"head_{h}": int(np.count_nonzero(attn_bias[h]))
            for h in range(attn_bias.shape[0])
        },
    }
    with open(out / "graph_stats.json", "w") as f:
        json.dump(stats, f, indent=2)

    print(f"\nExported to {out}/")
    return stats


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Convert concept graph to attention tensors")
    parser.add_argument("--db", default="data/db/state.db", help="Path to state.db")
    parser.add_argument("--out", default="research/hebbian_attention/data", help="Output directory")
    parser.add_argument("--min-strength", type=float, default=0.1, help="Min link strength")
    parser.add_argument("--potentiation", choices=["LONG", "SHORT"], default=None, help="Filter by potentiation")
    parser.add_argument("--long-only", action="store_true", help="Only use LONG-potentiated links")

    args = parser.parse_args()

    pot = "LONG" if args.long_only else args.potentiation

    stats = export_graph_data(
        db_path=args.db,
        output_dir=args.out,
        min_strength=args.min_strength,
        potentiation=pot,
    )

    print(f"\nDone. Vocab={stats['vocab_size']}, Edges={stats['total_edges']}")
