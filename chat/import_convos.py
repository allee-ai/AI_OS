"""
Import service for converting AI exports to AI OS format.
"""

import asyncio
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from uuid import uuid4

from chat.parsers import (
    ExportParserBase,
    ParsedConversation,
    ChatGPTExportParser,
    ClaudeExportParser,
    GeminiExportParser,
    VSCodeExportParser
)
from chat.schema import save_conversation, add_turn


class ImportConvos:
    """Import conversations from other AI platforms into AI OS."""
    
    def __init__(self, workspace_path: Path, feeds_path: Path):
        self.workspace_path = workspace_path
        self.feeds_path = feeds_path
        self.parsers: List[ExportParserBase] = [
            ChatGPTExportParser(),
            ClaudeExportParser(),
            GeminiExportParser(),
            VSCodeExportParser(),
        ]
    
    def detect_platform(self, export_path: Path) -> Optional[ExportParserBase]:
        """Auto-detect which platform the export is from."""
        for parser in self.parsers:
            if parser.validate(export_path):
                return parser
        return None
    
    async def import_conversations(
        self,
        export_path: Path,
        platform: Optional[str] = None,
        organize_by_project: bool = True
    ) -> Dict[str, Any]:
        """
        Import conversations from an export.
        
        Args:
            export_path: Path to export folder or file
            platform: Platform name (auto-detect if None)
            organize_by_project: Whether to organize files by project
            
        Returns:
            Import summary with statistics
        """
        # Detect platform if not specified
        if platform:
            parser = next((p for p in self.parsers if p.get_platform_name().lower() == platform.lower()), None)
            if not parser:
                raise ValueError(f"Unknown platform: {platform}")
        else:
            parser = self.detect_platform(export_path)
            if not parser:
                raise ValueError(f"Could not detect platform for: {export_path}")
        
        # Parse conversations
        conversations = await parser.parse(export_path)
        
        # Convert to AI OS format and save
        imported_count = 0
        failed_count = 0
        attachments_moved = 0
        
        for conv in conversations:
            try:
                # Convert to AI OS format
                aios_conv = self._convert_to_aios_format(conv)
                
                # Save conversation to JSON file
                conv_file = self.feeds_path / "conversations" / f"imported_{conv.id}.json"
                conv_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(conv_file, 'w', encoding='utf-8') as f:
                    json.dump(aios_conv, f, indent=2, default=str)
                
                # Save to SQLite DB with source tracking
                platform_name = parser.get_platform_name().lower()
                source_map = {
                    "chatgpt": "chatgpt",
                    "claude": "claude",
                    "gemini": "gemini",
                    "vscode": "copilot",
                    "copilot": "copilot",
                    "vscode-copilot": "copilot",
                }
                source = source_map.get(platform_name, platform_name)
                
                save_conversation(
                    session_id=aios_conv["session_id"],
                    name=aios_conv["name"],
                    channel="import",
                    state_snapshot=aios_conv.get("state_snapshot"),
                    source=source,
                )
                
                # Add turns to DB
                for turn in aios_conv.get("turns", []):
                    add_turn(
                        session_id=aios_conv["session_id"],
                        user_message=turn.get("user", ""),
                        assistant_message=turn.get("assistant", ""),
                        feed_type=turn.get("feed_type", "conversational"),
                        context_level=turn.get("context_level", 0),
                    )
                
                # Handle attachments
                if conv.attachments and organize_by_project:
                    attachments_moved += self._organize_attachments(conv)
                
                imported_count += 1
                
            except Exception as e:
                print(f"Failed to import conversation {conv.id}: {e}")
                failed_count += 1
                continue
        
        return {
            "platform": parser.get_platform_name(),
            "total_conversations": len(conversations),
            "imported": imported_count,
            "failed": failed_count,
            "attachments_moved": attachments_moved,
            "timestamp": datetime.now().isoformat()
        }
    
    def _convert_to_aios_format(self, conv: ParsedConversation) -> Dict[str, Any]:
        """Convert parsed conversation to AI OS's JSON format.
        
        Pairs messages into user/assistant turns. Handles:
        - Non-alternating roles (consecutive user or assistant messages)
        - Missing counterparts (user with no response, or assistant with no prompt)
        """
        turns = []
        messages = conv.messages
        i = 0
        
        while i < len(messages):
            msg = messages[i]
            
            if msg.role == "user":
                # Look ahead for assistant response
                assistant_text = ""
                if i + 1 < len(messages) and messages[i + 1].role == "assistant":
                    assistant_text = messages[i + 1].content
                    i += 2
                    # Absorb consecutive assistant messages (multi-part response)
                    while i < len(messages) and messages[i].role == "assistant":
                        assistant_text += "\n\n" + messages[i].content
                        i += 1
                else:
                    # User message with no assistant response
                    i += 1
                
                turns.append({
                    "timestamp": msg.timestamp.isoformat(),
                    "user": msg.content,
                    "assistant": assistant_text,
                    "feed_type": "conversational",
                    "context_level": 2
                })
            
            elif msg.role == "assistant":
                # Assistant message with no preceding user message
                turns.append({
                    "timestamp": msg.timestamp.isoformat(),
                    "user": "",
                    "assistant": msg.content,
                    "feed_type": "conversational",
                    "context_level": 2
                })
                i += 1
            
            else:
                # Skip system / tool / unknown roles
                i += 1
        
        return {
            "session_id": f"imported_{conv.id}",
            "channel": "import",
            "started": conv.created_at.isoformat(),
            "name": conv.title,
            "turns": turns,
            "state_snapshot": {
                "imported_from": (conv.metadata or {}).get("platform", "unknown"),
                "original_id": conv.id
            },
            "last_updated": conv.updated_at.isoformat()
        }
    
    def _organize_attachments(self, conv: ParsedConversation) -> int:
        """Organize attachments into workspace folders."""
        if not conv.attachments:
            return 0
        
        # Create media folder for this conversation
        media_folder = self.workspace_path / "imported_media" / conv.id
        media_folder.mkdir(parents=True, exist_ok=True)
        
        moved_count = 0
        for attachment in conv.attachments:
            try:
                dest = media_folder / attachment.name
                shutil.copy2(attachment, dest)
                moved_count += 1
            except Exception as e:
                print(f"Failed to move attachment {attachment}: {e}")
                continue
        
        return moved_count
