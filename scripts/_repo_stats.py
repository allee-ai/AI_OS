#!/usr/bin/env python3
"""Quick stats on the AI_OS git history + remote."""
import subprocess, os, datetime
from pathlib import Path

REPO = Path("/Users/cade/Desktop/AI_OS")
os.chdir(REPO)

def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()

print("=== REMOTE ===")
print(sh("git remote -v"))
print()

print("=== TIMELINE ===")
first = sh("git log --reverse --format='%aI %h %s' | head -1")
last  = sh("git log -1 --format='%aI %h %s'")
print(f"first: {first}")
print(f"last : {last}")

# parse age
try:
    f_iso = first.split()[0]
    l_iso = last.split()[0]
    f_dt = datetime.datetime.fromisoformat(f_iso)
    l_dt = datetime.datetime.fromisoformat(l_iso)
    span = (l_dt - f_dt).days
    print(f"span : {span} days  ({span/30.4:.1f} months)")
except Exception as e:
    span = None
    print(f"span parse failed: {e}")
print()

total = int(sh("git rev-list --all --count") or 0)
on_main = int(sh("git rev-list --count HEAD") or 0)
print(f"=== COMMITS ===")
print(f"total (all branches): {total}")
print(f"on HEAD branch     : {on_main}")
if span:
    print(f"avg/day            : {on_main/max(span,1):.2f}")
    print(f"avg/week           : {on_main/max(span/7,1):.1f}")
print()

print("=== AUTHORS ===")
print(sh("git shortlog -sne --all | head -10"))
print()

print("=== FILE COUNT ===")
tracked = sh('git ls-files | wc -l').strip()
py = sh("git ls-files '*.py' | wc -l").strip()
md = sh("git ls-files '*.md' | wc -l").strip()
ts = sh("git ls-files '*.ts' '*.tsx' | wc -l").strip()
print(f"tracked files : {tracked}")
print(f"  .py files   : {py}")
print(f"  .md files   : {md}")
print(f"  .ts/.tsx    : {ts}")
print()

print("=== LINES OF CODE (HEAD) ===")
loc_py = sh("git ls-files '*.py' | xargs wc -l 2>/dev/null | tail -1")
loc_md = sh("git ls-files '*.md' | xargs wc -l 2>/dev/null | tail -1")
loc_ts = sh("git ls-files '*.ts' '*.tsx' | xargs wc -l 2>/dev/null | tail -1")
print(f"py: {loc_py}")
print(f"md: {loc_md}")
print(f"ts: {loc_ts}")
print()

print("=== TOTAL CHURN (lines added/removed across all commits) ===")
churn = sh("git log --all --shortstat --format='' | awk '/files? changed/ {f+=$1; for(i=1;i<=NF;i++){if($i~/insert/)a+=$(i-1); if($i~/delet/)d+=$(i-1)}} END{print f, a, d}'")
parts = churn.split()
if len(parts) == 3:
    f, a, d = parts
    print(f"files touched: {f}")
    print(f"insertions:    {a}")
    print(f"deletions:     {d}")
    print(f"net:           {int(a)-int(d):+}")
print()

print("=== COMMITS PER MONTH (last 12 mo) ===")
print(sh("git log --format='%aI' --since='12 months ago' | cut -c1-7 | sort | uniq -c"))
print()

print("=== DAYS WITH AT LEAST ONE COMMIT (last 12 mo) ===")
days = sh("git log --format='%aI' --since='12 months ago' | cut -c1-10 | sort -u | wc -l").strip()
print(f"active days: {days}")
print()

print("=== TOP 10 TOUCHED FILES (all-time) ===")
print(sh("git log --all --pretty=format: --name-only | sort | uniq -c | sort -rn | grep -v '^ *[0-9]* *$' | head -10"))
