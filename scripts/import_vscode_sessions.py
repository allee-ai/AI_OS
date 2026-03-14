#!/usr/bin/env python3
"""
Import all VS Code Copilot chat sessions into AI OS.

Collects sessions from all VS Code workspace storage directories,
parses them with the fixed VSCodeExportParser, and saves them 
through the standard ImportConvos pipeline.

Usage:
    python3 scripts/import_vscode_sessions.py [--dry-run] [--skip-large MB]
"""

import asyncio
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from chat.import_convos import ImportConvos
from chat.parsers.vscode_export_parser import VSCodeExportParser


VSCODE_STORAGE = Path.home() / "Library/Application Support/Code/User/workspaceStorage"
SKIP_LARGE_MB = 400  # Skip files larger than this to avoid OOM


def find_all_sessions() -> list[Path]:
    """Find all VS Code Copilot chat session files."""
    pattern = str(VSCODE_STORAGE / "*/chatSessions/*.json")
    files = sorted(glob.glob(pattern))
    return [Path(f) for f in files]


async def import_all(dry_run: bool = False, skip_large_mb: float = SKIP_LARGE_MB):
    """Import all VS Code sessions through the AI OS pipeline."""
    workspace_path = PROJECT_ROOT / "workspace"
    feeds_path = PROJECT_ROOT / "Feeds"
    
    all_sessions = find_all_sessions()
    print(f"Found {len(all_sessions)} VS Code chat session files")
    
    # Filter out empty files and oversized files
    valid_sessions = []
    skipped_empty = 0
    skipped_large = 0
    for f in all_sessions:
        size = f.stat().st_size
        if size < 100:
            skipped_empty += 1
        elif size > skip_large_mb * 1024 * 1024:
            skipped_large += 1
            print(f"  Skipping {f.name} ({size / 1024 / 1024:.0f}MB > {skip_large_mb}MB)")
        else:
            valid_sessions.append(f)
    
    print(f"Valid: {len(valid_sessions)}, Skipped empty: {skipped_empty}, Skipped large: {skipped_large}")
    
    if dry_run:
        print("\n[DRY RUN] Would import the above files. Exiting.")
        return
    
    # Use the system's ImportConvos pipeline
    importer = ImportConvos(workspace_path=workspace_path, feeds_path=feeds_path)
    parser = VSCodeExportParser()
    
    total_imported = 0
    total_turns = 0
    total_failed = 0
    start_time = time.time()
    
    for i, session_file in enumerate(valid_sessions):
        try:
            conversations = await parser.parse(session_file)
            
            for conv in conversations:
                if not conv.messages:
                    continue
                    
                # Convert and save through the standard pipeline
                aios_conv = importer._convert_to_aios_format(conv)
                
                # Save conversation JSON
                conv_file = feeds_path / "conversations" / f"imported_{conv.id}.json"
                conv_file.parent.mkdir(parents=True, exist_ok=True)
                with open(conv_file, 'w', encoding='utf-8') as f:
                    json.dump(aios_conv, f, indent=2, default=str)
                
                # Save to DB
                from chat.schema import save_conversation, add_turn
                
                save_conversation(
                    session_id=aios_conv["session_id"],
                    name=aios_conv.get("name", ""),
                    channel="import",
                    state_snapshot=aios_conv.get("state_snapshot"),
                    source="copilot",
                )
                
                turn_count = 0
                for turn in aios_conv.get("turns", []):
                    add_turn(
                        session_id=aios_conv["session_id"],
                        user_message=turn.get("user", ""),
                        assistant_message=turn.get("assistant", ""),
                        feed_type=turn.get("feed_type", "conversational"),
                        context_level=turn.get("context_level", 0),
                    )
                    turn_count += 1
                
                total_turns += turn_count
                total_imported += 1
            
            if (i + 1) % 10 == 0:
                elapsed = time.time() - start_time
                print(f"  [{i+1}/{len(valid_sessions)}] {total_imported} convos, {total_turns} turns ({elapsed:.1f}s)")
                
        except Exception as e:
            total_failed += 1
            print(f"  FAILED {session_file.name}: {e}")
            continue
    
    elapsed = time.time() - start_time
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "total_files": len(all_sessions),
        "valid_files": len(valid_sessions),
        "imported_conversations": total_imported,
        "imported_turns": total_turns,
        "failed": total_failed,
        "skipped_empty": skipped_empty,
        "skipped_large": skipped_large,
        "elapsed_seconds": round(elapsed, 1),
    }
    
    # Save log
    log_path = PROJECT_ROOT / "data" / "vscode_import_log.json"
    with open(log_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"IMPORT COMPLETE")
    print(f"  Conversations: {total_imported}")
    print(f"  Turns: {total_turns}")
    print(f"  Failed: {total_failed}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Log: {log_path}")
    print(f"{'='*60}")
    
    return result


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    skip_mb = SKIP_LARGE_MB
    for arg in sys.argv:
        if arg.startswith("--skip-large"):
            try:
                skip_mb = float(sys.argv[sys.argv.index(arg) + 1])
            except (IndexError, ValueError):
                pass
    
    asyncio.run(import_all(dry_run=dry_run, skip_large_mb=skip_mb))
