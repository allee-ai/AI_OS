#!/usr/bin/env python3
"""
Copy all markdown files from AI_OS to ~/Desktop/docs for easy upload.
Preserves directory structure.
"""

import shutil
from pathlib import Path

# Source and destination
PROJECT_ROOT = Path(__file__).parent.parent
DEST_DIR = Path.home() / "Desktop" / "docs"

# Directories to skip
SKIP_DIRS = {
    ".venv", "node_modules", ".git", "__pycache__", 
    "dist", "build", ".next", "Nola AI OS.app"
}

def copy_md_files():
    """Copy all .md files preserving directory structure."""
    # Clean and create destination
    if DEST_DIR.exists():
        shutil.rmtree(DEST_DIR)
    DEST_DIR.mkdir(parents=True)
    
    copied = 0
    for md_file in PROJECT_ROOT.rglob("*.md"):
        # Skip if in excluded directory
        if any(skip in md_file.parts for skip in SKIP_DIRS):
            continue
        
        # Calculate relative path and destination
        rel_path = md_file.relative_to(PROJECT_ROOT)
        dest_path = DEST_DIR / rel_path
        
        # Create parent dirs and copy
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(md_file, dest_path)
        print(f"  ✓ {rel_path}")
        copied += 1
    
    print(f"\n📁 Copied {copied} markdown files to {DEST_DIR}")

if __name__ == "__main__":
    print("📄 Copying markdown files to Desktop/docs...\n")
    copy_md_files()
