#!/usr/bin/env python3
"""
Build a custom BPE tokenizer trained on the AI_OS codebase.

Why: The SmolLM2 tokenizer has 49,152 tokens. Most are irrelevant
(Chinese, Arabic, medical terms). Our model wastes 12.6M params on a
lookup table for tokens it never sees.

A custom 8K tokenizer:
  - Makes `linking_core`, `get_state`, `concept_graph` single tokens
  - Frees ~10M params for actual transformer capacity
  - Compresses our text ~30% better (more context per sequence)

Output: experiments/tokenizer/  (tokenizer.json + vocab files)
"""
import os
import json
import tempfile
from pathlib import Path

from tokenizers import Tokenizer, models, trainers, pre_tokenizers, decoders, processors

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "tokenizer"
OUT_DIR.mkdir(exist_ok=True)

VOCAB_SIZE = 16384

# Special tokens — order matters (IDs are assigned sequentially)
SPECIAL_TOKENS = [
    "<pad>",        # 0
    "<bos>",        # 1
    "<eos>",        # 2
    "<unk>",        # 3
    "<|user|>",     # 4
    "<|assistant|>",# 5
    "<|system|>",   # 6
    "<|STATE|>",    # 7
    "<|TOOL|>",     # 8
]


def collect_training_text():
    """Gather all text the tokenizer should learn from."""
    texts = []

    # 1. Python source files
    for root, dirs, files in os.walk(str(ROOT)):
        dirs[:] = [d for d in dirs if d not in {
            ".venv", "node_modules", "__pycache__", ".git",
            "runs", "assets", "research", ".mypy_cache",
        }]
        for fname in files:
            if not fname.endswith((".py", ".md", ".ts", ".tsx", ".json", ".yaml", ".yml")):
                continue
            fpath = os.path.join(root, fname)
            try:
                text = open(fpath).read()
            except Exception:
                continue
            if len(text) < 50:
                continue
            # Skip huge files (e.g. package-lock)
            if len(text) > 500_000:
                continue
            texts.append(text)

    # 2. Conversation files
    convo_dir = ROOT / "Feeds" / "conversations"
    if convo_dir.exists():
        for fname in sorted(os.listdir(convo_dir)):
            if not fname.endswith(".json"):
                continue
            fpath = convo_dir / fname
            try:
                data = json.loads(fpath.read_text())
            except Exception:
                continue
            for turn in data.get("turns", []):
                user = turn.get("user", "").strip()
                assistant = turn.get("assistant", "").strip()
                if user:
                    texts.append(user)
                if assistant:
                    texts.append(assistant)

    # 3. Training data
    for fname in (ROOT / "finetune").glob("*.jsonl"):
        try:
            for line in open(fname):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if "messages" in obj:
                    for m in obj["messages"]:
                        c = m.get("content", "")
                        if c:
                            texts.append(c)
                elif "text" in obj:
                    texts.append(obj["text"])
        except Exception:
            continue

    # 4. Self-SFT data
    sft_dir = ROOT / "experiments" / "self_sft"
    for sft_file in sft_dir.glob("*.jsonl"):
        try:
            for line in open(sft_file):
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                for m in obj.get("messages", []):
                    c = m.get("content", "")
                    if c:
                        texts.append(c)
        except Exception:
            continue

    return texts


def train_tokenizer(texts):
    """Train a BPE tokenizer on the collected texts."""
    tokenizer = Tokenizer(models.BPE(unk_token="<unk>"))

    # Pre-tokenizer: split on whitespace + punctuation (like GPT-2 style)
    tokenizer.pre_tokenizer = pre_tokenizers.ByteLevel(add_prefix_space=False)
    tokenizer.decoder = decoders.ByteLevel()

    trainer = trainers.BpeTrainer(
        vocab_size=VOCAB_SIZE,
        special_tokens=SPECIAL_TOKENS,
        min_frequency=2,
        show_progress=True,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(),
    )

    # Write texts to temp files (tokenizers library reads from files)
    tmp_dir = tempfile.mkdtemp()
    tmp_files = []
    chunk_size = 1000
    for i in range(0, len(texts), chunk_size):
        chunk = texts[i:i + chunk_size]
        tmp_path = os.path.join(tmp_dir, f"chunk_{i // chunk_size}.txt")
        with open(tmp_path, "w") as f:
            f.write("\n".join(chunk))
        tmp_files.append(tmp_path)

    print(f"Training BPE tokenizer on {len(texts)} text segments...")
    print(f"  Target vocab: {VOCAB_SIZE}")
    print(f"  Special tokens: {len(SPECIAL_TOKENS)}")

    tokenizer.train(tmp_files, trainer)

    # Add post-processor for BOS/EOS
    tokenizer.post_processor = processors.ByteLevel(trim_offsets=False)

    # Clean up
    for f in tmp_files:
        os.unlink(f)
    os.rmdir(tmp_dir)

    return tokenizer


def analyze_tokenizer(tokenizer, texts):
    """Show what the tokenizer learned."""
    vocab = tokenizer.get_vocab()
    print(f"\nTokenizer stats:")
    print(f"  Vocab size: {len(vocab)}")

    # Test encoding of key terms
    test_terms = [
        "linking_core", "concept_graph", "get_state", "spread_activate",
        "identity_thread", "orchestrator", "schema_drift", "unified_events",
        "def __call__(self, x):", "from agent.subconscious import",
        "<|user|>\nWhat is STATE?\n<|assistant|>\n",
        "self.embed_tokens", "mx.array", "train_phase",
    ]

    print(f"\n  Token efficiency (fewer = better):")
    for term in test_terms:
        encoded = tokenizer.encode(term)
        tokens = encoded.tokens
        print(f"    {term[:40]:40s} → {len(tokens):2d} tokens: {tokens}")

    # Compression ratio on sample text
    total_chars = sum(len(t) for t in texts[:500])
    total_tokens = sum(len(tokenizer.encode(t).ids) for t in texts[:500])
    ratio = total_chars / total_tokens if total_tokens else 0
    print(f"\n  Compression: {ratio:.1f} chars/token (GPT-2 ≈ 3.7, good custom ≈ 4.5+)")


def main():
    print("Building AI_OS custom tokenizer")
    print(f"  Output: {OUT_DIR}")
    print()

    texts = collect_training_text()
    print(f"  Collected {len(texts)} text segments")

    tokenizer = train_tokenizer(texts)
    analyze_tokenizer(tokenizer, texts)

    # Save
    tokenizer_path = str(OUT_DIR / "tokenizer.json")
    tokenizer.save(tokenizer_path)
    print(f"\n  Saved tokenizer to {tokenizer_path}")

    # Also save vocab for inspection
    vocab = tokenizer.get_vocab()
    sorted_vocab = sorted(vocab.items(), key=lambda x: x[1])
    with open(OUT_DIR / "vocab.txt", "w") as f:
        for token, idx in sorted_vocab:
            f.write(f"{idx:>6d}  {repr(token)}\n")
    print(f"  Saved vocab.txt ({len(vocab)} entries)")

    return tokenizer


if __name__ == "__main__":
    main()
