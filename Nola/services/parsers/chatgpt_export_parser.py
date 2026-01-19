"""
ChatGPT export parser.
Handles chat.html containing JSON conversation data + UUID folders with attachments.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup

from .export_parser_base import ExportParserBase, ParsedConversation, ParsedMessage


class ChatGPTExportParser(ExportParserBase):
    """Parser for ChatGPT export format (chat.html with embedded JSON)."""
    
    def get_platform_name(self) -> str:
        return "ChatGPT"
    
    def validate(self, export_path: Path) -> bool:
        """Check if this is a valid ChatGPT export."""
        if not export_path.is_dir():
            return False
        
        # ChatGPT exports have chat.html and user.json
        chat_html = export_path / "chat.html"
        user_json = export_path / "user.json"
        
        return chat_html.exists() and user_json.exists()
    
    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """Parse ChatGPT export folder."""
        chat_html_path = export_path / "chat.html"
        
        if not chat_html_path.exists():
            raise ValueError(f"chat.html not found in {export_path}")
        
        # Read HTML and extract JSON
        with open(chat_html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Extract JSON data from JavaScript variable
        json_data = self._extract_json_from_html(html_content)
        
        if not json_data:
            return []
        
        # Parse conversations
        conversations = []
        for conv_data in json_data:
            try:
                conv = self._parse_conversation_json(conv_data, export_path)
                if conv:
                    conversations.append(conv)
            except Exception as e:
                print(f"Failed to parse conversation '{conv_data.get('title', 'unknown')}': {e}")
                continue
        
        return conversations
    
    def _extract_json_from_html(self, html_content: str) -> Optional[List[Dict]]:
        """Extract JSON data from HTML script tag with multiple fallback strategies."""
        
        # Strategy 1: Try known variable names
        variable_patterns = [
            r'var jsonData\s*=\s*',
            r'const jsonData\s*=\s*',
            r'let jsonData\s*=\s*',
            r'var conversationData\s*=\s*',
            r'const conversationData\s*=\s*',
            r'window\.conversationData\s*=\s*'
        ]
        
        for pattern in variable_patterns:
            match = re.search(pattern, html_content)
            if match:
                data = self._extract_json_from_position(html_content, match.end())
                if data:
                    return data
        
        # Strategy 2: Look for large JSON arrays in script tags
        script_pattern = r'<script[^>]*>(.*?)</script>'
        for script_match in re.finditer(script_pattern, html_content, re.DOTALL):
            script_content = script_match.group(1)
            # Look for arrays that start with conversation-like objects
            if re.search(r'\[\s*\{\s*["\']id["\']', script_content):
                data = self._extract_json_from_position(script_content, 0)
                if data and isinstance(data, list) and len(data) > 0:
                    # Validate it looks like conversation data
                    if self._validate_conversation_structure(data[0]):
                        return data
        
        # Strategy 3: Try to find any large JSON array
        # Look for patterns like: [{..."id":"..."..."title":"..."...}]
        array_pattern = r'\[\s*\{\s*"[^"]+"\s*:\s*"[^"]*"'
        for match in re.finditer(array_pattern, html_content):
            data = self._extract_json_from_position(html_content, match.start())
            if data and isinstance(data, list) and len(data) > 0:
                if self._validate_conversation_structure(data[0]):
                    return data
        
        return None
    
    def _extract_json_from_position(self, content: str, start_pos: int) -> Optional[List[Dict]]:
        """Extract JSON array starting from a specific position."""
        # Skip whitespace
        while start_pos < len(content) and content[start_pos] in ' \t\n\r':
            start_pos += 1
        
        if start_pos >= len(content) or content[start_pos] != '[':
            return None
        
        # Match brackets properly
        bracket_count = 0
        in_string = False
        escape_next = False
        json_end = start_pos
        
        for i in range(start_pos, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '[' or char == '{':
                    bracket_count += 1
                elif char == ']' or char == '}':
                    bracket_count -= 1
                    if bracket_count == 0:
                        json_end = i + 1
                        break
        
        if bracket_count != 0:
            return None
        
        json_str = content[start_pos:json_end]
        
        try:
            data = json.loads(json_str)
            return data if isinstance(data, list) else None
        except json.JSONDecodeError:
            return None
    
    def _validate_conversation_structure(self, obj: Dict) -> bool:
        """Check if an object looks like a conversation."""
        if not isinstance(obj, dict):
            return False
        
        # Must have common conversation fields
        has_id = 'id' in obj or 'conversation_id' in obj
        has_title = 'title' in obj
        has_mapping = 'mapping' in obj
        has_messages = 'messages' in obj
        
        return has_id and (has_title or has_mapping or has_messages)
    
    def _parse_conversation_json(self, conv_data: Dict, export_path: Path) -> Optional[ParsedConversation]:
        """Parse a single conversation from JSON data with flexible field handling."""
        # Flexible ID extraction
        conv_id = conv_data.get('id') or conv_data.get('conversation_id') or conv_data.get('uuid')
        
        # Flexible title extraction
        title = conv_data.get('title') or conv_data.get('name') or 'Untitled Conversation'
        
        # Try different message structures
        messages = []
        
        # Strategy 1: mapping structure (current format)
        if 'mapping' in conv_data:
            mapping = conv_data['mapping']
            current_node = conv_data.get('current_node')
            messages = self._extract_messages_from_mapping(mapping, current_node)
        
        # Strategy 2: direct messages array (potential future format)
        elif 'messages' in conv_data:
            messages_data = conv_data['messages']
            if isinstance(messages_data, list):
                for msg_data in messages_data:
                    msg = self._parse_message_flexible(msg_data)
                    if msg:
                        messages.append(msg)
        
        # Strategy 3: conversation_thread structure
        elif 'conversation_thread' in conv_data:
            thread = conv_data['conversation_thread']
            if isinstance(thread, list):
                for msg_data in thread:
                    msg = self._parse_message_flexible(msg_data)
                    if msg:
                        messages.append(msg)
        
        if not messages:
            return None
        
        # Get timestamps
        created_at = messages[0].timestamp if messages else datetime.now()
        updated_at = messages[-1].timestamp if messages else datetime.now()
        
        # Try to extract create_time from conversation metadata
        if 'create_time' in conv_data:
            try:
                created_at = datetime.fromtimestamp(conv_data['create_time'])
            except (ValueError, TypeError):
                pass
        
        if 'update_time' in conv_data:
            try:
                updated_at = datetime.fromtimestamp(conv_data['update_time'])
            except (ValueError, TypeError):
                pass
        
        # Find attachments in UUID folders
        attachments = self._find_attachments(conv_id, export_path) if conv_id else []
        
        return ParsedConversation(
            id=conv_id or f"chatgpt_{hash(title)}",
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                "platform": "ChatGPT",
                "model": conv_data.get('default_model_slug') or conv_data.get('model') or 'unknown'
            },
            attachments=attachments
        )
    
    def _parse_message_flexible(self, message_data: Dict) -> Optional[ParsedMessage]:
        """Parse message with flexible field handling for format changes."""
        # Try different role locations
        role = None
        if 'author' in message_data:
            author = message_data['author']
            role = author.get('role') if isinstance(author, dict) else author
        elif 'role' in message_data:
            role = message_data['role']
        elif 'sender' in message_data:
            role = message_data['sender']
        
        if not role:
            role = 'user'  # default fallback
        
        # Try different content locations
        text = None
        
        # Current format: content.parts array
        if 'content' in message_data:
            content = message_data['content']
            if isinstance(content, dict):
                content_type = content.get('content_type', 'text')
                parts = content.get('parts', [])
                if parts:
                    text = self._extract_text_from_parts(parts)
            elif isinstance(content, str):
                text = content
        
        # Alternative: direct text field
        elif 'text' in message_data:
            text = message_data['text']
        
        # Alternative: message field
        elif 'message' in message_data:
            msg = message_data['message']
            if isinstance(msg, dict):
                text = msg.get('text') or msg.get('content')
            else:
                text = str(msg)
        
        if not text or not text.strip():
            return None
        
        # Get timestamp flexibly
        timestamp = datetime.now()
        for time_field in ['create_time', 'created_at', 'timestamp', 'time']:
            if time_field in message_data:
                try:
                    time_value = message_data[time_field]
                    if isinstance(time_value, (int, float)):
                        timestamp = datetime.fromtimestamp(time_value)
                    elif isinstance(time_value, str):
                        timestamp = datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                    break
                except (ValueError, TypeError):
                    continue
        
        return ParsedMessage(
            role=role,
            content=text.strip(),
            timestamp=timestamp,
            metadata={
                'model': message_data.get('metadata', {}).get('model_slug') if isinstance(message_data.get('metadata'), dict) else None,
                'message_id': message_data.get('id')
            }
        )
    
    def _extract_text_from_parts(self, parts: list) -> str:
        """Extract text from parts array, handling various content types."""
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                # Handle multimodal content
                if 'text' in part:
                    text_parts.append(part['text'])
                elif 'content' in part:
                    text_parts.append(str(part['content']))
                elif part.get('content_type') == 'text':
                    text_parts.append(part.get('text', ''))
        return '\n'.join(text_parts)
    
    def _extract_messages_from_mapping(self, mapping: Dict, current_node: Optional[str]) -> List[ParsedMessage]:
        """Extract messages in order from the mapping tree."""
        messages = []
        
        # Start from root and traverse to current node
        # Find the root (node with no parent)
        root_id = None
        for node_id, node_data in mapping.items():
            if not node_data.get('parent'):
                root_id = node_id
                break
        
        if not root_id:
            return messages
        
        # Traverse from root to current_node
        visited = set()
        self._traverse_messages(mapping, root_id, messages, visited)
        
        return messages
    
    def _traverse_messages(self, mapping: Dict, node_id: str, messages: List[ParsedMessage], visited: set):
        """Recursively traverse message tree."""
        if node_id in visited:
            return
        visited.add(node_id)
        
        node = mapping.get(node_id)
        if not node:
            return
        
        # Extract message from node
        message_data = node.get('message')
        if message_data and message_data.get('content'):
            msg = self._parse_message_node(message_data)
            if msg:
                messages.append(msg)
        
        # Traverse children (follow the first child if multiple)
        children = node.get('children', [])
        if children:
            # Follow first child (main conversation thread)
            self._traverse_messages(mapping, children[0], messages, visited)
    
    def _parse_message_node(self, message_data: Dict) -> Optional[ParsedMessage]:
        """Parse a message from the mapping node."""
        author = message_data.get('author', {})
        role = author.get('role', 'user')
        
        # Extract content
        content = message_data.get('content', {})
        content_type = content.get('content_type', 'text')
        
        if content_type == 'text':
            parts = content.get('parts', [])
            text = '\n'.join(str(p) for p in parts if p)
        elif content_type == 'multimodal_text':
            # Handle multimodal content (text + images)
            parts = content.get('parts', [])
            text_parts = []
            for part in parts:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and part.get('content_type') == 'text':
                    text_parts.append(part.get('text', ''))
            text = '\n'.join(text_parts)
        else:
            text = str(content)
        
        if not text or not text.strip():
            return None
        
        # Get timestamp
        create_time = message_data.get('create_time')
        if create_time:
            timestamp = datetime.fromtimestamp(create_time)
        else:
            timestamp = datetime.now()
        
        return ParsedMessage(
            role=role,
            content=text.strip(),
            timestamp=timestamp,
            metadata={
                'model': message_data.get('metadata', {}).get('model_slug'),
                'message_id': message_data.get('id')
            }
        )
    
    def _find_attachments(self, conversation_id: str, export_path: Path) -> List[Path]:
        """Find attachment files in UUID folders."""
        attachments = []
        
        # Look for folders with UUID pattern
        for item in export_path.iterdir():
            if item.is_dir() and self._is_uuid_folder(item.name):
                # Check if this folder might belong to this conversation
                # (In actual implementation, would need to match via file references)
                for file in item.rglob('*'):
                    if file.is_file():
                        attachments.append(file)
        
        return attachments
    
    def _is_uuid_folder(self, name: str) -> bool:
        """Check if folder name looks like a UUID."""
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        return bool(re.match(uuid_pattern, name, re.IGNORECASE))
