"""Count tokens across all data sources for pretraining estimate."""
import json, os, glob
from pathlib import Path

def count_words_in_files(pattern, exclude=None):
    total = 0
    for f in glob.glob(pattern, recursive=True):
        if exclude and any(e in f for e in exclude):
            continue
        try:
            with open(f) as fh:
                total += len(fh.read().split())
        except:
            pass
    return total

def count_jsonl_content(path):
    total = 0
    for line in open(path):
        obj = json.loads(line)
        for msg in obj.get("messages", []):
            total += len(msg.get("content", "").split())
    return total

os.chdir(Path(__file__).resolve().parent.parent)

# Source 1: Raw codebase
code_words = count_words_in_files("./**/*.py", exclude=[".venv", "node_modules", ".git"])
code_words += count_words_in_files("./**/*.ts", exclude=[".venv", "node_modules", ".git"])
code_words += count_words_in_files("./**/*.tsx", exclude=[".venv", "node_modules", ".git"])
code_words += count_words_in_files("./**/*.md", exclude=[".venv", "node_modules", ".git"])
code_words += count_words_in_files("./**/*.js", exclude=[".venv", "node_modules", ".git"])

# Source 2: Conversation chunks (text content only)
convo_words = count_jsonl_content("finetune/convo_chunks/train.jsonl")
convo_words += count_jsonl_content("finetune/convo_chunks/valid.jsonl")

# Source 3: System knowledge JSONL
sys_words = count_jsonl_content("finetune/train.jsonl")
sys_words += count_jsonl_content("finetune/valid.jsonl")

# Source 4: Raw conversation JSON files
raw_convo_words = count_words_in_files("Feeds/conversations/**/*.json")

# Token ratio: code ~1.5 tokens/word, English ~1.3 tokens/word
code_tokens = int(code_words * 1.5)
convo_tokens = int(convo_words * 1.3)
sys_tokens = int(sys_words * 1.3)
raw_tokens = int(raw_convo_words * 1.3)

print("=" * 60)
print("  PRETRAINING TOKEN BUDGET")
print("=" * 60)
print(f"  Codebase (.py/.ts/.md/.js):  {code_words:>10,} words  ~{code_tokens:>10,} tokens")
print(f"  Conversation chunks:         {convo_words:>10,} words  ~{convo_tokens:>10,} tokens")
print(f"  System knowledge JSONL:      {sys_words:>10,} words  ~{sys_tokens:>10,} tokens")
print(f"  Raw conversation files:      {raw_convo_words:>10,} words  ~{raw_tokens:>10,} tokens")
print("-" * 60)

# For pretraining you'd use: raw code + raw conversations (not JSONL-formatted)
pretrain_tokens = code_tokens + raw_tokens
print(f"  PRETRAIN TOTAL (code+raw):   {code_words+raw_convo_words:>10,} words  ~{pretrain_tokens:>10,} tokens")
print()

# Chinchilla optimal
print("  SCALING CONTEXT:")
print(f"  120M model Chinchilla-optimal: ~2,400,000,000 tokens (2.4B)")
print(f"  We have:                       ~{pretrain_tokens:>13,} tokens")
print(f"  Ratio:                         {pretrain_tokens/2_400_000_000:.4f}x of optimal")
print(f"  Epochs needed for optimal:     {2_400_000_000/pretrain_tokens:.0f}x over data")
print()
print("  TinyStories reference: coherent English from 1M params on ~470M tokens")
print(f"  Our data at 10 epochs:         ~{pretrain_tokens*10:,} tokens seen")
print(f"  Our data at 50 epochs:         ~{pretrain_tokens*50:,} tokens seen")
