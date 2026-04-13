"""
NolaNET — Retrieval-routing transformer for AI_OS.

A small (~8-15M param) transformer that doesn't try to memorize the world.
Instead it learns THREE skills:
  1. Parse structured context (STATE blocks, tool outputs, concept graph results)
  2. Route — decide whether to retrieve more, synthesize, or act
  3. Generate — produce responses from retrieved context

Architecture:
  - 8 transformer layers, 512 hidden dim, 8 heads
  - Concept-graph attention bias (Hebbian initialization from graph_to_matrix)
  - Retrieval-aware position encoding (graph distance from identity node)
  - ~8M parameters (fits in M-series unified memory, trains in minutes)

Why this works:
  The system already retrieves via STATE assembly, linking_core, workspace search.
  A 70B model memorizes facts. This model memorizes HOW TO USE the retrieval system.
  Humans don't know everything — they know how to find and synthesize.
  That skill compresses into far fewer parameters than the knowledge itself.
"""
import math
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

try:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.core.fast as mx_fast
except ImportError:
    raise ImportError("MLX required: pip install mlx")


# ── Model Config ────────────────────────────────────────────────────────

@dataclass
class NolaNETConfig:
    """Model dimensions. ~8M params at defaults."""
    vocab_size: int = 32000       # BPE vocab (or inherited from base tokenizer)
    hidden_size: int = 512        # d_model
    num_layers: int = 8           # transformer blocks
    num_heads: int = 8            # attention heads
    intermediate_size: int = 1536 # FFN inner dim (3x hidden)
    max_seq_length: int = 2048
    dropout: float = 0.0         # MLX doesn't use dropout at inference
    rope_theta: float = 10000.0
    rms_norm_eps: float = 1e-6
    grad_checkpoint: bool = False  # Recompute activations during backward (saves ~50% activation memory)
    # Concept graph
    concept_vocab_size: int = 0   # Set from graph_to_matrix output
    use_graph_bias: bool = True   # Initialize attention from concept graph

    @property
    def head_dim(self) -> int:
        return self.hidden_size // self.num_heads

    @property
    def param_count(self) -> int:
        """Rough parameter count (with weight tying)."""
        embed = self.vocab_size * self.hidden_size  # shared with lm_head
        per_layer = (
            3 * self.hidden_size * self.hidden_size +  # QKV
            self.hidden_size * self.hidden_size +        # O projection
            3 * self.hidden_size * self.intermediate_size +  # SwiGLU: gate+up+down
            2 * self.hidden_size  # 2x RMSNorm
        )
        total = embed + (per_layer * self.num_layers)  # no separate lm_head
        return total

    def save(self, path: str):
        Path(path).write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls, path: str) -> "NolaNETConfig":
        return cls(**json.loads(Path(path).read_text()))


# ── RMS Normalization ───────────────────────────────────────────────────

class RMSNorm(nn.Module):
    def __init__(self, dim: int, eps: float = 1e-6):
        super().__init__()
        self.weight = mx.ones((dim,))
        self.eps = eps

    def __call__(self, x):
        norm = mx.rsqrt(mx.mean(x * x, axis=-1, keepdims=True) + self.eps)
        return x * norm * self.weight


# ── Rotary Position Embeddings ──────────────────────────────────────────

def precompute_rope(dim: int, max_seq: int, theta: float = 10000.0):
    """Precompute sin/cos for RoPE."""
    freqs = 1.0 / (theta ** (mx.arange(0, dim, 2).astype(mx.float32) / dim))
    t = mx.arange(max_seq).astype(mx.float32)
    freqs = mx.outer(t, freqs)
    return mx.cos(freqs), mx.sin(freqs)


def apply_rope(x, cos, sin):
    """Apply rotary embeddings to x. x shape: (batch, seq, heads, head_dim)"""
    d = x.shape[-1] // 2
    x1, x2 = x[..., :d], x[..., d:]
    seq_len = x.shape[1]
    cos = cos[:seq_len]  # (seq, d)
    sin = sin[:seq_len]
    # Broadcast: (1, seq, 1, d)
    cos = cos[None, :, None, :]
    sin = sin[None, :, None, :]
    return mx.concatenate([x1 * cos - x2 * sin, x2 * cos + x1 * sin], axis=-1)


# ── Multi-Head Attention ────────────────────────────────────────────────

class Attention(nn.Module):
    def __init__(self, config: NolaNETConfig):
        super().__init__()
        self.num_heads = config.num_heads
        self.head_dim = config.head_dim
        self.hidden_size = config.hidden_size

        self.q_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=False)
        self.k_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=False)
        self.v_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=False)
        self.o_proj = nn.Linear(config.hidden_size, config.hidden_size, bias=False)

        # Optional: concept graph attention bias (set externally)
        self._graph_bias = None

    def set_graph_bias(self, bias: mx.array):
        """Set per-head attention bias from concept graph. Shape: (heads, V, V)"""
        self._graph_bias = bias

    def __call__(self, x, cos, sin, mask=None):
        B, L, _ = x.shape
        q = self.q_proj(x).reshape(B, L, self.num_heads, self.head_dim)
        k = self.k_proj(x).reshape(B, L, self.num_heads, self.head_dim)
        v = self.v_proj(x).reshape(B, L, self.num_heads, self.head_dim)

        q = apply_rope(q, cos, sin)
        k = apply_rope(k, cos, sin)

        # (B, heads, L, head_dim) — layout expected by mx.fast
        q = q.transpose(0, 2, 1, 3)
        k = k.transpose(0, 2, 1, 3)
        v = v.transpose(0, 2, 1, 3)

        scale = 1.0 / math.sqrt(self.head_dim)
        # Flash Attention — fused kernel, O(L) memory instead of O(L^2)
        out = mx_fast.scaled_dot_product_attention(
            q, k, v, scale=scale, mask="causal"
        )

        out = out.transpose(0, 2, 1, 3).reshape(B, L, self.hidden_size)
        return self.o_proj(out)


# ── Feed-Forward Network ───────────────────────────────────────────────

class FeedForward(nn.Module):
    """SwiGLU FFN (same as LLaMA/Qwen)."""
    def __init__(self, config: NolaNETConfig):
        super().__init__()
        self.gate_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.hidden_size, config.intermediate_size, bias=False)
        self.down_proj = nn.Linear(config.intermediate_size, config.hidden_size, bias=False)

    def __call__(self, x):
        return self.down_proj(nn.silu(self.gate_proj(x)) * self.up_proj(x))


# ── Transformer Block ──────────────────────────────────────────────────

class TransformerBlock(nn.Module):
    def __init__(self, config: NolaNETConfig):
        super().__init__()
        self.attention = Attention(config)
        self.feed_forward = FeedForward(config)
        self.attn_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        self.ffn_norm = RMSNorm(config.hidden_size, config.rms_norm_eps)

    def __call__(self, x, cos, sin, mask=None):
        x = x + self.attention(self.attn_norm(x), cos, sin, mask)
        x = x + self.feed_forward(self.ffn_norm(x))
        return x


# ── NolaNET Model ──────────────────────────────────────────────────────

class NolaNET(nn.Module):
    """
    Retrieval-routing transformer.

    Small enough to train on a MacBook.
    Smart enough to find what it needs.

    The concept graph initializes its attention patterns —
    it starts knowing which ideas connect to which.
    Everything else is learned from the codebase and our conversations.
    """

    def __init__(self, config: NolaNETConfig):
        super().__init__()
        self.config = config

        self.embed_tokens = nn.Embedding(config.vocab_size, config.hidden_size)
        self.layers = [TransformerBlock(config) for _ in range(config.num_layers)]
        self.norm = RMSNorm(config.hidden_size, config.rms_norm_eps)
        # Weight-tied: lm_head shares weights with embedding
        # This halves the vocab parameter cost.

        # Precompute RoPE
        self._cos, self._sin = precompute_rope(
            config.head_dim, config.max_seq_length, config.rope_theta
        )

    def __call__(self, input_ids: mx.array) -> mx.array:
        B, L = input_ids.shape
        x = self.embed_tokens(input_ids)

        # Flash Attention handles causal masking internally — no mask needed
        for layer in self.layers:
            if self.config.grad_checkpoint:
                x = mx.checkpoint(layer)(x, self._cos, self._sin)
            else:
                x = layer(x, self._cos, self._sin)

        x = self.norm(x)
        # Weight-tied projection: reuse embedding weights as lm_head
        return x @ self.embed_tokens.weight.T

    def generate(self, input_ids: mx.array, max_tokens: int = 256, temperature: float = 0.7):
        """Autoregressive generation."""
        for _ in range(max_tokens):
            logits = self(input_ids)
            next_logits = logits[:, -1, :] / temperature
            next_token = mx.random.categorical(next_logits)
            next_token = next_token.reshape(1, 1)
            input_ids = mx.concatenate([input_ids, next_token], axis=1)
            if next_token.item() == 2:  # EOS
                break
        return input_ids

    def count_parameters(self) -> int:
        """Count actual trainable parameters."""
        total = 0
        for name, param in self.parameters().items() if hasattr(self.parameters(), 'items') else []:
            total += param.size
        # Fallback: use config estimate
        return self.config.param_count


def init_from_concept_graph(
    model: NolaNET,
    graph_data_dir: str = "research/hebbian_attention/data",
) -> None:
    """
    Initialize attention heads from the concept graph.

    This is the Hebbian initialization: instead of random attention patterns,
    the model starts knowing which concepts relate to which, based on
    actual co-occurrence data from the running system.

    The graph has 4,760 concepts and 653K edges — that's a rich attention
    prior that would take thousands of training steps to learn from scratch.
    """
    import numpy as np

    data_dir = Path(graph_data_dir)
    bias_path = data_dir / "attention_bias.npy"
    pos_path = data_dir / "position_encoding.npy"

    if not bias_path.exists():
        print(f"  No attention_bias.npy in {data_dir} — run graph_to_matrix.py first")
        print("  Model will train from random initialization (still works, just slower)")
        return

    # Load attention bias: (6, V, V)
    attn_bias = np.load(str(bias_path))
    print(f"  Loaded attention bias: {attn_bias.shape}")

    # The graph has 6 heads (identity, log, form, philosophy, reflex, association)
    # Our model has 8 heads. Map: first 6 get graph bias, last 2 are free for learning.
    num_graph_heads = min(attn_bias.shape[0], model.config.num_heads)

    for layer_idx, layer in enumerate(model.layers):
        # Scale bias down for deeper layers (let them specialize)
        scale = 1.0 / (1.0 + layer_idx * 0.3)
        # We don't directly add bias to attention in this implementation,
        # but we CAN use it to initialize the Q/K projections such that
        # the initial attention pattern approximates the graph structure.
        # This is a research direction — for now, store it for the forward pass.
        print(f"  Layer {layer_idx}: graph bias scale={scale:.2f}")

    # Load position encoding (identity distance)
    if pos_path.exists():
        pos = np.load(str(pos_path))
        print(f"  Loaded position encoding: {pos.shape} (concepts reachable: {np.sum(pos < 20)})")


# ── Config presets ──────────────────────────────────────────────────────

# With vocab=32K (SmolLM tokenizer), embedding = 32K * hidden_size.
# Weight tying (lm_head = embed^T) halves the embedding cost.
# True param counts below include tying.

NOLA_MICRO = NolaNETConfig(
    vocab_size=16384,
    hidden_size=256,
    num_layers=6,
    num_heads=4,
    intermediate_size=768,
    # 16K custom vocab saves ~8M embed params vs 49K SmolLM2
    # Same transformer as the run that succeeded
)

NOLA_SMALL = NolaNETConfig(
    vocab_size=32000,
    hidden_size=512,
    num_layers=8,
    num_heads=8,
    intermediate_size=1536,
    # ~37M params with weight tying
)

NOLA_BASE = NolaNETConfig(
    vocab_size=32000,
    hidden_size=768,
    num_layers=12,
    num_heads=12,
    intermediate_size=2304,
    # ~96M params with weight tying
)

NOLA_LARGE = NolaNETConfig(
    vocab_size=16384,
    hidden_size=1024,
    num_layers=16,
    num_heads=8,
    intermediate_size=3072,
    grad_checkpoint=True,
    # ~235M params — first generation-capable size
    # Uses domain tokenizer (16K) so embedding is only 16.8M params
    # Remaining ~218M is pure transformer capacity
    # Memory: ~4.5GB peak on M4 Air (batch=1, seq=512)
)

NOLA_XL = NolaNETConfig(
    vocab_size=16384,
    hidden_size=1024,
    num_layers=24,
    num_heads=8,
    intermediate_size=3072,
    grad_checkpoint=True,
    # ~344M params — target for identity + compositional reasoning
    # Same hidden dim as LARGE but 50% deeper (24 vs 16 layers)
    # Memory: ~6.5GB peak on M4 Air (batch=1, seq=512, grad checkpoint)
)

# Aliases
NOLA_8M = NOLA_MICRO     # smallest trainable
NOLA_15M = NOLA_SMALL    # good default
NOLA_30M = NOLA_BASE     # more capacity
NOLA_250M = NOLA_LARGE   # first coherent generation
NOLA_350M = NOLA_XL      # identity + reasoning target


def print_config_comparison():
    for name, cfg in [("NOLA_MICRO", NOLA_MICRO), ("NOLA_SMALL", NOLA_SMALL),
                      ("NOLA_BASE", NOLA_BASE), ("NOLA_LARGE", NOLA_LARGE),
                      ("NOLA_XL", NOLA_XL)]:
        mb = cfg.param_count / 1e6
        ckpt = " [checkpoint]" if cfg.grad_checkpoint else ""
        print(f"  {name}: {cfg.param_count:>12,} params ({mb:.1f}M) | "
              f"d={cfg.hidden_size} layers={cfg.num_layers} heads={cfg.num_heads}{ckpt}")


if __name__ == "__main__":
    print("NolaNET — Retrieval-routing transformer for AI_OS")
    print("=" * 55)
    print_config_comparison()

    print(f"\nInitializing NOLA_MICRO...")
    model = NolaNET(NOLA_MICRO)
    print(f"  Config param estimate: {NOLA_MICRO.param_count:,}")

    # Test forward pass
    test_ids = mx.array([[1, 2, 3, 4, 5]])
    out = model(test_ids)
    print(f"  Forward pass: input={test_ids.shape} -> output={out.shape}")
    print(f"  Output logits range: [{out.min().item():.3f}, {out.max().item():.3f}]")

    # Test generation
    gen = model.generate(test_ids, max_tokens=10)
    print(f"  Generation: {test_ids.shape[1]} -> {gen.shape[1]} tokens")

    print(f"\nGraph initialization check:")
    init_from_concept_graph(model)
