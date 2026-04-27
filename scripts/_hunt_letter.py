#!/usr/bin/env python3
"""Hunt for handwritten-letter photos.

Strategy:
  1. Look at common photo/screenshot locations.
  2. Filter images by:
     - size likely to be a phone photo (> 500KB, not a tiny screenshot)
     - portrait orientation (most letter photos)
     - taken between ~Feb 2025 and ~Dec 2025 (Elaris/Nola era, before AI_OS repo)
  3. Don't crack the Photos.app library (would take forever / private).
  4. Also check iCloud Drive photo folders and Desktop / Downloads.
"""
import os, subprocess, datetime
from pathlib import Path

HOME = Path.home()

# Candidate roots (non-destructive read-only)
roots = [
    HOME / "Desktop",
    HOME / "Downloads",
    HOME / "Documents",
    HOME / "Pictures",
    HOME / "Library/Mobile Documents/com~apple~CloudDocs",  # iCloud Drive
]

IMG_EXT = {".jpg", ".jpeg", ".heic", ".png"}

# Time window: Jan 2025 → Dec 15 2025 (pre-AI_OS first commit)
start = datetime.datetime(2025, 1, 1).timestamp()
end   = datetime.datetime(2025, 12, 15).timestamp()

hits = []
errors = 0
for root in roots:
    if not root.exists(): continue
    for dp, dn, fn in os.walk(root):
        # skip noisy photo-library bundles and node_modules type stuff
        low = dp.lower()
        if any(s in low for s in ["/photos library.photoslibrary", "/node_modules", "/.venv", "/library/caches", "/library/containers"]):
            dn[:] = []  # don't recurse
            continue
        for name in fn:
            if Path(name).suffix.lower() not in IMG_EXT: continue
            p = Path(dp) / name
            try:
                st = p.stat()
                if st.st_size < 500_000: continue   # skip tiny screenshots
                if st.st_size > 30_000_000: continue  # skip huge raws
                if not (start <= st.st_mtime <= end): continue
                hits.append((st.st_mtime, st.st_size, p))
            except Exception:
                errors += 1

hits.sort()
print(f"candidate images (mtime 2025-01 → 2025-12-15, >500KB): {len(hits)}")
print(f"walk errors: {errors}")
print()
# group by parent folder
from collections import Counter
folder_count = Counter(str(p.parent) for _,_,p in hits)
print("=== FOLDERS WITH MOST HITS (top 15) ===")
for folder, n in folder_count.most_common(15):
    print(f"  {n:>4}  {folder}")

print()
print("=== SAMPLE (20 most recent candidate files) ===")
for ts, sz, p in hits[-20:]:
    d = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
    print(f"  {d}  {sz/1024/1024:>5.1f}MB  {p}")
