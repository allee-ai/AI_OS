"""Eval CLI — /eval list, /eval run, /eval results, /eval judge"""

DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _cmd_eval(args: str):
    """Dispatch /eval subcommands."""
    tokens = args.strip().split()
    if not tokens:
        _eval_help()
        return

    sub = tokens[0]
    rest = tokens[1:]

    if sub == "list":
        _eval_list()
    elif sub == "run":
        _eval_run(rest)
    elif sub == "results":
        _eval_results(rest)
    elif sub == "judge":
        _eval_judge(rest)
    else:
        _eval_help()


def _eval_list():
    """List all available evals with their defaults."""
    from .evals import list_evals
    evals = list_evals()
    print(f"\n  {BOLD}Available Evaluations{RESET}\n")
    for e in evals:
        defaults = ", ".join(f"{k}={v}" for k, v in e["defaults"].items())
        print(f"  {CYAN}{e['name']}{RESET}")
        print(f"    {e['description']}")
        print(f"    {DIM}defaults: {defaults}{RESET}")
    print()


def _eval_run(tokens: list):
    """
    /eval run <name|all> [--model X] [--save] [--key=val ...]
    """
    if not tokens:
        print(f"  {RED}usage: /eval run <name|all> [--model X] [--save] [--key=val]{RESET}")
        return

    name = tokens[0]
    save = "--save" in tokens
    overrides = {}

    for t in tokens[1:]:
        if t == "--save":
            continue
        if t.startswith("--model"):
            # Handle both --model X and --model=X
            if "=" in t:
                overrides["model"] = t.split("=", 1)[1]
            else:
                idx = tokens.index(t)
                if idx + 1 < len(tokens):
                    overrides["model"] = tokens[idx + 1]
        elif "=" in t and t.startswith("--"):
            k, v = t[2:].split("=", 1)
            # Try to parse numeric values
            try:
                v = int(v)
            except ValueError:
                try:
                    v = float(v)
                except ValueError:
                    pass
            overrides[k] = v

    if name == "all":
        from .evals import run_all
        print(f"\n  {BOLD}Running all evals{RESET} {'(saving)' if save else '(dry run)'}\n")
        results = run_all(save=save, **overrides)
        for r in results:
            _print_result(r)
        _print_summary(results)
    else:
        from .evals import run_eval
        print(f"\n  {BOLD}Running: {name}{RESET} {'(saving)' if save else '(dry run)'}\n")
        result = run_eval(name, save=save, **overrides)
        _print_result(result)


def _print_result(r: dict):
    """Pretty-print a single eval result."""
    if r.get("status") == "error":
        print(f"  {RED}✗ {r['eval_name']}: {r.get('error', 'unknown error')}{RESET}")
        return

    score = r.get("score", 0)
    total = r.get("total", 0)
    passed = r.get("passed", 0)
    status = r.get("status", "?")

    color = GREEN if status == "pass" else RED if status == "fail" else YELLOW
    bar = _score_bar(score)

    print(f"  {color}{'✓' if status == 'pass' else '✗'} {r['eval_name']}{RESET}  {bar}  {passed}/{total} ({score:.0%})")

    # Show per-case details
    for d in r.get("details", []):
        p = "✓" if d.get("passed") else "✗"
        prompt = d.get("prompt", "")[:60]
        print(f"    {DIM}{p} {prompt}{RESET}")

    if r.get("run_id"):
        print(f"    {DIM}saved as {r['run_id']}{RESET}")
    print()


def _score_bar(score: float, width: int = 20) -> str:
    """Render a visual score bar."""
    filled = int(score * width)
    bar = "█" * filled + "░" * (width - filled)
    color = GREEN if score >= 0.8 else YELLOW if score >= 0.5 else RED
    return f"{color}{bar}{RESET}"


def _print_summary(results: list):
    """Print aggregate summary after run-all."""
    total_pass = sum(1 for r in results if r.get("status") == "pass")
    total_fail = sum(1 for r in results if r.get("status") == "fail")
    total_err = sum(1 for r in results if r.get("status") == "error")
    avg_score = sum(r.get("score", 0) for r in results) / len(results) if results else 0

    print(f"  {BOLD}Summary{RESET}: {GREEN}{total_pass} pass{RESET}  {RED}{total_fail} fail{RESET}  {YELLOW}{total_err} error{RESET}  avg {avg_score:.0%}\n")


def _eval_results(tokens: list):
    """/eval results [--last N]"""
    from .schema import get_runs
    limit = 10
    for i, t in enumerate(tokens):
        if t == "--last" and i + 1 < len(tokens):
            try:
                limit = int(tokens[i + 1])
            except ValueError:
                pass

    runs = get_runs(limit=limit)
    if not runs:
        print("  No saved eval runs. Use --save to persist results.")
        return

    print(f"\n  {BOLD}Recent Eval Runs{RESET} (last {limit})\n")
    for run in runs:
        status = run.get("status", "?")
        color = GREEN if status == "pass" else RED if status == "fail" else YELLOW
        score = run.get("score", 0) or 0
        print(f"  {color}{status:5s}{RESET}  {run.get('eval_name', '?'):22s}  "
              f"{score:.0%}  {run.get('model', '?'):10s}  "
              f"{DIM}{run.get('id', '?')[:8]}  {run.get('created_at', '?')}{RESET}")
    print()


def _eval_judge(tokens: list):
    """/eval judge <run_id>"""
    if not tokens:
        print(f"  {RED}usage: /eval judge <run_id>{RESET}")
        return

    from .judge import judge_run_interactive
    result = judge_run_interactive(tokens[0])

    if result.get("error"):
        print(f"  {RED}{result['error']}{RESET}")
        return

    s = result.get("summary", {})
    print(f"\n  {BOLD}Human Judge Summary{RESET}")
    print(f"  {GREEN}Good: {s.get('human_good', 0)}{RESET}  "
          f"{YELLOW}Acceptable: {s.get('human_acceptable', 0)}{RESET}  "
          f"{RED}Bad: {s.get('human_bad', 0)}{RESET}  "
          f"{DIM}Skipped: {s.get('skipped', 0)}{RESET}")
    print(f"  Agreement with auto eval: {s.get('agreement_with_auto', 0)}%\n")


def _eval_help():
    print(f"""
  {BOLD}Eval Commands{RESET}

    {BOLD}/eval list{RESET}                       List available evals + defaults
    {BOLD}/eval run <name> [opts]{RESET}           Run a single eval
    {BOLD}/eval run all [opts]{RESET}              Run all evals
    {BOLD}/eval results [--last N]{RESET}          Show saved runs
    {BOLD}/eval judge <run_id>{RESET}              Human-judge a saved run

  {BOLD}Options{RESET}
    {BOLD}--save{RESET}                            Persist results (default: dry run)
    {BOLD}--model <name>{RESET}                    Override model
    {BOLD}--<key>=<value>{RESET}                   Override any eval config
""")


COMMANDS = {
    "/eval": _cmd_eval,
}
