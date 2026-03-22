"""
Export ALL AI_OS content as raw text for continued pretraining.

Outputs: {"text": "..."} JSONL format for mlx_lm --text-feature text

Sources:
  1. All Python source files (.py)
  2. All TypeScript/JS source files (.ts, .tsx, .js)
  3. All Markdown documentation (.md)
  4. All conversation data (imported VS Code sessions)
  5. All JSONL training data (system knowledge, curated pairs)

Excludes:
  - .venv/, node_modules/, .git/, __pycache__/
  - Binary files, images, .safetensors
  - 3 personal conversations (hardcoded UUIDs)
"""

import json
import os
import glob
import random
import argparse
from pathlib import Path

ROOT = Path(__file__).parent.parent  # AI_OS root

# Personal conversations to exclude
EXCLUDE_IDS = {
    "a4bd5e26",  # relationship issues
    "8858ad09",  # legal documents
    "bbfb2a1f",  # DARVO detection
}

SKIP_DIRS = {".venv", "node_modules", ".git", "__pycache__", ".next", "dist", "build"}
SKIP_FILES = {".safetensors", ".whl", ".pyc", ".pyo", ".so", ".dylib", ".dmg",
              ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".ttf",
              ".lock", ".map"}

# Max chunk size in characters (~2048 tokens ≈ ~8000 chars)
MAX_CHUNK_CHARS = 8000


def should_skip(path: Path) -> bool:
    """Skip binary files, venvs, node_modules, etc."""
    parts = path.parts
    if any(d in parts for d in SKIP_DIRS):
        return True
    if path.suffix.lower() in SKIP_FILES:
        return True
    return False


def read_safe(path: Path) -> str:
    """Read file, skip binary."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split long text into chunks, breaking at newlines."""
    if len(text) <= max_chars:
        return [text] if text.strip() else []

    chunks = []
    lines = text.split("\n")
    current = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len

    if current:
        chunk = "\n".join(current)
        if chunk.strip():
            chunks.append(chunk)

    return chunks


def export_source_files() -> list[str]:
    """Export all source code and documentation files as text chunks."""
    extensions = {".py", ".ts", ".tsx", ".js", ".md", ".yaml", ".yml", ".toml",
                  ".json", ".sh", ".sql", ".html", ".css"}
    texts = []

    for ext in extensions:
        for path in ROOT.rglob(f"*{ext}"):
            if should_skip(path):
                continue
            # Skip large generated files
            if path.stat().st_size > 500_000:
                continue
            # Skip JSONL training data (we'll handle that separately)
            if path.suffix == ".jsonl":
                continue

            content = read_safe(path)
            if not content.strip():
                continue

            rel = path.relative_to(ROOT)
            # Add file path as header so model learns file structure
            header = f"# File: {rel}\n\n"
            full_text = header + content

            for chunk in chunk_text(full_text):
                texts.append(chunk)

    return texts


def export_conversations() -> list[str]:
    """Export all VS Code conversation data as raw text."""
    convo_dir = ROOT / "Feeds" / "conversations"
    if not convo_dir.exists():
        return []

    texts = []
    for path in sorted(convo_dir.rglob("*.json")):
        # Check exclusion
        if any(eid in path.stem for eid in EXCLUDE_IDS):
            continue

        try:
            data = json.loads(path.read_text())
        except Exception:
            continue

        # Skip ChatGPT imports
        snapshot = data.get("state_snapshot", {})
        if snapshot.get("imported_from") == "ChatGPT":
            continue

        name = data.get("name", "untitled")
        turns = data.get("turns", [])
        if not turns:
            continue

        # Build conversation as natural text
        lines = [f"# Conversation: {name}\n"]
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            if not content.strip():
                continue
            lines.append(f"[{role}]: {content}\n")

        full_text = "\n".join(lines)
        for chunk in chunk_text(full_text):
            texts.append(chunk)

    return texts


def export_training_jsonl() -> list[str]:
    """Export existing JSONL training data as raw text (flatten messages)."""
    texts = []
    jsonl_files = [
        ROOT / "finetune" / "train.jsonl",
        ROOT / "finetune" / "valid.jsonl",
    ]
    # Also include curated pairs
    pairs_dir = ROOT / "finetune" / "readme_pairs"
    if pairs_dir.exists():
        jsonl_files.extend(sorted(pairs_dir.glob("*.jsonl")))

    for jf in jsonl_files:
        if not jf.exists():
            continue
        for line in jf.open():
            try:
                obj = json.loads(line)
            except Exception:
                continue

            messages = obj.get("messages", [])
            if not messages:
                continue

            # Flatten to text
            parts = []
            for msg in messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if content.strip():
                    parts.append(f"[{role}]: {content}")

            text = "\n\n".join(parts)
            for chunk in chunk_text(text):
                texts.append(chunk)

    return texts


def main():
    parser = argparse.ArgumentParser(description="Export AI_OS as raw text for pretraining")
    parser.add_argument("--output", default=str(ROOT / "finetune" / "pretrain_data"),
                        help="Output directory")
    parser.add_argument("--split", type=float, default=0.95,
                        help="Train/valid split ratio")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Exporting source files...")
    source_texts = export_source_files()
    print(f"  {len(source_texts)} chunks from source files")

    print("Exporting conversations...")
    convo_texts = export_conversations()
    print(f"  {len(convo_texts)} chunks from conversations")

    print("Exporting training JSONL...")
    jsonl_texts = export_training_jsonl()
    print(f"  {len(jsonl_texts)} chunks from JSONL data")

    # Combine all
    all_texts = source_texts + convo_texts + jsonl_texts
    random.shuffle(all_texts)

    # Stats
    total_chars = sum(len(t) for t in all_texts)
    est_tokens = int(total_chars / 4)  # ~4 chars per token average
    print(f"\nTotal: {len(all_texts)} chunks, ~{total_chars:,} chars, ~{est_tokens:,} tokens (est)")

    # Split
    split_idx = int(len(all_texts) * args.split)
    train = all_texts[:split_idx]
    valid = all_texts[split_idx:]

    # Write
    train_path = out_dir / "train.jsonl"
    valid_path = out_dir / "valid.jsonl"

    with open(train_path, "w") as f:
        for text in train:
            f.write(json.dumps({"text": text}) + "\n")

    with open(valid_path, "w") as f:
        for text in valid:
            f.write(json.dumps({"text": text}) + "\n")

    print(f"\nWritten:")
    print(f"  {train_path}: {len(train)} examples")
    print(f"  {valid_path}: {len(valid)} examples")
    print(f"\nPretrain data ready. Next steps:")
    print(f"  1. Download model:  python3 -c \"from huggingface_hub import snapshot_download; snapshot_download('mlx-community/SmolLM2-135M')\"")
    print(f"  2. Run pretrain:    python3 -m mlx_lm lora --model mlx-community/SmolLM2-135M --data {out_dir} --train --fine-tune-type full --text-feature text --iters 2500 --learning-rate 5e-5 --batch-size 4 --max-seq-length 2048 --save-every 500 --steps-per-eval 500 --steps-per-report 50 --adapter-path {out_dir}/weights --seed 42")
    print(f"  3. Fuse model:      python3 -m mlx_lm fuse --model mlx-community/SmolLM2-135M --adapter-path {out_dir}/weights")
    print(f"  4. SFT on fused:    (use existing train.jsonl with messages format)")


if __name__ == "__main__":
    main()
