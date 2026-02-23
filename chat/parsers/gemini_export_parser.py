"""
Gemini (Google AI) export parser.
Handles Google Takeout exports for Gemini/Bard.

Google Takeout structure:
  Takeout/
    Gemini Apps/  (or "Google Bard/")
      [conversations stored as individual JSON files or in My Activity]

Possible formats:
  1. Individual JSON files per conversation with "textInput"/"modelResponse" or
     "inputText"/"outputText" structures
  2. My Activity JSON: array of activity items with "title", "subtitles" etc.
  3. BardChat export: JSON with "conversations" array

Since Google changes their Takeout format periodically, this parser tries
multiple strategies and picks whichever matches.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

from .export_parser_base import ExportParserBase, ParsedConversation, ParsedMessage


class GeminiExportParser(ExportParserBase):
    """Parser for Google Gemini/Bard conversation exports."""

    def get_platform_name(self) -> str:
        return "Gemini"

    def validate(self, export_path: Path) -> bool:
        """Check if this looks like a Gemini/Bard export."""
        if export_path.is_file() and export_path.suffix == ".json":
            return self._probe_json_file(export_path)

        if not export_path.is_dir():
            return False

        # Look for Gemini Apps or Bard folder in Takeout structure
        gemini_dir = self._find_gemini_dir(export_path)
        if gemini_dir:
            return True

        # Check for JSON files that look like Gemini conversations
        for jf in export_path.rglob("*.json"):
            if jf.parent.name in ("__MACOSX", ".DS_Store"):
                continue
            if self._probe_json_file(jf):
                return True

        return False

    def _probe_json_file(self, path: Path) -> bool:
        """Check if a JSON file looks like Gemini data."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read(4096)
            # Gemini indicators
            gemini_signals = [
                '"textInput"',
                '"modelResponse"',
                '"inputText"',
                '"outputText"',
                "Gemini",
                "Bard",
                '"gemini"',
                '"bard"',
            ]
            return any(s in raw for s in gemini_signals)
        except Exception:
            return False

    async def parse(self, export_path: Path) -> List[ParsedConversation]:
        """Parse Gemini export."""
        conversations: List[ParsedConversation] = []

        if export_path.is_file() and export_path.suffix == ".json":
            conversations.extend(self._parse_json_file(export_path))
        elif export_path.is_dir():
            # Try to find the Gemini directory
            gemini_dir = self._find_gemini_dir(export_path) or export_path

            # Collect all JSON files
            json_files = sorted(gemini_dir.rglob("*.json"))
            for jf in json_files:
                if any(skip in str(jf) for skip in ("__MACOSX", ".DS_Store")):
                    continue
                try:
                    conversations.extend(self._parse_json_file(jf))
                except Exception as e:
                    print(f"⚠ Gemini: skipping {jf.name}: {e}")
                    continue

        return conversations

    # ------------------------------------------------------------------
    # Directory detection
    # ------------------------------------------------------------------

    def _find_gemini_dir(self, root: Path) -> Optional[Path]:
        """Find the Gemini/Bard data directory in a Takeout export."""
        patterns = ["Gemini Apps", "Google Bard", "Gemini", "Bard"]
        for pattern in patterns:
            # Direct child
            candidate = root / pattern
            if candidate.is_dir():
                return candidate
            # Inside a Takeout folder
            candidate = root / "Takeout" / pattern
            if candidate.is_dir():
                return candidate

        # Recursively look for folders with these names
        for d in root.rglob("*"):
            if d.is_dir() and d.name in patterns:
                return d

        return None

    # ------------------------------------------------------------------
    # JSON parsing - multiple format strategies
    # ------------------------------------------------------------------

    def _parse_json_file(self, path: Path) -> List[ParsedConversation]:
        """Parse a single JSON file, trying multiple formats."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

        results: List[ParsedConversation] = []

        if isinstance(data, list):
            for item in data:
                if not isinstance(item, dict):
                    continue
                conv = self._parse_conversation_object(item, path)
                if conv and conv.messages:
                    results.append(conv)
            # If no conversations found from individual items,
            # try treating the whole array as one conversation
            if not results:
                conv = self._parse_activity_array(data, path)
                if conv and conv.messages:
                    results.append(conv)

        elif isinstance(data, dict):
            # Single conversation object
            conv = self._parse_conversation_object(data, path)
            if conv and conv.messages:
                results.append(conv)
            # Or a wrapper with "conversations" key
            elif "conversations" in data and isinstance(data["conversations"], list):
                for item in data["conversations"]:
                    conv = self._parse_conversation_object(item, path)
                    if conv and conv.messages:
                        results.append(conv)

        return results

    def _parse_conversation_object(self, obj: Dict, source_file: Path) -> Optional[ParsedConversation]:
        """Parse a single conversation-like object."""
        messages: List[ParsedMessage] = []

        # Strategy 1: textInput / modelResponse pairs
        if "textInput" in obj or "modelResponse" in obj:
            if "textInput" in obj:
                messages.append(ParsedMessage(
                    role="user",
                    content=str(obj["textInput"]),
                    timestamp=self._extract_timestamp(obj) or datetime.now(),
                ))
            if "modelResponse" in obj:
                resp = obj["modelResponse"]
                text = resp if isinstance(resp, str) else json.dumps(resp) if resp else ""
                if text.strip():
                    messages.append(ParsedMessage(
                        role="assistant",
                        content=text.strip(),
                        timestamp=self._extract_timestamp(obj) or datetime.now(),
                    ))

        # Strategy 2: inputText / outputText pairs
        elif "inputText" in obj or "outputText" in obj:
            if "inputText" in obj:
                messages.append(ParsedMessage(
                    role="user",
                    content=str(obj["inputText"]),
                    timestamp=self._extract_timestamp(obj) or datetime.now(),
                ))
            if "outputText" in obj:
                text = str(obj["outputText"])
                if text.strip():
                    messages.append(ParsedMessage(
                        role="assistant",
                        content=text.strip(),
                        timestamp=self._extract_timestamp(obj) or datetime.now(),
                    ))

        # Strategy 3: messages array (generic)
        elif "messages" in obj and isinstance(obj["messages"], list):
            for msg in obj["messages"]:
                if not isinstance(msg, dict):
                    continue
                role_raw = (
                    msg.get("role", "")
                    or msg.get("author", "")
                    or msg.get("sender", "")
                ).lower()
                role = "user" if role_raw in ("user", "human", "USER") else (
                    "assistant" if role_raw in ("assistant", "model", "MODEL", "bot") else None
                )
                if not role:
                    continue
                text = msg.get("text") or msg.get("content") or msg.get("parts", "")
                if isinstance(text, list):
                    text = "\n".join(str(p) for p in text)
                if not text or not str(text).strip():
                    continue
                messages.append(ParsedMessage(
                    role=role,
                    content=str(text).strip(),
                    timestamp=self._parse_iso_ts(msg.get("createTime") or msg.get("created_at")) or datetime.now(),
                ))

        # Strategy 4: parts array with role
        elif "parts" in obj and isinstance(obj["parts"], list):
            for part in obj["parts"]:
                if isinstance(part, dict) and "text" in part:
                    role_raw = part.get("role", "").lower()
                    role = "user" if role_raw in ("user", "human") else (
                        "assistant" if role_raw in ("model", "assistant") else None
                    )
                    if role and part["text"].strip():
                        messages.append(ParsedMessage(
                            role=role,
                            content=part["text"].strip(),
                            timestamp=datetime.now(),
                        ))

        if not messages:
            return None

        title = (
            obj.get("title")
            or obj.get("name")
            or obj.get("conversationTitle")
            or messages[0].content[:80]
        )
        conv_id = obj.get("id") or obj.get("conversationId") or f"gemini_{hash(title) & 0xFFFFFFFF}"
        created = self._extract_timestamp(obj) or messages[0].timestamp
        updated = messages[-1].timestamp

        return ParsedConversation(
            id=str(conv_id),
            title=title,
            messages=messages,
            created_at=created,
            updated_at=updated,
            metadata={"platform": "Gemini"},
        )

    def _parse_activity_array(self, items: List[Dict], source_file: Path) -> Optional[ParsedConversation]:
        """Try to parse a My Activity-style array as one conversation."""
        messages: List[ParsedMessage] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            # My Activity format has "title" as the user query
            title = item.get("title", "")
            if not title:
                continue
            # Strip common prefixes
            for prefix in ("Asked Gemini", "Asked Bard", "Searched for"):
                if title.startswith(prefix):
                    title = title[len(prefix):].strip().strip('"')
                    break

            ts = self._extract_timestamp(item) or datetime.now()
            messages.append(ParsedMessage(role="user", content=title, timestamp=ts))

            # Subtitles sometimes contain the response
            subtitles = item.get("subtitles", [])
            if subtitles and isinstance(subtitles, list):
                for sub in subtitles:
                    sub_text = sub.get("name", "") if isinstance(sub, dict) else str(sub)
                    if sub_text.strip():
                        messages.append(ParsedMessage(
                            role="assistant", content=sub_text.strip(), timestamp=ts,
                        ))

        if not messages:
            return None

        return ParsedConversation(
            id=f"gemini_activity_{source_file.stem}",
            title=f"Gemini Activity ({source_file.stem})",
            messages=messages,
            created_at=messages[0].timestamp,
            updated_at=messages[-1].timestamp,
            metadata={"platform": "Gemini", "format": "my_activity"},
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_timestamp(self, obj: Dict) -> Optional[datetime]:
        """Try multiple timestamp fields."""
        for field in ("createTime", "created_at", "timestamp", "time", "startTime", "date"):
            val = obj.get(field)
            if val is None:
                continue
            ts = self._parse_iso_ts(val) or self._parse_unix_ts(val)
            if ts:
                return ts
        return None

    def _parse_iso_ts(self, val) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    def _parse_unix_ts(self, val) -> Optional[datetime]:
        if val is None:
            return None
        try:
            return datetime.fromtimestamp(float(val))
        except (ValueError, TypeError, OSError):
            return None
