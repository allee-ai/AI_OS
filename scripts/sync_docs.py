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

Rules:
- Module READMEs are the source of truth. This script NEVER writes to them.
- Root docs get their INCLUDE sections replaced with module content.
- Checkbox state is MERGED: if either side has [x], the result is [x].
  This prevents re-checking completed items and allows edits in either file.
- Module READMEs are append-only by convention — contributors add, never delete.
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


def _extract_checkboxes(text: str) -> dict[str, bool]:
    """Build a map of checkbox-line-text → checked for every ``- [x]`` / ``- [ ]`` line."""
    result: dict[str, bool] = {}
    for line in text.splitlines():
        m = re.match(r"^(\s*-\s*)\[([ xX])\]\s*(.*)", line)
        if m:
            # Key is the text after the checkbox, stripped, so we match regardless of indent
            key = m.group(3).strip()
            checked = m.group(2).lower() == "x"
            result[key] = checked
    return result


def _merge_checkboxes(incoming: str, existing: str) -> str:
    """Merge checkbox state: if EITHER side has [x], result is [x].

    ``incoming`` is the module README content (source of truth for new items).
    ``existing`` is what's currently in the root doc section.
    The merge ensures:
    - New items from module README appear.
    - Items checked in either place stay checked.
    - Items removed from module README are dropped (module is canonical for item list).
    """
    existing_checks = _extract_checkboxes(existing)

    lines: list[str] = []
    for line in incoming.splitlines():
        m = re.match(r"^(\s*-\s*)\[([ xX])\]\s*(.*)", line)
        if m:
            prefix, state, text = m.group(1), m.group(2), m.group(3)
            key = text.strip()
            # Checked if either side says so
            if state.lower() == "x" or existing_checks.get(key, False):
                line = f"{prefix}[x] {text}"
            else:
                line = f"{prefix}[ ] {text}"
        lines.append(line)
    return "\n".join(lines)


def update_doc_section(doc_path: Path, section: str, module: str, content: str, source_path: str) -> bool:
    """
    Update a section in a root doc file with content from a module.
    Merges checkbox state so [x] from either side is preserved.
    Returns True if updated, False if marker not found or no change.
    """
    if not doc_path.exists():
        return False
    
    doc_content = doc_path.read_text(encoding="utf-8")
    
    # Pattern: <!-- INCLUDE:identity:ARCHITECTURE --> ... <!-- /INCLUDE:identity:ARCHITECTURE -->
    pattern = f"(<!-- INCLUDE:{module}:{section} -->)(.*?)(<!-- /INCLUDE:{module}:{section} -->)"
    
    match = re.search(pattern, doc_content, re.DOTALL)
    if not match:
        return False
    
    existing_section = match.group(2)

    # Merge checkbox state between incoming content and existing root doc
    merged = _merge_checkboxes(content, existing_section)

    # Build replacement with source link
    header = f"\n_Source: [{source_path}/README.md]({source_path}/README.md)_\n\n"
    replacement = f"{match.group(1)}{header}{merged}\n{match.group(3)}"
    
    new_content = doc_content[:match.start()] + replacement + doc_content[match.end():]
    
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


def back_sync_checkboxes() -> dict:
    """Propagate [x] checks from root docs back to module READMEs.

    This is APPEND-ONLY: it only changes ``[ ]`` → ``[x]`` in module
    READMEs when the root doc already has ``[x]``.  It never deletes
    lines, never unchecks, and never adds new items.
    """
    total = 0
    touched: list[str] = []

    for path, module, _name in MODULES:
        readme = PROJECT_ROOT / path / "README.md"
        if not readme.exists():
            continue

        readme_text = readme.read_text(encoding="utf-8")
        changed = False

        for section, doc_path in ROOT_DOCS.items():
            if not doc_path.exists():
                continue
            doc_text = doc_path.read_text(encoding="utf-8")

            # Extract current root-doc section for this module
            pattern = f"<!-- INCLUDE:{module}:{section} -->(.*?)<!-- /INCLUDE:{module}:{section} -->"
            root_match = re.search(pattern, doc_text, re.DOTALL)
            if not root_match:
                continue
            root_checks = _extract_checkboxes(root_match.group(1))
            if not root_checks:
                continue

            # Extract corresponding section from module README
            mod_pattern = f"(<!-- {section}:{module} -->)(.*?)(<!-- /{section}:{module} -->)"
            mod_match = re.search(mod_pattern, readme_text, re.DOTALL)
            if not mod_match:
                continue

            mod_section = mod_match.group(2)
            new_lines: list[str] = []
            section_changed = False

            for line in mod_section.splitlines():
                m = re.match(r"^(\s*-\s*)\[([ xX])\]\s*(.*)", line)
                if m:
                    prefix, state, text = m.group(1), m.group(2), m.group(3)
                    key = text.strip()
                    if state.lower() != "x" and root_checks.get(key, False):
                        line = f"{prefix}[x] {text}"
                        section_changed = True
                new_lines.append(line)

            if section_changed:
                new_section = "\n".join(new_lines)
                readme_text = (
                    readme_text[:mod_match.start(2)]
                    + new_section
                    + readme_text[mod_match.end(2):]
                )
                changed = True
                total += 1

        if changed:
            readme.write_text(readme_text, encoding="utf-8")
            touched.append(module)

    return {"total": total, "modules": touched}


def main():
    """Main entry point."""
    do_back_sync = "--back-sync" in sys.argv

    # Forward sync: module READMEs → root docs (with checkbox merge)
    results = sync_all()
    
    if results["total_sections_synced"] > 0:
        print(f"  ✓ Synced {results['total_sections_synced']} sections from {len(results['modules'])} modules")
        for m in results["modules"]:
            print(f"    - {m}")
    else:
        print("  ✓ All docs already in sync")

    # Back-sync: propagate [x] from root docs → module READMEs (append-only)
    if do_back_sync:
        bs = back_sync_checkboxes()
        if bs["total"] > 0:
            print(f"  ✓ Back-synced checkboxes to {len(bs['modules'])} module(s): {', '.join(bs['modules'])}")
        else:
            print("  ✓ Module READMEs already up to date")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
