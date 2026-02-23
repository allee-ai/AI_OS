"""
ChatGPT export parser.
Handles the official ChatGPT data export ZIP which contains:
  - conversations.json  (primary — raw JSON array of conversations)
  - chat.html           (fallback — rendered HTML view)
  - user.json           (user metadata)

conversations.json format:
  [
    {
      "title": "...",
      "create_time": 1700000000.0,
      "update_time": 1700000000.0,
      "conversation_id": "uuid",
      "mapping": {
        "node_id": {
          "id": "...",
          "message": {
            "author": {"role": "user"|"assistant"|"system"|"tool"},
            "content": {"content_type": "text", "parts": ["..."]},
            "create_time": 1700000000.0
          },
          "parent": "parent_node_id",
          "children": ["child_node_id"]
        }
      },
      "current_node": "node_id"
    }
  ]
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .export_parser_base import ExportParserBase, ParsedConversation, ParsedMessage


class ChatGPTExportParser(ExportParserBase):
    """Parser for ChatGPT export format."""

    def get_platform_name(self) -> str:
        return "ChatGPT"

    def validate(self, export_path: Path) -> bool:
        """Check if this looks like a ChatGPT export."""
        if export_path.is_file():
            # Could be conversations.json directly
            if export_path.name == "conversations.json":
                return True
            # Or a JSON file with conversation-like structure
            if export_path.suffix == ".json":
                return self._probe_json_file(export_path)
            return False

        if not export_path.is_dir():
            return False

        # ChatGPT ZIP extracts to a folder with conversations.json
        if (export_path / "conversations.json").exists():
            return True

        # Legacy: chat.html + user.json
        if (export_path / "chat.html").exists() and (export_path / "user.json").exists():
            return True

        # Check subdirectories (ZIP may extract into a nested folder)
        for child in export_path.iterdir():
            if child.is_dir() and child.name not in ("__MACOSX", ".DS_Store"):
                if (child / "conversations.json").exists():
                    return True

        return False

    def _probe_json_file(self, path: Path) -> bool:
        """Quick check if a JSON file looks like ChatGPT conversations."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read(4096)
            # Must be an array of objects with "mapping" key
            if '"mapping"' in raw and '"title"' in raw and raw.lstrip().startswith("["):
                return True
        except Exception:
            pass
        return False

    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """Parse ChatGPT export."""
        json_data = self._load_conversations_json(export_path)
        if not json_data:
            return []

        conversations = []
        for conv_data in json_data:
            try:
                conv = self._parse_conversation(conv_data, export_path)
                if conv and conv.messages:
                    conversations.append(conv)
            except Exception as e:
                title = conv_data.get("title", "unknown")
                print(f"⚠ ChatGPT: skipping '{title}': {e}")
                continue

        return conversations

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load_conversations_json(self, export_path: Path) -> Optional[List[Dict]]:
        """Find and load conversations.json from various locations."""
        candidates: List[Path] = []

        if export_path.is_file():
            candidates.append(export_path)
        elif export_path.is_dir():
            # Direct
            candidates.append(export_path / "conversations.json")
            # Nested one level (ZIP extraction artifact)
            for child in export_path.iterdir():
                if child.is_dir() and child.name not in ("__MACOSX", ".DS_Store"):
                    candidates.append(child / "conversations.json")

        for path in candidates:
            if path.exists() and path.is_file():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        return data
                except (json.JSONDecodeError, OSError) as e:
                    print(f"⚠ ChatGPT: failed to read {path}: {e}")
                    continue

        return None

    # ------------------------------------------------------------------
    # Conversation parsing
    # ------------------------------------------------------------------

    def _parse_conversation(self, conv_data: Dict, export_path: Path) -> Optional[ParsedConversation]:
        """Parse a single conversation object."""
        conv_id = (
            conv_data.get("conversation_id")
            or conv_data.get("id")
            or conv_data.get("uuid")
        )
        title = conv_data.get("title") or "Untitled"

        # Extract messages from mapping tree
        messages: List[ParsedMessage] = []
        if "mapping" in conv_data:
            messages = self._extract_from_mapping(conv_data["mapping"])
        elif "messages" in conv_data and isinstance(conv_data["messages"], list):
            for msg in conv_data["messages"]:
                parsed = self._parse_message(msg)
                if parsed:
                    messages.append(parsed)

        if not messages:
            return None

        # Timestamps
        created_at = self._parse_unix_ts(conv_data.get("create_time")) or messages[0].timestamp
        updated_at = self._parse_unix_ts(conv_data.get("update_time")) or messages[-1].timestamp

        # Attachments
        attachments = self._find_attachments(conv_id, export_path) if conv_id else []

        return ParsedConversation(
            id=conv_id or f"chatgpt_{hash(title) & 0xFFFFFFFF}",
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                "platform": "ChatGPT",
                "model": conv_data.get("default_model_slug", "unknown"),
            },
            attachments=attachments if attachments else None,
        )

    # ------------------------------------------------------------------
    # Mapping tree -> flat message list
    # ------------------------------------------------------------------

    def _extract_from_mapping(self, mapping: Dict) -> List[ParsedMessage]:
        """Walk the mapping tree root->leaf along the main thread."""
        # Find root node (no parent or parent not in mapping)
        root_id = None
        for node_id, node in mapping.items():
            parent = node.get("parent")
            if parent is None or parent not in mapping:
                root_id = node_id
                break

        if not root_id:
            return []

        messages: List[ParsedMessage] = []
        visited: set = set()
        self._walk_tree(mapping, root_id, messages, visited)
        return messages

    def _walk_tree(self, mapping: Dict, node_id: str, out: List[ParsedMessage], visited: set):
        """DFS through the main conversation thread."""
        if node_id in visited:
            return
        visited.add(node_id)

        node = mapping.get(node_id)
        if not node:
            return

        msg_data = node.get("message")
        if msg_data:
            parsed = self._parse_message_node(msg_data)
            if parsed:
                out.append(parsed)

        # Follow first child (main thread)
        children = node.get("children", [])
        if children:
            self._walk_tree(mapping, children[0], out, visited)

    # ------------------------------------------------------------------
    # Message parsing
    # ------------------------------------------------------------------

    def _parse_message_node(self, msg: Dict) -> Optional[ParsedMessage]:
        """Parse a message from inside a mapping node."""
        author = msg.get("author", {})
        role = author.get("role", "unknown")

        # Only keep user + assistant messages
        if role not in ("user", "assistant"):
            return None

        content = msg.get("content", {})
        text = self._extract_content_text(content)
        if not text or not text.strip():
            return None

        timestamp = self._parse_unix_ts(msg.get("create_time")) or datetime.now()

        model_slug = None
        meta = msg.get("metadata")
        if isinstance(meta, dict):
            model_slug = meta.get("model_slug")

        return ParsedMessage(
            role=role,
            content=text.strip(),
            timestamp=timestamp,
            metadata={"model": model_slug, "message_id": msg.get("id")},
        )

    def _parse_message(self, msg: Dict) -> Optional[ParsedMessage]:
        """Parse a message from a flat messages array (alternative format)."""
        role = (
            msg.get("role")
            or (msg.get("author", {}) or {}).get("role")
            or msg.get("sender")
        )
        if role not in ("user", "assistant"):
            return None

        text = None
        if "content" in msg:
            c = msg["content"]
            if isinstance(c, dict):
                text = self._extract_content_text(c)
            elif isinstance(c, str):
                text = c
        text = text or msg.get("text") or msg.get("message")
        if isinstance(text, dict):
            text = text.get("text") or text.get("content")

        if not text or not text.strip():
            return None

        timestamp = (
            self._parse_unix_ts(msg.get("create_time"))
            or self._parse_iso_ts(msg.get("created_at"))
            or self._parse_unix_ts(msg.get("timestamp"))
            or datetime.now()
        )

        return ParsedMessage(role=role, content=text.strip(), timestamp=timestamp)

    def _extract_content_text(self, content: Dict) -> str:
        """Extract plain text from a content object with parts[]."""
        parts = content.get("parts", [])
        text_parts = []
        for part in parts:
            if isinstance(part, str):
                text_parts.append(part)
            elif isinstance(part, dict):
                t = part.get("text") or part.get("content")
                if t:
                    text_parts.append(str(t))
        return "\n".join(text_parts)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_unix_ts(self, val) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromtimestamp(float(val))
        except (ValueError, TypeError, OSError):
            return None

    def _parse_iso_ts(self, val) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _find_attachments(self, conversation_id: str, export_path: Path) -> List[Path]:
        """Find attachment files in UUID-named folders."""
        if not export_path.is_dir():
            return []
        attachments = []
        uuid_re = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        for item in export_path.iterdir():
            if item.is_dir() and uuid_re.match(item.name):
                for f in item.rglob("*"):
                    if f.is_file():
                        attachments.append(f)
        return attachments
