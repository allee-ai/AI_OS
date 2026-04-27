#!/usr/bin/env python3
"""Hunt for old Elaris 'awareness' module + sibling stub folders, ignoring venvs."""
import os, re
from pathlib import Path

ROOTS = [
    Path("/Users/cade/Desktop/Junk"),
    Path("/Users/cade/Library/Mobile Documents"),
    Path("/Users/cade/ElarisV4"),
    Path("/Users/cade/Documents"),
]
SKIP_DIR = re.compile(r"(\.venv|venv|__pycache__|node_modules|\.git|site-packages|dist-info|\.Trash|Library/Caches|Library/Logs)")
NAME_HIT = re.compile(r"awareness", re.I)

# Pass 1: any directory or file whose name contains 'awareness'
print("=== Files/dirs named *awareness* ===")
hits_dirs = []
for root in ROOTS:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        if SKIP_DIR.search(dirpath):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not SKIP_DIR.search(d)]
        for d in dirnames:
            if NAME_HIT.search(d):
                full = Path(dirpath) / d
                hits_dirs.append(full)
        for f in filenames:
            if NAME_HIT.search(f):
                print(f"  FILE: {Path(dirpath) / f}")

print(f"\n=== {len(hits_dirs)} dirs named *awareness* ===")
for d in hits_dirs[:30]:
    print(f"  DIR: {d}")
    # peek parent — what siblings did it have?
    parent = d.parent
    try:
        sibs = sorted([s.name for s in parent.iterdir() if s.is_dir() and not s.name.startswith('.')])
        print(f"    parent: {parent}")
        print(f"    siblings ({len(sibs)}): {sibs[:30]}")
        # try to read a one-line README in awareness dir
        for cand in ("README.md", "README.txt", "readme.md", "DESCRIPTION", "DESCRIPTION.md"):
            r = d / cand
            if r.exists() and r.stat().st_size < 5000:
                txt = r.read_text(errors="ignore").strip()
                first = txt.split("\n")[0][:200]
                print(f"    README ({cand}): {first}")
    except Exception as e:
        print(f"    (sib read failed: {e})")
    print()
