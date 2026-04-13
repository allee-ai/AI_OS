"""
Train NolaNET from scratch on AI_OS data.

Three-phase training on a single machine:
  Phase 1 (REPEAT):      Raw codebase text — learn the token distribution
  Phase 2 (UNDERSTAND):  Self-SFT — learn to talk about itself (our conversations)
  Phase 3 (ROUTE):       Retrieval routing — learn when to look up vs synthesize

Uses MLX for Apple Silicon native training.
Memory-efficient: streams batches one at a time, gradient accumulation.
"""
import gc
import json
import math
import os
import time
from pathlib import Path
from typing import Optional

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np

import mlx.utils

from nola_net import (
    NolaNET, NolaNETConfig, NOLA_MICRO, NOLA_SMALL, NOLA_BASE,
    NOLA_LARGE, NOLA_XL, NOLA_8M, NOLA_15M, NOLA_30M,
    NOLA_250M, NOLA_350M, init_from_concept_graph, print_config_comparison,
)

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = Path(__file__).resolve().parent / "runs"


# ── Memory & Safety Utilities ───────────────────────────────────────────

def _memory_str() -> str:
    """Get Metal memory usage string for logging."""
    try:
        active = mx.get_active_memory() / 1e9
        peak = mx.get_peak_memory() / 1e9
        return f" | Mem: {active:.1f}GB (peak {peak:.1f}GB)"
    except (AttributeError, Exception):
        try:
            active = mx.metal.get_active_memory() / 1e9
            peak = mx.metal.get_peak_memory() / 1e9
            return f" | Mem: {active:.1f}GB (peak {peak:.1f}GB)"
        except (AttributeError, Exception):
            return ""


def _report_memory(label: str = ""):
    """Print current memory usage."""
    try:
        active = mx.get_active_memory() / 1e9
        peak = mx.get_peak_memory() / 1e9
        cache = mx.get_cache_memory() / 1e9
    except (AttributeError, Exception):
        try:
            active = mx.metal.get_active_memory() / 1e9
            peak = mx.metal.get_peak_memory() / 1e9
            cache = mx.metal.get_cache_memory() / 1e9
        except (AttributeError, Exception):
            return
    print(f"  Memory{' (' + label + ')' if label else ''}: "
          f"active={active:.2f}GB, peak={peak:.2f}GB, cache={cache:.2f}GB")


def _clip_grad_norm(grads, max_norm: float = 1.0):
    """Clip gradient L2 norm to prevent training explosion."""
    flat = mlx.utils.tree_flatten(grads)
    total_sq = sum(mx.sum(g * g).item() for _, g in flat)
    total_norm = total_sq ** 0.5
    if total_norm > max_norm:
        scale = max_norm / (total_norm + 1e-8)
        grads = mlx.utils.tree_map(lambda g: g * scale, grads)
    return grads


def _dry_run(model: NolaNET, tokenizer, max_seq: int = 512):
    """Run a single forward+backward pass to verify memory fits."""
    print(f"\n  Dry run: verifying memory with seq_len={max_seq}...")
    try:
        mx.reset_peak_memory()
    except (AttributeError, Exception):
        try:
            mx.metal.reset_peak_memory()
        except (AttributeError, Exception):
            pass

    # Create dummy batch
    dummy_ids = mx.array([[1] * max_seq])
    loss_fn = nn.value_and_grad(model, cross_entropy_loss)

    try:
        loss, grads = loss_fn(model, dummy_ids)
        mx.eval(loss, grads)
        print(f"  Dry run forward+backward OK — loss: {loss.item():.4f}")
        _report_memory("after dry run")

        # Check if we're using too much memory
        try:
            peak_gb = mx.get_peak_memory() / 1e9
        except (AttributeError, Exception):
            try:
                peak_gb = mx.metal.get_peak_memory() / 1e9
            except (AttributeError, Exception):
                peak_gb = None

        if peak_gb is not None:
            if peak_gb > 12.0:
                print(f"  ⚠  Peak memory {peak_gb:.1f}GB is high for 16GB machine.")
                print(f"     Consider: --size 250m or reducing --max-seq")
                return False
            elif peak_gb > 8.0:
                print(f"  ⚠  Peak memory {peak_gb:.1f}GB — should fit but monitor closely.")
            else:
                print(f"  ✓  Peak memory {peak_gb:.1f}GB — safe margin on 16GB.")
        else:
            print(f"  ✓  Dry run passed (memory tracking unavailable).")

    except Exception as e:
        print(f"  ✗  Dry run FAILED: {e}")
        print(f"     This model+seq_len will crash during training.")
        print(f"     Try: --size 250m or smaller --max-seq")
        return False

    # Cleanup
    del loss, grads, dummy_ids, loss_fn
    gc.collect()
    return True


def load_sft_file(filepath: str, tokenizer, max_seq: int = 512):
    """Load SFT examples from a single .jsonl file."""
    examples = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            messages = obj.get("messages", [])
            if not messages:
                continue
            text = ""
            for m in messages:
                role = m.get("role", "user")
                content = m.get("content", "")
                if role == "system":
                    text += f"<|system|>\n{content}\n"
                elif role == "user":
                    text += f"<|user|>\n{content}\n"
                elif role == "assistant":
                    text += f"<|assistant|>\n{content}\n"
            ids = tokenizer.encode(text, truncation=True, max_length=max_seq)
            if len(ids) >= 16:
                examples.append(ids)
    return examples


# ── Tokenizer ───────────────────────────────────────────────────────────
# We use the SmolLM2 tokenizer for now (same vocab, proven BPE).
# A custom tokenizer trained on the codebase is a future step —
# it would compress Python/JSON tokens better, but the gains are
# marginal for a retrieval model that mostly sees structured context.

def get_tokenizer(custom_path=None):
    """Load tokenizer. Prefers custom AI_OS tokenizer, falls back to SmolLM2."""
    # Try custom tokenizer first
    if custom_path is None:
        custom_path = Path(__file__).resolve().parent / "tokenizer" / "tokenizer.json"
    if Path(custom_path).exists():
        from tokenizers import Tokenizer as HFTokenizer

        class CustomTokenizer:
            def __init__(self, path):
                self._tok = HFTokenizer.from_file(str(path))
                self._tok.enable_padding(pad_id=0, pad_token="<pad>")
                self._tok.enable_truncation(max_length=2048)
                self.pad_token_id = 0
                self.eos_token_id = 2

            def encode(self, text, truncation=True, max_length=2048):
                self._tok.enable_truncation(max_length=max_length)
                return self._tok.encode(text).ids

            def decode(self, ids):
                return self._tok.decode(ids, skip_special_tokens=False)

            def __len__(self):
                return self._tok.get_vocab_size()

        tok = CustomTokenizer(custom_path)
        print(f"  Using custom AI_OS tokenizer ({len(tok)} tokens)")
        return tok

    # Fallback to SmolLM2
    try:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained("HuggingFaceTB/SmolLM2-135M")
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        print(f"  Using SmolLM2 tokenizer ({len(tok)} tokens)")
        return tok
    except Exception:
        raise ImportError(
            "Need tokenizers or transformers: pip install tokenizers transformers"
        )


# ── Data Loading ────────────────────────────────────────────────────────

def load_pretrain_data(data_dir: str, tokenizer, max_seq: int = 512):
    """Load Layer 1 pretrain data (raw text chunks). Returns Python lists (not mx arrays)."""
    path = Path(data_dir)
    examples = []
    for split in ["train.jsonl", "valid.jsonl"]:
        fp = path / split
        if not fp.exists():
            continue
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                text = obj.get("text", "")
                if not text:
                    continue
                ids = tokenizer.encode(text, truncation=True, max_length=max_seq)
                if len(ids) >= 16:
                    examples.append(ids)
    return examples


def load_sft_data(data_dir: str, tokenizer, max_seq: int = 512):
    """Load SFT data (message format). Returns Python lists."""
    path = Path(data_dir)
    examples = []
    for split in ["train.jsonl", "valid.jsonl"]:
        fp = path / split
        if not fp.exists():
            continue
        with open(fp) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                messages = obj.get("messages", [])
                if not messages:
                    continue
                text = ""
                for m in messages:
                    role = m.get("role", "user")
                    content = m.get("content", "")
                    if role == "system":
                        text += f"<|system|>\n{content}\n"
                    elif role == "user":
                        text += f"<|user|>\n{content}\n"
                    elif role == "assistant":
                        text += f"<|assistant|>\n{content}\n"
                ids = tokenizer.encode(text, truncation=True, max_length=max_seq)
                if len(ids) >= 16:
                    examples.append(ids)
    return examples


def iter_batches(examples, batch_size: int, max_seq: int):
    """Yield one padded batch at a time. Never holds all batches in RAM."""
    np.random.shuffle(examples)
    for i in range(0, len(examples), batch_size):
        batch = examples[i:i + batch_size]
        if not batch:
            continue
        max_len = min(max(len(s) for s in batch), max_seq)
        padded = []
        for seq in batch:
            if len(seq) < max_len:
                seq = seq + [0] * (max_len - len(seq))
            else:
                seq = seq[:max_len]
            padded.append(seq)
        yield mx.array(padded)


# ── Loss ────────────────────────────────────────────────────────────────

def cross_entropy_loss(model: NolaNET, input_ids: mx.array):
    """Standard causal LM loss: predict next token."""
    logits = model(input_ids[:, :-1])
    targets = input_ids[:, 1:]
    # Flatten
    B, L, V = logits.shape
    logits = logits.reshape(-1, V)
    targets = targets.reshape(-1)
    # Mask padding (token 0)
    mask = targets != 0
    loss = nn.losses.cross_entropy(logits, targets, reduction="none")
    loss = (loss * mask).sum() / (mask.sum() + 1e-8)
    return loss


# ── Training Loop ───────────────────────────────────────────────────────

def train_phase(
    model: NolaNET,
    examples: list,
    phase_name: str,
    num_epochs: int = 3,
    batch_size: int = 1,
    accum_steps: int = 4,
    lr: float = 5e-4,
    max_seq: int = 512,
    warmup_steps: int = 50,
    log_every: int = 10,
    save_dir: Optional[str] = None,
    checkpoint_every: int = 2000,
):
    """Train with gradient accumulation. batch_size=1, accum=4 → effective batch 4."""
    print(f"\n{'='*60}")
    print(f"Phase: {phase_name}")
    print(f"  Examples: {len(examples)}")
    print(f"  Epochs: {num_epochs}, Micro-batch: {batch_size}, "
          f"Accum: {accum_steps}, Effective batch: {batch_size * accum_steps}, LR: {lr}")
    print(f"  Max seq: {max_seq}")
    print(f"{'='*60}\n")

    if not examples:
        print("  No data — skipping phase")
        return

    loss_and_grad = nn.value_and_grad(model, cross_entropy_loss)

    total_steps = num_epochs * (len(examples) // (batch_size * accum_steps) + 1)
    scheduler = optim.cosine_decay(lr, total_steps, lr * 0.01)
    optimizer = optim.Adam(learning_rate=scheduler)

    step = 0
    accum_loss = 0.0
    accum_count = 0
    losses = []
    t0 = time.time()
    total_tokens = 0

    for epoch in range(num_epochs):
        epoch_loss = 0.0
        epoch_batches = 0

        for batch_ids in iter_batches(examples, batch_size, max_seq):
            if step < warmup_steps:
                optimizer.learning_rate = lr * (step + 1) / warmup_steps

            loss, grads = loss_and_grad(model, batch_ids)

            accum_loss += loss.item()
            accum_count += 1
            total_tokens += batch_ids.size

            if accum_count >= accum_steps:
                clipped = _clip_grad_norm(grads, max_norm=1.0)
                optimizer.update(model, clipped)
                mx.eval(loss, model.parameters(), optimizer.state)

                avg_loss = accum_loss / accum_count
                epoch_loss += avg_loss
                epoch_batches += 1
                step += 1

                if step % log_every == 0:
                    elapsed = time.time() - t0
                    tps = total_tokens / elapsed if elapsed > 0 else 0
                    mem = _memory_str()
                    print(f"  Step {step:>5d} | Loss: {avg_loss:.4f} | "
                          f"Tok/s: {tps:.0f} | LR: {optimizer.learning_rate:.2e}{mem}")

                losses.append({"step": step, "loss": avg_loss, "epoch": epoch})
                accum_loss = 0.0
                accum_count = 0

                # Periodic checkpoint
                if save_dir and checkpoint_every > 0 and step % checkpoint_every == 0:
                    ckpt_path = Path(save_dir)
                    ckpt_path.mkdir(parents=True, exist_ok=True)
                    flat = dict(mlx.utils.tree_flatten(model.trainable_parameters()))
                    mx.save_safetensors(str(ckpt_path / "model.safetensors"), flat)
                    model.config.save(str(ckpt_path / "config.json"))
                    with open(ckpt_path / "train_log.json", "w") as f:
                        json.dump(losses, f)
                    print(f"  ✓ Checkpoint saved at step {step} → {ckpt_path}")

        avg = epoch_loss / max(epoch_batches, 1)
        print(f"  Epoch {epoch+1}/{num_epochs} — avg loss: {avg:.4f}")

    elapsed = time.time() - t0
    print(f"\n  Phase complete: {step} steps in {elapsed:.1f}s")
    print(f"  Total tokens processed: {total_tokens:,}")

    # Save checkpoint
    if save_dir:
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)
        weights_path = save_path / "model.safetensors"
        flat = dict(mlx.utils.tree_flatten(model.trainable_parameters()))
        mx.save_safetensors(str(weights_path), flat)
        model.config.save(str(save_path / "config.json"))
        with open(save_path / "train_log.json", "w") as f:
            json.dump(losses, f)
        print(f"  Saved to {save_path}")

    # Free gradient graph memory
    gc.collect()


# ── Full Pipeline ───────────────────────────────────────────────────────

def run_full_pipeline(
    config: NolaNETConfig = NOLA_8M,
    run_id: Optional[str] = None,
    dry_run: bool = False,
    max_seq_override: Optional[int] = None,
    phase2_only: bool = False,
    phase1_epochs_override: Optional[int] = None,
    phase2_epochs_override: Optional[int] = None,
    resume_from: Optional[str] = None,
):
    """
    Full three-phase training pipeline.

    Phase 1: Learn source code token distribution
    Phase 2: Learn self-knowledge from conversations
    Phase 3: (future) Learn retrieval routing
    """
    import uuid

    if run_id is None:
        run_id = str(uuid.uuid4())[:8]

    run_dir = RUNS_DIR / f"nola-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Size-aware training parameters
    param_m = config.param_count / 1e6
    if param_m > 200:
        # Large model: conservative settings
        MAX_SEQ = 1024
        phase1_lr = 1e-4
        phase1_epochs = 3
        phase2_lr = 5e-5
        phase2_epochs = 5
        accum_steps = 2  # less accumulation = less memory
    elif param_m > 50:
        # Medium model
        MAX_SEQ = 512
        phase1_lr = 3e-4
        phase1_epochs = 3
        phase2_lr = 1e-4
        phase2_epochs = 5
        accum_steps = 4
    else:
        # Small model: existing defaults
        MAX_SEQ = 512
        phase1_lr = 5e-4
        phase1_epochs = 3
        phase2_lr = 2e-4
        phase2_epochs = 5
        accum_steps = 4

    if phase1_epochs_override is not None:
        phase1_epochs = phase1_epochs_override

    if phase2_epochs_override is not None:
        phase2_epochs = phase2_epochs_override

    if max_seq_override:
        MAX_SEQ = max_seq_override

    print(f"NolaNET Training Pipeline")
    print(f"  Run: {run_id}")
    print(f"  Config: {config.param_count:,} params ({config.param_count/1e6:.1f}M)")
    print(f"  Grad checkpoint: {config.grad_checkpoint}")
    print(f"  Max seq: {MAX_SEQ}, Phase 1 LR: {phase1_lr}, Phase 2 LR: {phase2_lr}")
    print(f"  Output: {run_dir}")

    # Initialize model
    print(f"\nInitializing model...")
    model = NolaNET(config)
    print(f"  {config.num_layers} layers, d={config.hidden_size}, "
          f"heads={config.num_heads}, FFN={config.intermediate_size}")

    # Hebbian initialization from concept graph
    print(f"\nHebbian attention initialization...")
    graph_dir = ROOT / "research" / "hebbian_attention" / "data"
    init_from_concept_graph(model, str(graph_dir))

    # Tokenizer
    print(f"\nLoading tokenizer...")
    tokenizer = get_tokenizer()
    config.vocab_size = len(tokenizer)
    print(f"  Vocab size: {config.vocab_size}")

    # Reinitialize model with correct vocab size if needed
    if config.vocab_size != 32000:
        print(f"  Reinitializing with vocab_size={config.vocab_size}")
        model = NolaNET(config)

    # Load checkpoint if resuming
    if resume_from:
        ckpt_path = Path(resume_from) / "model.safetensors"
        if ckpt_path.exists():
            print(f"\n  Loading checkpoint: {ckpt_path}")
            weights = mx.load(str(ckpt_path))
            model.load_weights(list(weights.items()))
            print(f"  Loaded {len(weights)} weight tensors")
        else:
            print(f"  ⚠ Checkpoint not found: {ckpt_path}")

    # Cast to bfloat16 — halves memory, ~40-80% faster on Metal
    # (optimizer states stay float32 automatically, Flash Attention does softmax in float32)
    def _to_bf16(x):
        return x.astype(mx.bfloat16) if x.dtype == mx.float32 else x
    model.apply_to_modules(lambda k, m: m.apply(_to_bf16))
    mx.eval(model.parameters())
    print(f"  Model dtype: bfloat16")

    _report_memory("after model init")

    # ── Memory validation ───────────────────────────────────────────
    if not _dry_run(model, tokenizer, max_seq=MAX_SEQ):
        print("\nAborting: dry run failed. Reduce model size or max_seq.")
        return None, run_dir

    if dry_run:
        print("\nDry run complete. No training performed.")
        return model, run_dir

    # ── Phase 1: REPEAT (raw codebase) ──────────────────────────────
    pretrain_dir = run_dir / "pretrain_data"
    pretrain_dir.mkdir(exist_ok=True)

    # Check if pretrain data exists, build if not
    pretrain_data_src = None
    for candidate in [
        ROOT / "experiments" / "runs",  # look for existing run data
        ROOT / "finetune" / "pretrain_data",
    ]:
        if candidate.exists():
            # Find most recent pretrain data
            for sub in sorted(candidate.iterdir(), reverse=True):
                if (sub / "pretrain_data" / "train.jsonl").exists():
                    pretrain_data_src = sub / "pretrain_data"
                    break
                elif (sub / "train.jsonl").exists():
                    pretrain_data_src = sub
                    break
        if pretrain_data_src:
            break

    if pretrain_data_src:
        print(f"\n  Using existing pretrain data: {pretrain_data_src}")
        pretrain_examples = load_pretrain_data(str(pretrain_data_src), tokenizer, max_seq=MAX_SEQ)
    else:
        print(f"\n  Building pretrain data from codebase...")
        pretrain_examples = []
        for root_path, dirs, files in os.walk(str(ROOT)):
            dirs[:] = [d for d in dirs if d not in {
                ".venv", "node_modules", "__pycache__", ".git", "runs",
                "assets", "research",
            }]
            for fname in files:
                if not fname.endswith((".py", ".md", ".ts", ".tsx")):
                    continue
                fpath = os.path.join(root_path, fname)
                try:
                    text = open(fpath).read()
                except Exception:
                    continue
                if len(text) < 100:
                    continue
                # Chunk at ~512 token boundaries (~1500 chars)
                chunk_size = 1500
                for i in range(0, len(text), chunk_size):
                    chunk = text[i:i + chunk_size]
                    ids = tokenizer.encode(chunk, truncation=True, max_length=MAX_SEQ)
                    if len(ids) >= 32:
                        pretrain_examples.append(ids)

    print(f"  Pretrain examples: {len(pretrain_examples)}")

    if pretrain_examples and not phase2_only:
        train_phase(
            model, pretrain_examples,
            phase_name="Layer 1: REPEAT (codebase)",
            num_epochs=phase1_epochs,
            batch_size=1,
            accum_steps=accum_steps,
            lr=phase1_lr,
            max_seq=MAX_SEQ,
            save_dir=str(run_dir / "phase1_repeat"),
        )

    # Free pretrain data before loading SFT
    del pretrain_examples
    gc.collect()

    # ── Phase 2: UNDERSTAND (self-SFT from conversations) ──────────
    self_sft_dir = ROOT / "experiments" / "self_sft"
    sft_examples = []

    # Load original self-SFT data
    if (self_sft_dir / "train.jsonl").exists():
        convo_sft = load_sft_data(str(self_sft_dir), tokenizer, max_seq=MAX_SEQ)
        sft_examples.extend(convo_sft)
        print(f"  Self-SFT (original): {len(convo_sft)} examples")

    # Load mined conversation data
    convo_train = self_sft_dir / "convo_train.jsonl"
    if convo_train.exists():
        convo_mined = load_sft_file(str(convo_train), tokenizer, max_seq=MAX_SEQ)
        sft_examples.extend(convo_mined)
        print(f"  Conversation mining:  {len(convo_mined)} examples")

    # Load gold demo examples (10x oversampled — these are the target behavior)
    demo_gold = self_sft_dir / "demo_gold.jsonl"
    if demo_gold.exists():
        gold = load_sft_file(str(demo_gold), tokenizer, max_seq=MAX_SEQ)
        oversample = 10
        sft_examples.extend(gold * oversample)
        print(f"  Demo gold examples:   {len(gold)} x{oversample} = {len(gold)*oversample}")

    # Aggregate additional training data from finetune/
    extra_sft_files = [
        ROOT / "finetune" / "behavioral_train.jsonl",
        ROOT / "finetune" / "identity_train.jsonl",
        ROOT / "finetune" / "philosophy_train.jsonl",
        ROOT / "finetune" / "form_train.jsonl",
        ROOT / "finetune" / "reflex_train.jsonl",
        ROOT / "finetune" / "log_train.jsonl",
        ROOT / "finetune" / "linking_core_train.jsonl",
        ROOT / "finetune" / "docs_train.jsonl",
        ROOT / "finetune" / "reasoning_train.jsonl",
        ROOT / "finetune" / "chat_train.jsonl",
    ]

    # Also load readme_pairs and generated data
    readme_dir = ROOT / "finetune" / "readme_pairs"
    if readme_dir.exists():
        for jsonl_path in sorted(readme_dir.glob("*.jsonl")):
            extra_sft_files.append(jsonl_path)
    gen_dir = ROOT / "finetune" / "generated"
    if gen_dir.exists():
        for jsonl_path in sorted(gen_dir.glob("*.jsonl")):
            extra_sft_files.append(jsonl_path)

    for jsonl_path in extra_sft_files:
        if jsonl_path.exists():
            extra = load_sft_file(str(jsonl_path), tokenizer, max_seq=MAX_SEQ)
            if extra:
                sft_examples.extend(extra)
                print(f"    + {len(extra):>5d} from {jsonl_path.name}")

    print(f"  Total Phase 2 examples: {len(sft_examples)}")

    if sft_examples:
        train_phase(
            model, sft_examples,
            phase_name="Layer 2: UNDERSTAND (self-knowledge)",
            num_epochs=phase2_epochs,
            batch_size=1,
            accum_steps=accum_steps,
            lr=phase2_lr,
            max_seq=MAX_SEQ,
            save_dir=str(run_dir / "phase2_understand"),
        )

    del sft_examples
    gc.collect()

    # ── Save final model ────────────────────────────────────────────
    final_dir = run_dir / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    flat = dict(mlx.utils.tree_flatten(model.trainable_parameters()))
    mx.save_safetensors(str(final_dir / "model.safetensors"), flat)
    config.save(str(final_dir / "config.json"))

    print(f"\n{'='*60}")
    print(f"Training complete!")
    print(f"  Final model: {final_dir}")
    print(f"  Params: {config.param_count:,} ({config.param_count/1e6:.1f}M)")
    print(f"{'='*60}")

    return model, run_dir


# ── CLI ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train NolaNET from scratch")
    parser.add_argument("--size", choices=["8m", "15m", "30m", "250m", "350m"],
                        default="250m", help="Model size preset")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--phase1-only", action="store_true",
                        help="Only run Layer 1 pretraining")
    parser.add_argument("--phase2-only", action="store_true",
                        help="Skip Phase 1, go straight to SFT")
    parser.add_argument("--phase1-epochs", type=int, default=None,
                        help="Override Phase 1 epoch count (default: auto by size)")
    parser.add_argument("--phase2-epochs", type=int, default=None,
                        help="Override Phase 2 epoch count (default: auto by size)")
    parser.add_argument("--resume", type=str, default=None,
                        help="Path to checkpoint dir to resume from")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run one forward+backward pass then exit (memory check)")
    parser.add_argument("--max-seq", type=int, default=None,
                        help="Override max sequence length (default: auto by size)")
    parser.add_argument("--list-sizes", action="store_true",
                        help="Print all available model configs")
    args = parser.parse_args()

    if args.list_sizes:
        print("\nAvailable NolaNET configs:")
        print_config_comparison()
        raise SystemExit(0)

    configs = {
        "8m": NOLA_8M, "15m": NOLA_15M, "30m": NOLA_30M,
        "250m": NOLA_250M, "350m": NOLA_350M,
    }

    run_full_pipeline(
        config=configs[args.size],
        run_id=args.run_id,
        dry_run=args.dry_run,
        max_seq_override=args.max_seq,
        phase2_only=args.phase2_only,
        phase1_epochs_override=args.phase1_epochs,
        phase2_epochs_override=args.phase2_epochs,
        resume_from=args.resume,
    )
