"""
Finetune CLI — Training Data & Model Management
================================================
CLI commands for exporting data, generating training examples,
managing adapters, and launching training runs.

Commands:
    /finetune                     Show data stats overview
    /finetune export              Export all thread data → aios_combined.jsonl
    /finetune generate            Run cloud data generator (--provider, --max, etc.)
    /finetune generate --dry-run  Preview what would be generated
    /finetune train               Launch training (train_mac.sh)
    /finetune runs                List previous training runs
    /finetune config              Show current MLX config
"""

import os
import sys
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FT_DIR = ROOT / "finetune"

# ANSI
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_finetune(args: str):
    """Main /finetune dispatcher."""
    tokens = args.strip().split()
    sub = tokens[0] if tokens else ""
    rest = " ".join(tokens[1:]) if len(tokens) > 1 else ""

    if sub == "":
        _ft_stats()
    elif sub == "export":
        _ft_export(rest)
    elif sub in ("generate", "gen"):
        _ft_generate(rest)
    elif sub == "train":
        _ft_train(rest)
    elif sub == "runs":
        _ft_runs()
    elif sub == "config":
        _ft_config()
    elif sub == "help":
        _ft_help()
    else:
        print(f"  Unknown subcommand: {sub}")
        _ft_help()


def _ft_stats():
    """Show training data overview."""
    print(f"\n  {BOLD}Training Data Overview{RESET}\n")

    # Count lines in each data source
    sources = {}

    # Thread exports
    for f in sorted(FT_DIR.glob("*_train.jsonl")):
        name = f.stem.replace("_train", "")
        count = sum(1 for _ in open(f))
        sources[f"thread/{name}"] = count

    # Generated
    gen_dir = FT_DIR / "generated"
    if gen_dir.exists():
        for f in sorted(gen_dir.glob("*.jsonl")):
            if f.name.startswith("."):
                continue
            count = sum(1 for _ in open(f))
            sources[f"generated/{f.stem}"] = count

    # Combined
    combined = FT_DIR / "aios_combined.jsonl"
    if combined.exists():
        combined_count = sum(1 for _ in open(combined))
    else:
        combined_count = 0

    # Train/valid split
    train_f = FT_DIR / "train.jsonl"
    valid_f = FT_DIR / "valid.jsonl"
    train_count = sum(1 for _ in open(train_f)) if train_f.exists() else 0
    valid_count = sum(1 for _ in open(valid_f)) if valid_f.exists() else 0

    # Display
    thread_total = sum(v for k, v in sources.items() if k.startswith("thread/"))
    gen_total = sum(v for k, v in sources.items() if k.startswith("generated/"))

    print(f"  {CYAN}Thread exports:{RESET}  {thread_total:,} examples")
    for k, v in sorted(sources.items()):
        if k.startswith("thread/"):
            print(f"    {k.split('/')[1]:20s} {v:5d}")

    print(f"\n  {CYAN}Generated:{RESET}       {gen_total:,} examples")
    for k, v in sorted(sources.items()):
        if k.startswith("generated/"):
            print(f"    {k.split('/')[1]:20s} {v:5d}")

    print(f"\n  {CYAN}Combined:{RESET}        {combined_count:,} (aios_combined.jsonl)")
    print(f"  {CYAN}Train/Valid:{RESET}     {train_count:,} / {valid_count:,}")

    # Cloud gen progress
    progress_file = FT_DIR / "generated" / ".cloud_gen_progress.json"
    if progress_file.exists():
        try:
            prog = json.loads(progress_file.read_text())
            stats = prog.get("stats", {})
            done = len(prog.get("completed", {}))
            print(f"\n  {CYAN}Cloud gen:{RESET}       {done} blocks done, "
                  f"{stats.get('total_examples', 0):,} examples, "
                  f"{stats.get('errors', 0)} errors")
        except Exception:
            pass
    print()


def _ft_export(args: str):
    """Export training data from all threads."""
    print(f"  Exporting training data...")
    try:
        from finetune.combine_all import main as combine_main
        combine_main()
        combined = FT_DIR / "aios_combined.jsonl"
        if combined.exists():
            count = sum(1 for _ in open(combined))
            print(f"  {GREEN}✓{RESET} Exported {count:,} examples → aios_combined.jsonl")
        else:
            print(f"  {YELLOW}Warning: combine produced no output{RESET}")
    except Exception as e:
        print(f"  {RED}Error: {e}{RESET}")


def _ft_generate(args: str):
    """Run cloud training data generator."""
    # Parse args into cloud_gen CLI args
    argv = args.split() if args else []

    # Map short forms
    cmd = [sys.executable, "-m", "finetune.cloud_gen"] + argv
    print(f"  {DIM}running: {' '.join(cmd)}{RESET}\n")
    subprocess.run(cmd, cwd=str(ROOT))


def _ft_train(args: str):
    """Launch training."""
    tokens = args.strip().split()

    script = FT_DIR / "train_mac.sh"
    if not script.exists():
        print(f"  {RED}train_mac.sh not found{RESET}")
        return

    env = os.environ.copy()
    # Pass through any key=value args
    for t in tokens:
        if "=" in t:
            k, v = t.split("=", 1)
            env[k] = v

    print(f"  Launching training...\n  {DIM}{script}{RESET}\n")
    subprocess.run(["bash", str(script)], cwd=str(FT_DIR), env=env)


def _ft_runs():
    """List training runs from finetune/runs/."""
    runs_dir = FT_DIR / "runs"
    if not runs_dir.exists():
        print("  No runs directory found.")
        return

    print(f"\n  {BOLD}Training Runs{RESET}\n")
    for d in sorted(runs_dir.iterdir()):
        if d.is_dir():
            # Check for adapter config
            adapter = d / "adapter_config.json"
            status = f"{GREEN}✓ adapter{RESET}" if adapter.exists() else f"{DIM}no adapter{RESET}"
            # Size
            size = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            size_mb = size / (1024 * 1024)
            print(f"    {d.name:30s} {size_mb:6.1f} MB  {status}")
    print()


def _ft_config():
    """Show MLX training config."""
    config_path = FT_DIR / "mlx_config.yaml"
    if not config_path.exists():
        print("  mlx_config.yaml not found.")
        return

    print(f"\n  {BOLD}MLX Config{RESET} ({config_path.name})\n")
    print(config_path.read_text())


def _ft_help():
    print(f"""
  {BOLD}Finetune Commands{RESET}

  {BOLD}/finetune{RESET}                         Training data overview & stats
  {BOLD}/finetune export{RESET}                  Export all thread data → aios_combined.jsonl
  {BOLD}/finetune generate [opts]{RESET}         Run cloud data generator
  {BOLD}/finetune train [KEY=VAL ...]{RESET}     Launch training (train_mac.sh)
  {BOLD}/finetune runs{RESET}                    List training run directories
  {BOLD}/finetune config{RESET}                  Show MLX training configuration
  {BOLD}/finetune help{RESET}                    Show this help

  {CYAN}Generate options:{RESET}
    {BOLD}--dry-run{RESET}                        Preview what would be generated
    {BOLD}--provider gemini{RESET}                Use single provider
    {BOLD}--resume{RESET}                         Skip already-generated blocks
    {BOLD}--module identity{RESET}                Filter to single module
    {BOLD}--file agent/agent.py{RESET}            Filter to single file
    {BOLD}--max 50{RESET}                         Limit to N blocks
    {BOLD}--delay 6{RESET}                        Seconds between API calls

  {CYAN}Environment variables:{RESET}
    GEMINI_API_KEY           Google AI Studio (free: 15 RPM)
    ANTHROPIC_API_KEY        Anthropic Claude
    OPENAI_API_KEY           OpenAI
    OPENROUTER_API_KEY       OpenRouter (free models available)
""")


COMMANDS = {
    "/finetune": _cmd_finetune,
}
