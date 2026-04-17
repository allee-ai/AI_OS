"""
Showdown Results Collector
==========================
SSH into all 3 droplets, pull git logs + evolution DB,
and produce a side-by-side comparison.

Usage:
    python3 scripts/showdown_collect.py
    python3 scripts/showdown_collect.py --html   # generate HTML report
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

DROPLETS = {
    "claude":  {"name": "nola-claude",  "provider": "claude",  "model": "claude-sonnet-4-20250514"},
    "openai":  {"name": "nola-openai",  "provider": "openai",  "model": "gpt-4o"},
    "gemini":  {"name": "nola-gemini",  "provider": "gemini",  "model": "gemini-2.0-flash"},
}

SSH_KEY = Path.home() / ".ssh" / "do_droplet"
OUTPUT_DIR = Path(__file__).parent.parent / "eval" / "showdown_results"


def get_droplet_ip(name: str) -> str:
    result = subprocess.run(
        ["doctl", "compute", "droplet", "list",
         "--format", "Name,PublicIPv4", "--no-header"],
        capture_output=True, text=True, timeout=15,
    )
    for line in result.stdout.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == name:
            return parts[1]
    return ""


def ssh_cmd(ip: str, cmd: str) -> str:
    result = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-i", str(SSH_KEY),
         f"root@{ip}", cmd],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


def collect_one(key: str, info: dict) -> dict:
    ip = get_droplet_ip(info["name"])
    if not ip:
        print(f"  ✗ {info['name']}: no IP found")
        return {"error": "no IP", **info}

    print(f"  ▸ {info['name']} ({ip})")

    data = {**info, "ip": ip, "commits": [], "evolution_log": [], "git_stats": {}}

    # Git log — all evolution commits
    raw_log = ssh_cmd(ip, 'cd /opt/aios && git log --oneline --all --grep="\\[evolve\\]" --format="%H|%ai|%s"')
    for line in raw_log.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            data["commits"].append({
                "hash": parts[0][:8],
                "date": parts[1],
                "message": parts[2],
            })

    # Git diff stat — total changes from initial state
    raw_stat = ssh_cmd(ip, 'cd /opt/aios && git diff --stat HEAD~$(git log --oneline --grep="\\[evolve\\]" | wc -l) HEAD 2>/dev/null || echo "no stats"')
    data["git_stats"]["diff_stat"] = raw_stat[:2000]

    # Files changed count
    raw_files = ssh_cmd(ip, 'cd /opt/aios && git log --grep="\\[evolve\\]" --name-only --format="" | sort -u')
    data["git_stats"]["files_touched"] = [f for f in raw_files.splitlines() if f.strip()]

    # Evolution log from DB
    raw_evo = ssh_cmd(ip, """cd /opt/aios && python3 -c "
import json, sqlite3
conn = sqlite3.connect('data/db/aios.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM evolution_log ORDER BY id').fetchall()
print(json.dumps([dict(r) for r in rows]))
conn.close()
" 2>/dev/null || echo "[]"
""")
    try:
        data["evolution_log"] = json.loads(raw_evo)
    except json.JSONDecodeError:
        data["evolution_log"] = []

    # Service status
    data["service_status"] = ssh_cmd(ip, "systemctl is-active aios 2>/dev/null || echo unknown")

    print(f"    {len(data['commits'])} commits, {len(data['evolution_log'])} log entries")
    return data


def print_summary(results: dict):
    print("\n" + "=" * 70)
    print("  SHOWDOWN RESULTS")
    print("=" * 70)

    for key, data in results.items():
        if "error" in data:
            print(f"\n  {key}: ERROR — {data['error']}")
            continue

        commits = data.get("commits", [])
        evo_log = data.get("evolution_log", [])
        successes = [e for e in evo_log if e.get("success")]
        failures = [e for e in evo_log if not e.get("success")]
        files = data.get("git_stats", {}).get("files_touched", [])

        print(f"\n  {key.upper()} ({data.get('model', '?')})")
        print(f"    Status:     {data.get('service_status', '?')}")
        print(f"    Commits:    {len(commits)}")
        print(f"    Successes:  {len(successes)}")
        print(f"    Failures:   {len(failures)}")
        print(f"    Files:      {len(files)} unique")
        if files:
            for f in files[:10]:
                print(f"      - {f}")
            if len(files) > 10:
                print(f"      ... and {len(files) - 10} more")

        if successes:
            print(f"    Recent changes:")
            for e in successes[-5:]:
                print(f"      [{e.get('commit_hash', '?')}] {e.get('description', '?')[:60]}")

    print("\n" + "=" * 70)


def generate_html(results: dict) -> Path:
    """Generate an HTML comparison report."""
    html_parts = ["""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>Evolution Showdown Results</title>
<style>
  body { font-family: system-ui; background: #0f0f1a; color: #e0e0e0; padding: 2rem; }
  h1 { color: #6c63ff; text-align: center; }
  .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-top: 2rem; }
  .card { background: #1a1a2e; border-radius: 12px; padding: 1.5rem; }
  .card h2 { color: #6c63ff; margin-top: 0; }
  .stat { display: flex; justify-content: space-between; padding: 0.3rem 0; border-bottom: 1px solid #2a2a3e; }
  .stat-label { color: #888; }
  .stat-value { color: #fff; font-weight: bold; }
  .commit { font-size: 0.85rem; padding: 0.3rem 0; border-bottom: 1px solid #1f1f30; }
  .hash { color: #6c63ff; font-family: monospace; }
  .success { color: #4caf50; }
  .failure { color: #f44336; }
  .file { font-family: monospace; font-size: 0.8rem; color: #aaa; }
  .timestamp { color: #666; text-align: center; margin-top: 2rem; }
</style>
</head><body>
<h1>Evolution Showdown Results</h1>
<div class="grid">"""]

    for key, data in results.items():
        commits = data.get("commits", [])
        evo_log = data.get("evolution_log", [])
        successes = [e for e in evo_log if e.get("success")]
        failures = [e for e in evo_log if not e.get("success")]
        files = data.get("git_stats", {}).get("files_touched", [])

        html_parts.append(f"""
<div class="card">
  <h2>{key.upper()}</h2>
  <p style="color:#888">{data.get('model', '?')}</p>
  <div class="stat"><span class="stat-label">Status</span><span class="stat-value">{data.get('service_status', '?')}</span></div>
  <div class="stat"><span class="stat-label">Commits</span><span class="stat-value">{len(commits)}</span></div>
  <div class="stat"><span class="stat-label">Successes</span><span class="stat-value success">{len(successes)}</span></div>
  <div class="stat"><span class="stat-label">Failures</span><span class="stat-value failure">{len(failures)}</span></div>
  <div class="stat"><span class="stat-label">Files touched</span><span class="stat-value">{len(files)}</span></div>
  <h3 style="margin-top:1rem;">Recent Changes</h3>""")

        for e in successes[-8:]:
            html_parts.append(f"""
  <div class="commit">
    <span class="hash">{e.get('commit_hash', '?')}</span>
    {e.get('description', '?')[:80]}
  </div>""")

        if files:
            html_parts.append("<h3>Files</h3>")
            for f in files[:15]:
                html_parts.append(f'<div class="file">{f}</div>')

        html_parts.append("</div>")

    html_parts.append(f"""
</div>
<p class="timestamp">Collected: {datetime.now().isoformat()}</p>
</body></html>""")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "showdown_report.html"
    out_path.write_text("\n".join(html_parts))
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Collect showdown results")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    args = parser.parse_args()

    print("Collecting showdown results...\n")

    results = {}
    for key, info in DROPLETS.items():
        results[key] = collect_one(key, info)

    # Save raw JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "showdown_results.json"
    json_path.write_text(json.dumps(results, indent=2, default=str))
    print(f"\n  Raw data: {json_path}")

    print_summary(results)

    if args.html:
        html_path = generate_html(results)
        print(f"\n  HTML report: {html_path}")


if __name__ == "__main__":
    main()
