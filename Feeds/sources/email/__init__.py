"""
Email Feed Module
=================

Multi-provider email integration supporting Gmail, Outlook, and Proton.
Each provider has its own OAuth flow but shares common event types.
"""

from typing import List, Dict, Any, Optional
from Feeds.events import EventTypeDefinition, register_event_types, emit_event, EventPriority

# ============================================================================
# Supported Providers
# ============================================================================

EMAIL_PROVIDERS = {
    "gmail": {
        "name": "Gmail",
        "icon": "📧",
        "oauth_provider": "google",
        "client_id_env": "GOOGLE_CLIENT_ID",
        "client_secret_env": "GOOGLE_CLIENT_SECRET",
        "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uri": "http://localhost:8000/api/feeds/email/oauth/callback?provider=gmail",
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.labels",
        ],
        "api_base": "https://gmail.googleapis.com/gmail/v1",
    },
    "outlook": {
        "name": "Outlook",
        "icon": "📬",
        "oauth_provider": "microsoft",
        "client_id_env": "MICROSOFT_CLIENT_ID",
        "client_secret_env": "MICROSOFT_CLIENT_SECRET",
        "auth_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "redirect_uri": "http://localhost:8000/api/feeds/email/oauth/callback?provider=outlook",
        "scopes": [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.Send",
            "offline_access",
        ],
        "api_base": "https://graph.microsoft.com/v1.0/me",
    },
    "proton": {
        "name": "Proton Mail",
        "icon": "🔒",
        "oauth_provider": "proton",
        "client_id_env": "PROTON_CLIENT_ID",
        "client_secret_env": "PROTON_CLIENT_SECRET",
        "auth_uri": "https://account.proton.me/authorize",
        "token_uri": "https://account.proton.me/api/auth/token",
        "redirect_uri": "http://localhost:8000/api/feeds/email/oauth/callback?provider=proton",
        "scopes": ["mail.read", "mail.send"],
        "api_base": "https://mail.proton.me/api",
        "coming_soon": True,  # Proton's OAuth is limited, mark as coming soon
    },
}


# ============================================================================
# Event Types (shared across all email providers)
# ============================================================================

EMAIL_EVENT_TYPES = [
    EventTypeDefinition(
        name="email_received",
        description="A new email was received",
        payload_schema={
            "provider": "str",
            "message_id": "str",
            "thread_id": "str",
            "from": "str",
            "to": "List[str]",
            "subject": "str",
            "snippet": "str",
            "date": "str",
            "labels": "List[str]",
        },
        example_payload={
            "provider": "gmail",
            "message_id": "abc123",
            "thread_id": "thread456",
            "from": "sender@example.com",
            "to": ["me@gmail.com"],
            "subject": "Meeting tomorrow",
            "snippet": "Hi, just wanted to confirm our meeting...",
            "date": "2026-02-01T10:30:00Z",
            "labels": ["INBOX", "UNREAD"],
        },
    ),
    EventTypeDefinition(
        name="email_sent",
        description="An email was sent",
        payload_schema={
            "provider": "str",
            "message_id": "str",
            "thread_id": "str",
            "to": "List[str]",
            "subject": "str",
        },
        example_payload={
            "provider": "gmail",
            "message_id": "def789",
            "thread_id": "thread456",
            "to": ["recipient@example.com"],
            "subject": "Re: Meeting tomorrow",
        },
    ),
    EventTypeDefinition(
        name="email_draft_created",
        description="A draft email was created (e.g., AI-generated reply)",
        payload_schema={
            "provider": "str",
            "draft_id": "str",
            "to": "List[str]",
            "subject": "str",
            "body_preview": "str",
        },
        example_payload={
            "provider": "gmail",
            "draft_id": "draft123",
            "to": ["recipient@example.com"],
            "subject": "Re: Question",
            "body_preview": "Thanks for reaching out...",
        },
    ),
    EventTypeDefinition(
        name="email_starred",
        description="An email was starred/flagged",
        payload_schema={
            "provider": "str",
            "message_id": "str",
            "subject": "str",
        },
        example_payload={
            "provider": "outlook",
            "message_id": "abc123",
            "subject": "Important document",
        },
    ),
]

# Register on import
register_event_types("email", EMAIL_EVENT_TYPES)


# ============================================================================
# OAuth Configuration (for module discovery)
# ============================================================================

EMAIL_OAUTH_CONFIG = {
    "providers": list(EMAIL_PROVIDERS.keys()),
    "multi_provider": True,
}


# ============================================================================
# OAuth Functions
# ============================================================================

def get_oauth_url(provider: str, state: Optional[str] = None) -> str:
    """Generate OAuth authorization URL for a specific provider."""
    import os
    from urllib.parse import urlencode
    
    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"Unknown email provider: {provider}")
    
    config = EMAIL_PROVIDERS[provider]
    
    if config.get("coming_soon"):
        raise ValueError(f"{config['name']} integration coming soon")
    
    client_id = os.environ.get(config["client_id_env"], "")
    if not client_id:
        raise ValueError(f"{config['client_id_env']} environment variable not set")
    
    params = {
        "client_id": client_id,
        "redirect_uri": config["redirect_uri"],
        "response_type": "code",
        "scope": " ".join(config["scopes"]),
    }
    
    # Provider-specific params
    if provider == "gmail":
        params["access_type"] = "offline"
        params["prompt"] = "consent"
    elif provider == "outlook":
        params["response_mode"] = "query"
    
    if state:
        params["state"] = state
    
    return f"{config['auth_uri']}?{urlencode(params)}"


async def exchange_code_for_tokens(provider: str, code: str) -> Dict[str, Any]:
    """Exchange authorization code for access/refresh tokens."""
    import os
    import httpx
    
    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"Unknown email provider: {provider}")
    
    config = EMAIL_PROVIDERS[provider]
    client_id = os.environ.get(config["client_id_env"], "")
    client_secret = os.environ.get(config["client_secret_env"], "")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config["token_uri"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": config["redirect_uri"],
                "grant_type": "authorization_code",
            },
        )
        response.raise_for_status()
        return response.json()


async def refresh_access_token(provider: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh the access token for a specific provider."""
    import os
    import httpx
    
    if provider not in EMAIL_PROVIDERS:
        raise ValueError(f"Unknown email provider: {provider}")
    
    config = EMAIL_PROVIDERS[provider]
    client_id = os.environ.get(config["client_id_env"], "")
    client_secret = os.environ.get(config["client_secret_env"], "")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config["token_uri"],
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        response.raise_for_status()
        return response.json()


# ============================================================================
# Email Adapter (unified interface for all providers)
# ============================================================================

class EmailAdapter:
    """Unified adapter for email operations across providers."""
    
    def __init__(self, provider: str):
        if provider not in EMAIL_PROVIDERS:
            raise ValueError(f"Unknown email provider: {provider}")
        self.provider = provider
        self.config = EMAIL_PROVIDERS[provider]
    
    async def get_access_token(self) -> Optional[str]:
        """Get valid access token, refreshing if needed."""
        from agent.core.secrets import get_oauth_tokens, store_oauth_tokens
        from datetime import datetime, timedelta
        
        # Store tokens per-provider: email_gmail, email_outlook, etc.
        feed_key = f"email_{self.provider}"
        tokens = get_oauth_tokens(feed_key)
        if not tokens:
            return None
        
        # Check if expired (with 5 min buffer)
        if tokens.get("expires_at"):
            expires_at = datetime.fromisoformat(tokens["expires_at"])
            if datetime.utcnow() > expires_at - timedelta(minutes=5):
                # Refresh
                if tokens.get("refresh_token"):
                    new_tokens = await refresh_access_token(self.provider, tokens["refresh_token"])
                    expires_at = (datetime.utcnow() + timedelta(seconds=new_tokens.get("expires_in", 3600))).isoformat()
                    store_oauth_tokens(
                        feed_key,
                        new_tokens["access_token"],
                        tokens.get("refresh_token"),
                        expires_at,
                        tokens.get("scopes"),
                    )
                    return new_tokens["access_token"]
                return None
        
        return tokens.get("access_token")
    
    async def list_messages(self, max_results: int = 20, query: Optional[str] = None) -> List[Dict[str, Any]]:
        """List messages from inbox."""
        import httpx
        
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError(f"Not authenticated with {self.config['name']}")
        
        if self.provider == "gmail":
            return await self._gmail_list_messages(access_token, max_results, query)
        elif self.provider == "outlook":
            return await self._outlook_list_messages(access_token, max_results, query)
        else:
            raise NotImplementedError(f"List messages not implemented for {self.provider}")
    
    async def _gmail_list_messages(self, token: str, max_results: int, query: Optional[str]) -> List[Dict[str, Any]]:
        import httpx
        params = {"maxResults": max_results}
        if query:
            params["q"] = query
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.config['api_base']}/users/me/messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            response.raise_for_status()
            return response.json().get("messages", [])
    
    async def _outlook_list_messages(self, token: str, max_results: int, query: Optional[str]) -> List[Dict[str, Any]]:
        import httpx
        params = {"$top": max_results, "$orderby": "receivedDateTime desc"}
        if query:
            params["$search"] = f'"{query}"'
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.config['api_base']}/messages",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )
            response.raise_for_status()
            return response.json().get("value", [])
    
    async def send_message(self, to: str, subject: str, body: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """Send an email."""
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError(f"Not authenticated with {self.config['name']}")
        
        if self.provider == "gmail":
            return await self._gmail_send(access_token, to, subject, body, thread_id)
        elif self.provider == "outlook":
            return await self._outlook_send(access_token, to, subject, body)
        else:
            raise NotImplementedError(f"Send not implemented for {self.provider}")
    
    async def _gmail_send(self, token: str, to: str, subject: str, body: str, thread_id: Optional[str]) -> Dict[str, Any]:
        import httpx
        import base64
        from email.mime.text import MIMEText
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        payload = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.config['api_base']}/users/me/messages/send",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            
            emit_event("email", "email_sent", {
                "provider": "gmail",
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "to": [to],
                "subject": subject,
            })
            
            return result
    
    async def _outlook_send(self, token: str, to: str, subject: str, body: str) -> Dict[str, Any]:
        import httpx
        
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.config['api_base']}/sendMail",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            
            emit_event("email", "email_sent", {
                "provider": "outlook",
                "message_id": "sent",
                "thread_id": None,
                "to": [to],
                "subject": subject,
            })
            
            return {"status": "sent"}


# Adapter factory
_adapters: Dict[str, EmailAdapter] = {}

def get_adapter(provider: str = "gmail") -> EmailAdapter:
    """Get or create an adapter for the specified provider."""
    if provider not in _adapters:
        _adapters[provider] = EmailAdapter(provider)
    return _adapters[provider]


def get_connected_providers() -> List[str]:
    """Get list of providers that have stored tokens."""
    from agent.core.secrets import get_oauth_tokens
    connected = []
    for provider in EMAIL_PROVIDERS:
        if get_oauth_tokens(f"email_{provider}"):
            connected.append(provider)
    return connected
