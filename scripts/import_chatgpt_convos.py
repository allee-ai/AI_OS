#!/usr/bin/env python3
"""
Import ChatGPT conversations from an official data export.

Handles:
  - conversations.json (standard OpenAI export)
  - ZIP files (extracts automatically)
  - Nested folders from ZIP extraction

Usage:
    python3 scripts/import_chatgpt_convos.py <path_to_export>
    python3 scripts/import_chatgpt_convos.py ~/Desktop/Junk/chatgpt_export.zip
    python3 scripts/import_chatgpt_convos.py /tmp/chatgpt_export/  [extracted folder]
    
    Options:
      --dry-run    Show what would be imported without writing to DB
"""

import asyncio
import sys
import time
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chat.import_convos import ImportConvos


async def import_chatgpt(export_path: Path, dry_run: bool = False):
    """Import ChatGPT conversations."""
    workspace_path = PROJECT_ROOT / "workspace"
    feeds_path = PROJECT_ROOT / "Feeds"

    # If it's a zip, extract to a temp dir
    cleanup_dir = None
    if export_path.is_file() and export_path.suffix == ".zip":
        print(f"Extracting ZIP: {export_path.name}")
        cleanup_dir = Path(tempfile.mkdtemp(prefix="chatgpt_import_"))
        with zipfile.ZipFile(export_path, "r") as zf:
            zf.extractall(cleanup_dir)
        export_path = cleanup_dir
        print(f"Extracted to: {cleanup_dir}")

    importer = ImportConvos(workspace_path=workspace_path, feeds_path=feeds_path)

    # Detect platform
    parser = importer.detect_platform(export_path)
    if not parser:
        print(f"ERROR: Could not detect ChatGPT export at: {export_path}")
        print("Expected: conversations.json inside a folder or ZIP")
        return

    platform = parser.get_platform_name()
    print(f"Detected platform: {platform}")

    # Parse
    print("Parsing conversations...")
    conversations = await parser.parse(export_path)
    print(f"Parsed {len(conversations)} conversations")

    if not conversations:
        print("No conversations found.")
        return

    # Show summary
    total_msgs = sum(len(c.messages) for c in conversations)
    print(f"Total messages: {total_msgs}")

    # Sample
    for c in conversations[:5]:
        roles = {}
        for m in c.messages:
            roles[m.role] = roles.get(m.role, 0) + 1
        print(f"  [{c.id[:12]}] {c.title[:50]:50s} | {len(c.messages):3d} msgs | {c.created_at.strftime('%Y-%m-%d')}")

    if len(conversations) > 5:
        print(f"  ... and {len(conversations) - 5} more")

    if dry_run:
        print("\n[DRY RUN] Would import the above. Exiting.")
        return

    # Import through the standard pipeline
    print(f"\nImporting {len(conversations)} conversations...")
    start = time.time()
    result = await importer.import_conversations(export_path, platform=platform)
    elapsed = time.time() - start

    print(f"\nDone in {elapsed:.1f}s")
    print(f"  Platform:  {result['platform']}")
    print(f"  Imported:  {result['imported']}")
    print(f"  Failed:    {result['failed']}")
    print(f"  Total:     {result['total_conversations']}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/import_chatgpt_convos.py <path_to_export> [--dry-run]")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser().resolve()
    dry_run = "--dry-run" in sys.argv

    if not path.exists():
        print(f"ERROR: Path not found: {path}")
        sys.exit(1)

    asyncio.run(import_chatgpt(path, dry_run=dry_run))


if __name__ == "__main__":
    main()
