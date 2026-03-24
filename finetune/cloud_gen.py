"""
Cloud Training Data Generator
==============================
Walks every def/class block in the codebase, round-robins across
free-tier cloud LLMs (Gemini, Claude, GPT, OpenRouter, Ollama),
and generates 5 conversational Q&A training examples per function.

Usage:
    python -m finetune.cloud_gen                     # Run all providers
    python -m finetune.cloud_gen --provider gemini   # Single provider
    python -m finetune.cloud_gen --dry-run            # Show what would be generated
    python -m finetune.cloud_gen --resume             # Skip already-generated files
    python -m finetune.cloud_gen --module identity    # Single module only
    python -m finetune.cloud_gen --file agent/agent.py  # Single file only

Environment variables:
    GEMINI_API_KEY        — Google AI Studio key (free tier: 15 RPM)
    ANTHROPIC_API_KEY     — Anthropic key (free tier via console)
    OPENAI_API_KEY        — OpenAI key
    OPENROUTER_API_KEY    — OpenRouter key (free models available)
    AIOS_CLOUD_GEN_MODEL  — Override model name per provider
    AIOS_CLOUD_GEN_DELAY  — Seconds between calls (default: 4)
"""

import ast
import json
import os
import sys
import time
import random
import hashlib
import argparse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = ROOT / "finetune" / "generated"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

# Track what's been generated to allow --resume
PROGRESS_FILE = GENERATED_DIR / ".cloud_gen_progress.json"

# ── Provider Layer (shared) ─────────────────────────────────
# All provider logic lives in agent.services.llm
# We import it here for discovery and calling.

from agent.services.llm import (
    get_provider,
    available_providers as _available_providers,
    generate as llm_generate,
    PROVIDER_CLASSES,
)


# ── System Prompt ───────────────────────────────────────────

SYSTEM_PROMPT = """You are generating conversational training data for a personal AI called Nola.
Nola is a Cognitive Operating System that runs on 6 threads: identity (WHO), philosophy (WHY),
log (WHEN), reflex (HOW), form (WHAT/tools), and linking_core (WHICH/relevance).

You will be given a Python function or class from Nola's codebase.
Generate exactly 5 conversational training examples as a JSON array.

Each example must have this structure:
{"messages": [{"role": "system", "content": "<STATE block>"}, {"role": "user", "content": "<question>"}, {"role": "assistant", "content": "<answer>"}]}

CRITICAL RULES:
1. The system content MUST start with "== STATE ==" and end with "== END STATE =="
   Include realistic thread sections: [self], [identity], [form], [log], etc.
2. Questions must be NATURAL — how a real user talks, not robotic
3. Answers must be FIRST PERSON as Nola: "I use...", "My system...", "That's handled by my..."
4. Answers must reference SPECIFIC details from the code: function names, variable names, logic
5. Mix question types:
   - "How does X work?" (architecture)
   - "What happens when Y?" (behavior)
   - "Why is Z designed that way?" (reasoning)
   - "Can you do X?" (capability)
   - Identity/adversarial: "Who are you?" → answer referencing the code's role
6. Answers: 80-250 words. Concise but show real understanding.
7. If the function relates to identity/memory/state, include at least one example where
   Nola demonstrates CONSULTING its STATE to answer (not just quoting a key, but reasoning)

Output ONLY a JSON array. No markdown fences. No explanation."""


# ── AST Code Extractor ─────────────────────────────────────

def extract_blocks(filepath: Path) -> List[Dict[str, str]]:
    """Extract all function and class definitions from a Python file."""
    try:
        source = filepath.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return []

    lines = source.splitlines()
    blocks = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            start = node.lineno - 1  # 0-indexed
            # Find end line
            end = node.end_lineno if hasattr(node, 'end_lineno') and node.end_lineno else start + 1
            code = "\n".join(lines[start:end])

            # Cap at ~3000 chars per block
            if len(code) > 3000:
                code = code[:3000] + "\n    # ... (truncated)"

            # Skip tiny/trivial blocks
            if len(code.strip()) < 30:
                continue

            blocks.append({
                "name": node.name,
                "kind": kind,
                "code": code,
                "file": str(filepath.relative_to(ROOT)),
                "line": node.lineno,
            })

    return blocks


def discover_all_blocks(module_filter: str = "", file_filter: str = "") -> List[Dict[str, str]]:
    """Walk the codebase and extract all def/class blocks."""
    skip_dirs = {"__pycache__", ".venv", "node_modules", ".git", "_archive", "frontend"}
    skip_files = {"__init__.py"}  # Usually just imports

    all_blocks = []

    for py_file in sorted(ROOT.rglob("*.py")):
        # Skip excluded directories
        parts = py_file.relative_to(ROOT).parts
        if any(d in parts for d in skip_dirs):
            continue
        if py_file.name in skip_files and py_file.stat().st_size < 200:
            continue

        rel = str(py_file.relative_to(ROOT))

        # Apply filters
        if file_filter and rel != file_filter:
            continue
        if module_filter:
            from agent.subconscious.loops.training_gen import MODULE_DIRS
            mod_dir = MODULE_DIRS.get(module_filter, module_filter)
            if not rel.startswith(mod_dir):
                continue

        blocks = extract_blocks(py_file)
        all_blocks.extend(blocks)

    return all_blocks


# ── Provider Calling (delegates to shared layer) ───────────

def call_provider(provider_name: str, prompt: str) -> str:
    """Call a provider by name using the shared LLM layer."""
    model_override = os.environ.get("AIOS_CLOUD_GEN_MODEL")
    return llm_generate(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        provider=provider_name,
        model=model_override,
        temperature=0.7,
        max_tokens=4096,
    )


# ── Example Parsing & Validation ────────────────────────────

def parse_examples(raw: str, block: Dict[str, str], provider: str) -> List[Dict[str, Any]]:
    """Parse and validate LLM output into training examples."""
    import re

    raw = raw.strip()

    # Remove markdown code fences
    code_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', raw)
    if code_match:
        raw = code_match.group(1).strip()

    # Find JSON array
    bracket_start = raw.find('[')
    bracket_end = raw.rfind(']')
    if bracket_start == -1 or bracket_end == -1:
        return []

    raw = raw[bracket_start:bracket_end + 1]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    valid = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        messages = item.get("messages", [])
        if not isinstance(messages, list) or len(messages) != 3:
            continue
        roles = [m.get("role") for m in messages]
        if roles != ["system", "user", "assistant"]:
            continue
        if not all(m.get("content", "").strip() for m in messages):
            continue
        # Assistant response must be substantial
        if len(messages[2].get("content", "")) < 50:
            continue

        item["metadata"] = {
            "source": _file_to_module(block["file"]),
            "section": "cloud_generated",
            "type": "conversational",
            "provider": provider,
            "function": block["name"],
            "file": block["file"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        valid.append(item)

    return valid


def _file_to_module(filepath: str) -> str:
    """Map a file path to its module name."""
    from agent.subconscious.loops.training_gen import MODULE_DIRS
    for mod, src_dir in MODULE_DIRS.items():
        if filepath.startswith(src_dir):
            return mod
    # Fallback to directory name
    parts = filepath.split("/")
    return parts[0] if parts else "unknown"


# ── Progress Tracking ───────────────────────────────────────

def load_progress() -> Dict[str, Any]:
    """Load generation progress for --resume support."""
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text())
        except Exception:
            pass
    return {"completed": {}, "stats": {"total_examples": 0, "total_calls": 0, "errors": 0}}


def save_progress(progress: Dict[str, Any]):
    """Save generation progress."""
    PROGRESS_FILE.write_text(json.dumps(progress, indent=2))


def block_key(block: Dict[str, str]) -> str:
    """Unique key for a code block (file + function name + line)."""
    return f"{block['file']}::{block['name']}::{block['line']}"


# ── Prompt Builder ──────────────────────────────────────────

def build_prompt(block: Dict[str, str]) -> str:
    """Build the generation prompt for a code block."""
    module = _file_to_module(block["file"])
    return (
        f"Generate 5 conversational training examples for this {block['kind']} "
        f"from the '{module}' module of AI OS (file: {block['file']}).\n\n"
        f"```python\n{block['code']}\n```\n\n"
        f"The model being trained is 'Nola', a personal AI OS. "
        f"Responses should be first-person, natural, and reference specific "
        f"details from the code above. Include at least one identity-grounding "
        f"example where Nola explains what this code means for her capabilities.\n\n"
        f"Output ONLY a JSON array of 5 example objects."
    )


# ── Main Loop ──────────────────────────────────────────────

def get_available_providers(requested: Optional[str] = None) -> List[str]:
    """Return list of providers that have API keys configured."""
    if requested:
        try:
            p = get_provider(requested)
            return [requested] if p.is_available() else []
        except ValueError:
            return []

    return [p.name for p in _available_providers()]


def run(
    provider_filter: Optional[str] = None,
    module_filter: str = "",
    file_filter: str = "",
    dry_run: bool = False,
    resume: bool = False,
    max_blocks: int = 0,
    delay: float = 0,
):
    """Main generation loop."""
    providers = get_available_providers(provider_filter)
    if not providers:
        print("No providers available. Set at least one API key:")
        for name, cls in PROVIDER_CLASSES.items():
            p = get_provider(name)
            status = "✓" if p.is_available() else f"✗ (set {p.key_env or 'N/A'})"
            print(f"  {name:12s} {status}")
        sys.exit(1)

    if not delay:
        delay = float(os.environ.get("AIOS_CLOUD_GEN_DELAY", "4"))

    print(f"Providers: {', '.join(providers)}")
    print(f"Delay: {delay}s between calls")
    print()

    # Discover all code blocks
    print("Scanning codebase...")
    blocks = discover_all_blocks(module_filter=module_filter, file_filter=file_filter)
    print(f"Found {len(blocks)} def/class blocks across codebase")

    if max_blocks:
        blocks = blocks[:max_blocks]
        print(f"Limited to first {max_blocks} blocks")

    # Load progress for resume
    progress = load_progress() if resume else {"completed": {}, "stats": {"total_examples": 0, "total_calls": 0, "errors": 0}}

    if resume:
        before = len(blocks)
        blocks = [b for b in blocks if block_key(b) not in progress["completed"]]
        print(f"Resuming: {before - len(blocks)} already done, {len(blocks)} remaining")

    if dry_run:
        print(f"\nDry run — would generate for {len(blocks)} blocks:")
        by_module: Dict[str, int] = {}
        for b in blocks:
            mod = _file_to_module(b["file"])
            by_module[mod] = by_module.get(mod, 0) + 1
        for mod, count in sorted(by_module.items()):
            print(f"  {mod:20s} {count:4d} blocks → ~{count * 5} examples")
        print(f"\n  TOTAL: {len(blocks)} blocks → ~{len(blocks) * 5} examples")
        print(f"  Estimated calls: {len(blocks)} (round-robin across {len(providers)} providers)")
        return

    # Shuffle blocks for better distribution across modules
    random.shuffle(blocks)

    # Output file per provider+module
    output_path = GENERATED_DIR / "cloud_generated.jsonl"
    total_examples = progress["stats"]["total_examples"]
    total_calls = progress["stats"]["total_calls"]
    errors = progress["stats"]["errors"]
    provider_idx = 0

    print(f"\nGenerating {len(blocks)} blocks × 5 examples = ~{len(blocks) * 5} training examples")
    print(f"Output: {output_path}\n")

    for i, block in enumerate(blocks):
        # Round-robin provider selection
        provider = providers[provider_idx % len(providers)]
        provider_idx += 1

        bk = block_key(block)
        module = _file_to_module(block["file"])

        print(f"[{i+1}/{len(blocks)}] {block['file']}::{block['name']} ({block['kind']}) → {provider}", end=" ", flush=True)

        prompt = build_prompt(block)

        try:
            raw = call_provider(provider, prompt)
            examples = parse_examples(raw, block, provider)
            total_calls += 1

            if examples:
                with open(output_path, "a") as f:
                    for ex in examples:
                        f.write(json.dumps(ex) + "\n")
                total_examples += len(examples)
                print(f"✓ {len(examples)} examples")
            else:
                print("✗ parse failed")
                errors += 1

        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:200]
            except Exception:
                pass
            print(f"✗ HTTP {e.code}: {body}")
            errors += 1
            # Back off on rate limits
            if e.code == 429:
                wait = delay * 5
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
        except Exception as e:
            print(f"✗ {type(e).__name__}: {e}")
            errors += 1

        # Save progress
        progress["completed"][bk] = {
            "provider": provider,
            "time": datetime.now(timezone.utc).isoformat(),
        }
        progress["stats"] = {
            "total_examples": total_examples,
            "total_calls": total_calls,
            "errors": errors,
        }
        save_progress(progress)

        # Delay between calls
        if i < len(blocks) - 1:
            time.sleep(delay)

    print(f"\n{'='*60}")
    print(f"Done! Generated {total_examples} examples from {total_calls} calls ({errors} errors)")
    print(f"Output: {output_path}")
    print(f"Next: run 'python -m finetune.combine_all' to merge into training set")


# ── CLI ─────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate training data using free-tier cloud LLMs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m finetune.cloud_gen --dry-run                    # Preview scope
  python -m finetune.cloud_gen --provider gemini            # Gemini only
  python -m finetune.cloud_gen --resume                     # Continue where you left off
  python -m finetune.cloud_gen --module identity --max 20   # 20 identity blocks
  python -m finetune.cloud_gen --file agent/agent.py        # Single file
        """,
    )
    parser.add_argument("--provider", "-p", help="Use single provider (gemini/claude/openai/openrouter/ollama)")
    parser.add_argument("--module", "-m", help="Filter to single module")
    parser.add_argument("--file", "-f", help="Filter to single file (relative path)")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be generated")
    parser.add_argument("--resume", "-r", action="store_true", help="Skip already-generated blocks")
    parser.add_argument("--max", type=int, default=0, help="Max blocks to process")
    parser.add_argument("--delay", type=float, default=0, help="Seconds between API calls")

    args = parser.parse_args()

    run(
        provider_filter=args.provider,
        module_filter=args.module or "",
        file_filter=args.file or "",
        dry_run=args.dry_run,
        resume=args.resume,
        max_blocks=args.max,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
