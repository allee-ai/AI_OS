"""
Base parser interface for AI conversation exports.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


@dataclass
class ParsedMessage:
    """A single message in a conversation."""
    role: str  # 'user' or 'assistant' or 'system'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ParsedConversation:
    """A parsed conversation from an export."""
    id: str
    title: str
    messages: List[ParsedMessage]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[Dict[str, Any]] = None
    attachments: Optional[List[Path]] = None  # Paths to audio/video/files


class ExportParserBase(ABC):
    """Abstract base class for export parsers."""
    
    @abstractmethod
    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """
        Parse an export folder/file into structured conversations.
        
        Args:
            export_path: Path to export folder or file
            
        Returns:
            List of parsed conversations
        """
        pass
    
    @abstractmethod
    def validate(self, export_path: Path) -> bool:
        """
        Validate that the export is in the expected format.
        
        Args:
            export_path: Path to export folder or file
            
        Returns:
            True if valid format for this parser
        """
        pass
    
    @abstractmethod
    def get_platform_name(self) -> str:
        """Return the platform name (e.g., 'ChatGPT', 'Claude', 'Gemini')."""
        pass
