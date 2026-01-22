"""
Gemini export parser - placeholder.
"""

from pathlib import Path
from typing import List
from .export_parser_base import ExportParserBase, ParsedConversation


class GeminiExportParser(ExportParserBase):
    def get_platform_name(self) -> str:
        return "Gemini"
    
    def validate(self, export_path: Path) -> bool:
        return False  # Placeholder
    
    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        return []  # Placeholder
