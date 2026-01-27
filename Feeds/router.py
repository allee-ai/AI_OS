"""
Feeds Router - Universal API Adapter Layer

Config-driven integration with external APIs.
Add new feed sources by dropping a YAML file in sources/.

LLM only fills probabilistic slots (subject, body).
Everything else (routing, auth, threading) is deterministic.
"""

import yaml
import json
import re
import base64
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod
import urllib.request
import urllib.parse
from email.mime.text import MIMEText


FEEDS_DIR = Path(__file__).parent
SOURCES_DIR = FEEDS_DIR / "sources"
TOKENS_DIR = Path.home() / ".aios" / "tokens"


@dataclass
class NormalizedMessage:
    """Universal message format from any source"""
    platform: str
    id: str
    thread_id: str
    sender_id: str
    sender_name: str
    subject: Optional[str]
    body: str
    timestamp: datetime
    raw: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "id": self.id,
            "thread_id": self.thread_id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "subject": self.subject,
            "body": self.body,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass 
class ResponseTemplate:
    """Template with deterministic fields + LLM slots"""
    # Deterministic (filled by code)
    platform: str
    to: str
    to_name: str
    thread_id: str
    in_reply_to: Optional[str] = None
    sender_profile: Dict[str, Any] = field(default_factory=dict)
    user_profile: Dict[str, Any] = field(default_factory=dict)
    conversation: List[Dict] = field(default_factory=list)
    
    # Probabilistic (filled by LLM)
    subject: Optional[str] = None
    body: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "to": self.to,
            "to_name": self.to_name,
            "thread_id": self.thread_id,
            "in_reply_to": self.in_reply_to,
            "subject": self.subject,
            "body": self.body,
        }


@dataclass
class SourceConfig:
    """Parsed YAML source configuration"""
    name: str
    type: str  # "rest", "imap", "websocket"
    auth: Dict[str, Any]
    pull: Dict[str, Any]
    push: Dict[str, Any]
    poll_interval: int = 300  # seconds
    enabled: bool = True


class FeedsRouter:
    """
    Universal router for external API integrations.
    
    Usage:
        router = FeedsRouter()
        messages = router.pull_all()
        
        for msg in messages:
            response = generate_response(msg)  # LLM fills slots
            router.push(msg.platform, response)
    """
    
    def __init__(self):
        self.sources: Dict[str, SourceConfig] = {}
        self._load_sources()
    
    def _load_sources(self):
        """Load all YAML source configs"""
        if not SOURCES_DIR.exists():
            SOURCES_DIR.mkdir(parents=True, exist_ok=True)
            return
        
        for yaml_file in SOURCES_DIR.glob("*.yaml"):
            try:
                config = self._parse_source(yaml_file)
                if config.enabled:
                    self.sources[config.name] = config
                    print(f"✓ Loaded feed source: {config.name}")
            except Exception as e:
                print(f"⚠ Failed to load {yaml_file.name}: {e}")
    
    def _parse_source(self, path: Path) -> SourceConfig:
        """Parse a YAML source file"""
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return SourceConfig(
            name=data["name"],
            type=data.get("type", "rest"),
            auth=data.get("auth", {}),
            pull=data.get("pull", {}),
            push=data.get("push", {}),
            poll_interval=data.get("poll_interval", 300),
            enabled=data.get("enabled", True),
        )
    
    def _get_auth_headers(self, config: SourceConfig) -> Dict[str, str]:
        """Build auth headers based on config"""
        auth = config.auth
        method = auth.get("method", "none")
        
        if method == "bearer":
            token_env = auth.get("token_env")
            token = os.getenv(token_env, "")
            return {"Authorization": f"Bearer {token}"}
        
        elif method == "oauth2":
            token_path = Path(auth.get("token_path", "")).expanduser()
            if token_path.exists():
                with open(token_path) as f:
                    token_data = json.load(f)
                return {"Authorization": f"Bearer {token_data.get('access_token', '')}"}
        
        elif method == "api_key":
            key_env = auth.get("key_env")
            key_param = auth.get("key_param", "api_key")
            return {key_param: os.getenv(key_env, "")}
        
        return {}
    
    def _http_request(
        self, 
        url: str, 
        method: str = "GET",
        headers: Dict[str, str] = None,
        params: Dict[str, str] = None,
        body: Any = None
    ) -> Dict[str, Any]:
        """Make HTTP request and return JSON response"""
        headers = headers or {}
        headers["Content-Type"] = "application/json"
        
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        
        data = json.dumps(body).encode() if body else None
        
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except Exception as e:
            print(f"HTTP error: {e}")
            return {}
    
    def _extract_jsonpath(self, data: Any, path: str) -> Any:
        """Simple JSONPath extraction (supports $.field, $.array[*], $.array[0])"""
        if not path.startswith("$"):
            return data
        
        parts = path[2:].split(".") if path[1:].startswith(".") else path[1:].split(".")
        result = data
        
        for part in parts:
            if not part:
                continue
            
            # Handle array access
            array_match = re.match(r'(\w+)\[(\*|\d+)\]', part)
            if array_match:
                key, index = array_match.groups()
                result = result.get(key, []) if isinstance(result, dict) else result
                if index == "*":
                    result = result if isinstance(result, list) else []
                else:
                    result = result[int(index)] if isinstance(result, list) and len(result) > int(index) else None
            else:
                result = result.get(part) if isinstance(result, dict) else None
            
            if result is None:
                return None
        
        return result
    
    def _apply_mapping(self, raw: Dict, mapping: Dict[str, str], platform: str) -> List[NormalizedMessage]:
        """Apply mapping config to extract normalized messages"""
        messages = []
        
        # Get the array of messages
        messages_path = mapping.get("messages", "$")
        raw_messages = self._extract_jsonpath(raw, messages_path)
        
        if not isinstance(raw_messages, list):
            raw_messages = [raw_messages] if raw_messages else []
        
        for raw_msg in raw_messages:
            try:
                msg = NormalizedMessage(
                    platform=platform,
                    id=str(self._extract_jsonpath(raw_msg, mapping.get("id", "$.id")) or ""),
                    thread_id=str(self._extract_jsonpath(raw_msg, mapping.get("thread_id", "$.id")) or ""),
                    sender_id=str(self._extract_jsonpath(raw_msg, mapping.get("sender_id", "$.sender")) or ""),
                    sender_name=str(self._extract_jsonpath(raw_msg, mapping.get("sender_name", "$.sender")) or ""),
                    subject=self._extract_jsonpath(raw_msg, mapping.get("subject", "")) or None,
                    body=str(self._extract_jsonpath(raw_msg, mapping.get("body", "$.body")) or ""),
                    timestamp=datetime.now(),  # TODO: parse from mapping
                    raw=raw_msg,
                )
                messages.append(msg)
            except Exception as e:
                print(f"Failed to map message: {e}")
        
        return messages
    
    def _render_template(self, template: Dict, response: ResponseTemplate) -> Dict:
        """Render push body template with response data"""
        def replace_vars(obj):
            if isinstance(obj, str):
                # Replace {{var}} placeholders
                result = obj
                for key, value in response.to_dict().items():
                    result = result.replace(f"{{{{{key}}}}}", str(value or ""))
                
                # Special: base64 email for Gmail
                if "{{base64_email}}" in result:
                    email_raw = self._build_email_raw(response)
                    result = result.replace("{{base64_email}}", email_raw)
                
                return result
            elif isinstance(obj, dict):
                return {k: replace_vars(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_vars(item) for item in obj]
            return obj
        
        return replace_vars(template)
    
    def _build_email_raw(self, response: ResponseTemplate) -> str:
        """Build base64-encoded email for Gmail API"""
        msg = MIMEText(response.body or "")
        msg["to"] = response.to
        msg["subject"] = response.subject or ""
        
        if response.in_reply_to:
            msg["In-Reply-To"] = response.in_reply_to
            msg["References"] = response.in_reply_to
        
        return base64.urlsafe_b64encode(msg.as_bytes()).decode()
    
    # ==================== PUBLIC API ====================
    
    def list_sources(self) -> List[str]:
        """List all enabled source names"""
        return list(self.sources.keys())
    
    def pull(self, source_name: str) -> List[NormalizedMessage]:
        """Pull messages from a specific source"""
        if source_name not in self.sources:
            raise ValueError(f"Unknown source: {source_name}")
        
        config = self.sources[source_name]
        pull_config = config.pull
        
        headers = self._get_auth_headers(config)
        url = pull_config.get("endpoint", "")
        method = pull_config.get("method", "GET")
        params = pull_config.get("params", {})
        
        raw = self._http_request(url, method, headers, params)
        
        mapping = pull_config.get("mapping", {})
        return self._apply_mapping(raw, mapping, source_name)
    
    def pull_all(self) -> List[NormalizedMessage]:
        """Pull from all enabled sources"""
        all_messages = []
        for name in self.sources:
            try:
                messages = self.pull(name)
                all_messages.extend(messages)
            except Exception as e:
                print(f"Failed to pull from {name}: {e}")
        return all_messages
    
    def push(self, source_name: str, response: ResponseTemplate) -> bool:
        """Push response to source (as draft)"""
        if source_name not in self.sources:
            raise ValueError(f"Unknown source: {source_name}")
        
        config = self.sources[source_name]
        push_config = config.push
        
        headers = self._get_auth_headers(config)
        url = push_config.get("endpoint", "")
        method = push_config.get("method", "POST")
        
        body_template = push_config.get("body_template", {})
        body = self._render_template(body_template, response)
        
        result = self._http_request(url, method, headers, body=body)
        return bool(result)
    
    def add_source(self, name: str, config_dict: Dict) -> bool:
        """Add a new source from dict (saves to YAML)"""
        config_dict["name"] = name
        
        yaml_path = SOURCES_DIR / f"{name}.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(config_dict, f, default_flow_style=False)
        
        config = self._parse_source(yaml_path)
        self.sources[name] = config
        return True


# ==================== Convenience Functions ====================

_router: Optional[FeedsRouter] = None

def get_router() -> FeedsRouter:
    """Get singleton router instance"""
    global _router
    if _router is None:
        _router = FeedsRouter()
    return _router


def pull_all() -> List[NormalizedMessage]:
    """Pull from all sources"""
    return get_router().pull_all()


def push(platform: str, response: ResponseTemplate) -> bool:
    """Push response to platform"""
    return get_router().push(platform, response)
