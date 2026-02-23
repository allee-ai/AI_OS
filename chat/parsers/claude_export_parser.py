"""
Claude export parser.
Handles the official Claude data export which is a JSON file containing:

  [
    {
      "uuid": "...",
      "name": "Conversation Title",
      "created_at": "2024-01-15T10:30:00.000000+00:00",
      "updated_at": "2024-01-15T11:00:00.000000+00:00",
      "chat_messages": [
        {
          "uuid": "...",
          "text": "Hello!",
          "sender": "human",
          "created_at": "2024-01-15T10:30:00.000000+00:00",
          "updated_at": "2024-01-15T10:30:00.000000+00:00",
          "attachments": [],
          "files": []
        },
        {
          "uuid": "...",
          "text": "Hi there!",
          "sender": "assistant",
          "created_at": "2024-01-15T10:30:05.000000+00:00",
          ...
        }
      ]
    }
  ]
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .export_parser_base import ExportParserBase, ParsedConversation, ParsedMessage


class ClaudeExportParser(ExportParserBase):
    """Parser for Claude conversation exports."""

    def get_platform_name(self) -> str:
        return "Claude"

    def validate(self, export_path: Path) -> bool:
        """Check if this looks like a Claude export."""
        json_file = self._find_json_file(export_path)
        if not json_file:
            return False

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                raw = f.read(4096)
            # Claude exports have chat_messages with sender field
            return (
                raw.lstrip().startswith("[")
                and '"chat_messages"' in raw
                and '"sender"' in raw
            )
        except Exception:
            return False

    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """Parse Claude export."""
        json_file = self._find_json_file(export_path)
        if not json_file:
            return []

        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠ Claude: failed to read {json_file}: {e}")
            return []

        if not isinstance(data, list):
            return []

        conversations = []
        for conv_data in data:
            try:
                conv = self._parse_conversation(conv_data)
                if conv and conv.messages:
                    conversations.append(conv)
            except Exception as e:
                name = conv_data.get("name", "unknown")
                print(f"⚠ Claude: skipping '{name}': {e}")
                continue

        return conversations

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_json_file(self, export_path: Path) -> Optional[Path]:
        """Find the JSON file in the export."""
        if export_path.is_file() and export_path.suffix == ".json":
            return export_path

        if export_path.is_dir():
            # Look for JSON files in the directory
            json_files = [
                f for f in export_path.iterdir()
                if f.is_file() and f.suffix == ".json" and f.name not in ("user.json",)
            ]
            # Prefer conversations.json, then largest JSON file
            for jf in json_files:
                if "conversation" in jf.name.lower() or "claude" in jf.name.lower():
                    return jf
            if json_files:
                return max(json_files, key=lambda f: f.stat().st_size)

            # Check one level deeper (ZIP extraction)
            for child in export_path.iterdir():
                if child.is_dir() and child.name not in ("__MACOSX", ".DS_Store"):
                    result = self._find_json_file(child)
                    if result:
                        return result

        return None

    def _parse_conversation(self, conv_data: Dict) -> Optional[ParsedConversation]:
        """Parse a single Claude conversation object."""
        conv_id = conv_data.get("uuid") or conv_data.get("id", "")
        title = conv_data.get("name") or conv_data.get("title") or "Untitled"

        chat_messages = conv_data.get("chat_messages", [])
        if not chat_messages:
            return None

        messages: List[ParsedMessage] = []
        for msg in chat_messages:
            parsed = self._parse_message(msg)
            if parsed:
                messages.append(parsed)

        if not messages:
            return None

        created_at = self._parse_iso_ts(conv_data.get("created_at")) or messages[0].timestamp
        updated_at = self._parse_iso_ts(conv_data.get("updated_at")) or messages[-1].timestamp

        # Collect attachment info from messages
        attachments_info = []
        for msg in chat_messages:
            for att in msg.get("attachments", []):
                if att.get("file_name"):
                    attachments_info.append(att["file_name"])
            for f in msg.get("files", []):
                if f.get("file_name"):
                    attachments_info.append(f["file_name"])

        return ParsedConversation(
            id=conv_id,
            title=title,
            messages=messages,
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                "platform": "Claude",
                "model": conv_data.get("model", "unknown"),
                "attachments_referenced": attachments_info if attachments_info else None,
            },
        )

    def _parse_message(self, msg: Dict) -> Optional[ParsedMessage]:
        """Parse a single Claude message."""
        sender = msg.get("sender", "")

        # Map Claude roles to standard roles
        role_map = {"human": "user", "user": "user", "assistant": "assistant"}
        role = role_map.get(sender)
        if not role:
            return None

        text = msg.get("text", "")

        # Claude sometimes has content as a list
        if not text and "content" in msg:
            content = msg["content"]
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        parts.append(block)
                text = "\n".join(parts)
            elif isinstance(content, str):
                text = content

        if not text or not text.strip():
            return None

        timestamp = self._parse_iso_ts(msg.get("created_at")) or datetime.now()

        return ParsedMessage(
            role=role,
            content=text.strip(),
            timestamp=timestamp,
            metadata={"message_id": msg.get("uuid")},
        )

    def _parse_iso_ts(self, val) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
