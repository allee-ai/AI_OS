"""
VS Code GitHub Copilot Chat export parser.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from .export_parser_base import ExportParserBase, ParsedConversation, ParsedMessage


class VSCodeExportParser(ExportParserBase):
    """Parser for VS Code GitHub Copilot chat sessions."""
    
    def get_platform_name(self) -> str:
        return "VSCode-Copilot"
    
    def validate(self, export_path: Path) -> bool:
        """Validate VS Code chat session format."""
        if export_path.is_file():
            try:
                with open(export_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Check for VS Code chat session structure
                    return ('version' in data and 
                            'requests' in data and 
                            'responderUsername' in data)
            except (json.JSONDecodeError, UnicodeDecodeError):
                return False
        elif export_path.is_dir():
            # Check if directory contains .json files with chat sessions
            json_files = list(export_path.glob('*.json'))
            if not json_files:
                return False
            return self.validate(json_files[0])
        return False
    
    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """
        Parse VS Code chat sessions.
        
        Args:
            export_path: Path to a single .json file or directory of .json files
            
        Returns:
            List of parsed conversations
        """
        conversations = []
        
        if export_path.is_file():
            json_files = [export_path]
        else:
            json_files = sorted(export_path.glob('*.json'))
        
        for json_file in json_files:
            try:
                conv = await self._parse_session_file(json_file)
                if conv:
                    conversations.append(conv)
            except Exception as e:
                print(f"Failed to parse {json_file.name}: {e}")
                continue
        
        return conversations
    
    async def _parse_session_file(self, file_path: Path) -> ParsedConversation:
        """Parse a single VS Code chat session file."""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract metadata
        session_id = file_path.stem
        requester = data.get('requesterUsername', 'User')
        responder = data.get('responderUsername', 'GitHub Copilot')
        
        # Parse messages from requests
        messages = []
        created_at = None
        updated_at = None
        
        for request in data.get('requests', []):
            # Parse user message
            message_data = request.get('message', {})
            user_text = message_data.get('text', '')
            
            # Try to extract timestamp (may not be present)
            # Use file modification time as fallback
            timestamp = datetime.fromtimestamp(file_path.stat().st_mtime)
            
            if user_text:
                messages.append(ParsedMessage(
                    role='user',
                    content=user_text,
                    timestamp=timestamp,
                    metadata={
                        'request_id': request.get('requestId'),
                        'variables': request.get('variableData', {}).get('variables', [])
                    }
                ))
            
            # Parse assistant response
            response = request.get('response', [])
            assistant_text_parts = []
            
            for resp_item in response:
                # Response can be string or object with value/string fields
                if isinstance(resp_item, dict):
                    if 'value' in resp_item:
                        if isinstance(resp_item['value'], str):
                            assistant_text_parts.append(resp_item['value'])
                        elif isinstance(resp_item['value'], dict):
                            text = resp_item['value'].get('value', '')
                            assistant_text_parts.append(text)
                    elif 'string' in resp_item:
                        assistant_text_parts.append(resp_item['string'])
                elif isinstance(resp_item, str):
                    assistant_text_parts.append(resp_item)
            
            assistant_text = '\n'.join(assistant_text_parts)
            
            if assistant_text:
                messages.append(ParsedMessage(
                    role='assistant',
                    content=assistant_text,
                    timestamp=timestamp,
                    metadata={
                        'request_id': request.get('requestId')
                    }
                ))
            
            # Track timestamps
            if created_at is None:
                created_at = timestamp
            updated_at = timestamp
        
        # Use file times as fallback
        if not created_at:
            created_at = datetime.fromtimestamp(file_path.stat().st_ctime)
        if not updated_at:
            updated_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Generate title from first user message or use session ID
        title = session_id
        if messages and messages[0].role == 'user':
            first_msg = messages[0].content[:100]
            title = first_msg if len(first_msg) < 100 else first_msg + '...'
        
        return ParsedConversation(
            id=session_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                'platform': 'vscode-copilot',
                'requester': requester,
                'responder': responder,
                'location': data.get('initialLocation', 'unknown'),
                'source_file': str(file_path)
            }
        )
