"""
Import service for converting AI exports to Nola format.
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


class ImportConvos:
    """Import conversations from other AI platforms into Nola."""
    
    def __init__(self, workspace_path: Path, stimuli_path: Path):
        self.workspace_path = workspace_path
        self.stimuli_path = stimuli_path
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
        
        # Convert to Nola format and save
        imported_count = 0
        failed_count = 0
        attachments_moved = 0
        
        for conv in conversations:
            try:
                # Convert to Nola format
                nola_conv = self._convert_to_nola_format(conv)
                
                # Save conversation
                conv_file = self.stimuli_path / "conversations" / f"imported_{conv.id}.json"
                conv_file.parent.mkdir(parents=True, exist_ok=True)
                
                with open(conv_file, 'w', encoding='utf-8') as f:
                    json.dump(nola_conv, f, indent=2, default=str)
                
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
    
    def _convert_to_nola_format(self, conv: ParsedConversation) -> Dict[str, Any]:
        """Convert parsed conversation to Nola's JSON format."""
        turns = []
        
        for i in range(0, len(conv.messages), 2):
            user_msg = conv.messages[i]
            assistant_msg = conv.messages[i + 1] if i + 1 < len(conv.messages) else None
            
            turn = {
                "timestamp": user_msg.timestamp.isoformat(),
                "user": user_msg.content,
                "assistant": assistant_msg.content if assistant_msg else "",
                "stimuli_type": "conversational",
                "context_level": 2
            }
            turns.append(turn)
        
        return {
            "session_id": f"imported_{conv.id}",
            "channel": "import",
            "started": conv.created_at.isoformat(),
            "name": conv.title,
            "turns": turns,
            "state_snapshot": {
                "imported_from": conv.metadata.get("platform", "unknown"),
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
