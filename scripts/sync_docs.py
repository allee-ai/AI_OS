#!/usr/bin/env python3
"""
sync_docs.py — Sync module READMEs to root documentation
=========================================================

Called by push.command before git commit to ensure root docs are up-to-date.
Can also be run standalone: python scripts/sync_docs.py

Syncs:
- Module ARCHITECTURE sections → docs/ARCHITECTURE.md
- Module ROADMAP sections → docs/ROADMAP.md
- Module CHANGELOG sections → docs/CHANGELOG.md
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional

# Project root is one level up from scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Modules to scan for documentation sections
MODULES: List[Tuple[str, str, str]] = [
    # (path, module_id, display_name)
    ("agent/threads/identity", "identity", "Identity Thread"),
    ("agent/threads/philosophy", "philosophy", "Philosophy Thread"),
    ("agent/threads/log", "log", "Log Thread"),
    ("agent/threads/form", "form", "Form Thread"),
    ("agent/threads/reflex", "reflex", "Reflex Thread"),
    ("agent/threads/linking_core", "linking_core", "Linking Core"),
    ("agent/subconscious", "subconscious", "Subconscious"),
    ("agent/subconscious/temp_memory", "temp_memory", "Temp Memory"),
    ("agent/services", "services", "Services"),
    ("chat", "chat", "Chat"),
    ("Feeds", "feeds", "Feeds"),
    ("workspace", "workspace", "Workspace"),
    ("finetune", "finetune", "Finetune"),
    ("eval", "eval", "Eval"),
]

# Root docs to update
ROOT_DOCS = {
    "ARCHITECTURE": PROJECT_ROOT / "docs" / "ARCHITECTURE.md",
    "ROADMAP": PROJECT_ROOT / "docs" / "ROADMAP.md",
    "CHANGELOG": PROJECT_ROOT / "docs" / "CHANGELOG.md",
}


def extract_section(readme_path: Path, section: str, module: str) -> str:
    """Extract a marked section from a README file."""
    if not readme_path.exists():
        return ""
    
    content = readme_path.read_text(encoding="utf-8")
    pattern = f"<!-- {section}:{module} -->(.*?)<!-- /{section}:{module} -->"
    match = re.search(pattern, content, re.DOTALL)
    return match.group(1).strip() if match else ""


def update_doc_section(doc_path: Path, section: str, module: str, content: str, source_path: str) -> bool:
    """
    Update a section in a root doc file with content from a module.
    Returns True if updated, False if marker not found or no change.
    """
    if not doc_path.exists():
        return False
    
    doc_content = doc_path.read_text(encoding="utf-8")
    
    # Pattern: <!-- INCLUDE:identity:ARCHITECTURE --> ... <!-- /INCLUDE:identity:ARCHITECTURE -->
    pattern = f"(<!-- INCLUDE:{module}:{section} -->)(.*?)(<!-- /INCLUDE:{module}:{section} -->)"
    
    if not re.search(pattern, doc_content, re.DOTALL):
        return False
    
    # Build replacement with source link
    header = f"\n_Source: [{source_path}/README.md]({source_path}/README.md)_\n\n"
    replacement = f"\\g<1>{header}{content}\n\\g<3>"
    
    new_content = re.sub(pattern, replacement, doc_content, flags=re.DOTALL)
    
    if new_content != doc_content:
        doc_path.write_text(new_content, encoding="utf-8")
        return True
    return False


def sync_module(path: str, module: str, name: str) -> dict:
    """Sync a single module's documentation to root docs."""
    readme = PROJECT_ROOT / path / "README.md"
    results = {"module": module, "synced": []}
    
    for section, doc_path in ROOT_DOCS.items():
        content = extract_section(readme, section, module)
        if content:
            updated = update_doc_section(doc_path, section, module, content, path)
            if updated:
                results["synced"].append(section.lower())
    
    return results


def sync_all() -> dict:
    """Sync all modules to root docs."""
    total_synced = 0
    modules_synced = []
    
    for path, module, name in MODULES:
        result = sync_module(path, module, name)
        if result["synced"]:
            modules_synced.append(f"{module}: {', '.join(result['synced'])}")
            total_synced += len(result["synced"])
    
    return {
        "total_sections_synced": total_synced,
        "modules": modules_synced
    }


def main():
    """Main entry point."""
    results = sync_all()
    
    if results["total_sections_synced"] > 0:
        print(f"  ✓ Synced {results['total_sections_synced']} sections from {len(results['modules'])} modules")
        for m in results["modules"]:
            print(f"    - {m}")
    else:
        print("  ✓ All docs already in sync")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
