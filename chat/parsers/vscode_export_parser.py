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
        session_id = data.get('sessionId', file_path.stem)
        requester = data.get('requesterUsername', 'User')
        responder = data.get('responderUsername', 'GitHub Copilot')
        
        # Parse messages from requests
        messages = []
        created_at = None
        updated_at = None
        file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        for request in data.get('requests', []):
            # Parse user message
            message_data = request.get('message', {})
            user_text = message_data.get('text', '')
            
            # Use per-request timestamp (epoch ms), fall back to file mtime
            ts_ms = request.get('timestamp')
            timestamp = datetime.fromtimestamp(ts_ms / 1000) if ts_ms else file_mtime
            
            model_id = request.get('modelId', '')
            
            if user_text:
                messages.append(ParsedMessage(
                    role='user',
                    content=user_text,
                    timestamp=timestamp,
                    metadata={
                        'request_id': request.get('requestId'),
                        'model': model_id,
                        'variables': request.get('variableData', {}).get('variables', [])
                    }
                ))
            
            # Parse assistant response
            response = request.get('response', [])
            assistant_text_parts = []
            thinking_parts = []
            
            for resp_item in response:
                if isinstance(resp_item, str):
                    assistant_text_parts.append(resp_item)
                    continue
                if not isinstance(resp_item, dict):
                    continue
                
                kind = resp_item.get('kind')
                
                if kind == 'markdownContent':
                    # kind: "markdownContent" → content.value
                    content = resp_item.get('content', {})
                    text = content.get('value', '') if isinstance(content, dict) else ''
                    if text:
                        assistant_text_parts.append(text)
                
                elif kind == 'thinking':
                    # kind: "thinking" → value (reasoning trace)
                    val = resp_item.get('value', '')
                    if val:
                        thinking_parts.append(val)
                
                elif kind is None and 'value' in resp_item:
                    # No kind key — plain text part (value is a string)
                    val = resp_item['value']
                    if isinstance(val, str) and val.strip():
                        assistant_text_parts.append(val)
                    elif isinstance(val, dict):
                        text = val.get('value', '')
                        if text:
                            assistant_text_parts.append(text)
                
                elif kind is None and 'string' in resp_item:
                    assistant_text_parts.append(resp_item['string'])
                
                # Skip: toolInvocationSerialized, progressMessage,
                # mcpServersStarting, command, prepareToolInvocation, etc.
            
            assistant_text = '\n'.join(p for p in assistant_text_parts if p)
            thinking_text = '\n'.join(p for p in thinking_parts if p)
            
            if assistant_text:
                meta = {'request_id': request.get('requestId'), 'model': model_id}
                if thinking_text:
                    meta['thinking'] = thinking_text
                messages.append(ParsedMessage(
                    role='assistant',
                    content=assistant_text,
                    timestamp=timestamp,
                    metadata=meta
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
        
        # Use custom title if available, else first user message, else session ID
        title = data.get('customTitle', '')
        if not title and messages and messages[0].role == 'user':
            first_msg = messages[0].content[:100]
            title = first_msg if len(first_msg) < 100 else first_msg + '...'
        if not title:
            title = session_id
        
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
