"""
Claude export parser - placeholder.
"""

from pathlib import Path
from typing import List
from .export_parser_base import ExportParserBase, ParsedConversation


class ClaudeExportParser(ExportParserBase):
    def get_platform_name(self) -> str:
        return "Claude"
    
    def validate(self, export_path: Path) -> bool:
        return False  # Placeholder
    
    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        return []  # Placeholder
