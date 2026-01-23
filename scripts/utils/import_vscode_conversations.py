#!/usr/bin/env python3
"""
Import all VS Code GitHub Copilot conversations into AI OS.

This script:
1. Finds all VS Code chat sessions from Library
2. Parses them using the VSCodeExportParser
3. Imports them into AI OS's Stimuli/conversations folder
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import agent modules
sys.path.insert(0, str(Path(__file__).parent))

from chat.import_convos import ImportConvos
from chat.parsers import VSCodeExportParser


def find_vscode_chat_sessions() -> list[Path]:
    """Find all VS Code chat session directories."""
    home = Path.home()
    vscode_dir = home / "Library/Application Support/Code/User"
    
    chat_dirs = []
    
    # Empty window chat sessions
    empty_window_chats = vscode_dir / "globalStorage/emptyWindowChatSessions"
    if empty_window_chats.exists():
        chat_dirs.append(empty_window_chats)
        print(f"Found empty window chats: {empty_window_chats}")
    
    # Workspace-specific chat sessions
    workspace_storage = vscode_dir / "workspaceStorage"
    if workspace_storage.exists():
        for workspace_dir in workspace_storage.iterdir():
            chat_sessions = workspace_dir / "chatSessions"
            if chat_sessions.exists() and list(chat_sessions.glob("*.json")):
                chat_dirs.append(chat_sessions)
                json_count = len(list(chat_sessions.glob("*.json")))
                print(f"Found workspace chats: {workspace_dir.name} ({json_count} sessions)")
    
    return chat_dirs


async def main():
    """Import all VS Code conversations."""
    print("=" * 80)
    print("VS Code Conversations Import to AI OS")
    print("=" * 80)
    
    # Setup paths
    base_dir = Path(__file__).parent
    workspace_path = base_dir / "agent/workspace"
    stimuli_path = base_dir / "agent/Stimuli"
    
    # Ensure directories exist
    workspace_path.mkdir(parents=True, exist_ok=True)
    stimuli_path.mkdir(parents=True, exist_ok=True)
    
    # Find all chat session directories
    print("\nSearching for VS Code chat sessions...")
    chat_dirs = find_vscode_chat_sessions()
    
    if not chat_dirs:
        print("No VS Code chat sessions found!")
        return
    
    print(f"\nFound {len(chat_dirs)} chat session locations")
    
    # Count total conversations
    total_files = sum(len(list(d.glob("*.json"))) for d in chat_dirs)
    print(f"Total conversation files: {total_files}")
    
    # Create import service
    import_convos = ImportConvos(workspace_path, stimuli_path)

    # Import from each directory
    all_results = []
    total_imported = 0
    total_failed = 0
    
    print("\n" + "=" * 80)
    print("Starting import...")
    print("=" * 80)
    
    for i, chat_dir in enumerate(chat_dirs, 1):
        print(f"\n[{i}/{len(chat_dirs)}] Processing: {chat_dir.name}")
        print(f"  Path: {chat_dir}")
        
        try:
            result = await import_convos.import_conversations(
                export_path=chat_dir,
                platform="vscode-copilot",
                organize_by_project=True
            )
            
            all_results.append(result)
            total_imported += result['imported']
            total_failed += result['failed']
            
            print(f"  ✓ Imported: {result['imported']}")
            print(f"  ✗ Failed: {result['failed']}")
            
        except Exception as e:
            print(f"  ✗ Error processing {chat_dir.name}: {e}")
            total_failed += len(list(chat_dir.glob("*.json")))
    
    # Summary
    print("\n" + "=" * 80)
    print("Import Summary")
    print("=" * 80)
    print(f"Total files found: {total_files}")
    print(f"Successfully imported: {total_imported}")
    print(f"Failed: {total_failed}")
    print(f"Import location: {stimuli_path / 'conversations'}")
    
    # Save import log
    log_file = base_dir / "vscode_import_log.json"
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "total_files": total_files,
        "imported": total_imported,
        "failed": total_failed,
        "results": all_results
    }
    
    with open(log_file, 'w') as f:
        json.dump(log_data, f, indent=2, default=str)
    
    print(f"\nImport log saved to: {log_file}")
    print("\n✓ Import complete!")


if __name__ == "__main__":
    asyncio.run(main())
