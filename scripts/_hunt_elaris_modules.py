#!/usr/bin/env python3
"""One-off: find old Elaris module-stub artifacts, ignoring venvs and caches."""
import os, re
from pathlib import Path

ROOTS = [
    Path("/Users/cade/Desktop/Junk/AI Development"),
    Path("/Users/cade/Desktop/Junk/Elaris copy"),
    Path("/Users/cade/Library/Mobile Documents/iCloud~com~omz-software~Pythonista3/Documents/Everything Else 2"),
    Path("/Users/cade/Library/Mobile Documents/com~apple~CloudDocs/X_other_stuff_2025-05-01_1214/Elaris_5:1:25"),
    Path("/Users/cade/ElarisV4"),
    Path("/Users/cade/Desktop/Junk/Nola"),
    Path("/Users/cade/Desktop/Junk/Polaris_v1"),
]
SKIP_DIR = re.compile(r"(\.venv|venv|__pycache__|node_modules|\.git|site-packages|dist-info)")
TARGETS = re.compile(r"\b(checkpoint|awareness|22[\s_-]?modules?|module[_ ]?list|stub|threads?:|sub[_ ]?modules?|consciousness|attention[_ ]?manager|working[_ ]?memory)\b", re.I)
EXTS = {".py", ".md", ".txt", ".json", ".yaml", ".yml"}

hits = []
for root in ROOTS:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        # prune
        dirnames[:] = [d for d in dirnames if not SKIP_DIR.search(d)]
        for fn in filenames:
            p = Path(dirpath) / fn
            if p.suffix.lower() not in EXTS:
                continue
            try:
                if p.stat().st_size > 200_000:  # skip giants
                    continue
                txt = p.read_text(errors="ignore")
            except Exception:
                continue
            matches = [w for w in set(TARGETS.findall(txt)) if w]
            if matches:
                hits.append((len(matches), str(p), matches[:6]))

hits.sort(reverse=True)
print(f"=== {len(hits)} files matched ===\n")
for score, path, words in hits[:40]:
    print(f"[{score} kw] {path}")
    print(f"    words: {words}")

# also: dump any directory whose direct children look like module stubs (10+ subdirs all py)
print("\n=== Directories with many py-module subfolders ===")
for root in ROOTS:
    if not root.exists():
        continue
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not SKIP_DIR.search(d)]
        sub_modules = [d for d in dirnames if (Path(dirpath) / d / "__init__.py").exists()]
        if len(sub_modules) >= 8:
            print(f"  {dirpath}  ({len(sub_modules)} pkg subdirs)")
            for d in sub_modules[:25]:
                print(f"    - {d}")
