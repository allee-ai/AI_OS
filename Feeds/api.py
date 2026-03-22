"""
Feeds API - Manage external feed sources
============================================
CRUD for feed source configurations, secrets, OAuth flows, and events.
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from pathlib import Path
import yaml

import json

router = APIRouter(prefix="/api/feeds", tags=["feeds"])

# Paths relative to this module
FEEDS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = FEEDS_DIR / "sources"
_ENABLED_FILE = SOURCES_DIR / ".enabled.json"

# Whitelist: only directories under sources/ that contain __init__.py
_ALLOWED_MODULES = frozenset(
    d.name for d in SOURCES_DIR.iterdir()
    if d.is_dir() and (d / "__init__.py").exists()
)


def _load_enabled() -> Dict[str, bool]:
    """Load per-source enabled flags from disk."""
    if _ENABLED_FILE.exists():
        try:
            return json.loads(_ENABLED_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_enabled(state: Dict[str, bool]) -> None:
    """Persist per-source enabled flags."""
    _ENABLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    _ENABLED_FILE.write_text(json.dumps(state, indent=2))


class FeedSourceConfig(BaseModel):
    """Feeds source configuration"""
    name: str
    type: str = "rest"
    enabled: bool = False
    poll_interval: int = 300
    auth: Dict[str, Any] = {}
    pull: Dict[str, Any] = {}
    push: Dict[str, Any] = {}
    description: Optional[str] = None


class FeedSourceSummary(BaseModel):
    """Summary for list view"""
    name: str
    type: str
    enabled: bool
    poll_interval: int
    has_auth: bool
    description: Optional[str] = None


def _get_module_info(module_dir: Path) -> Optional[Dict[str, Any]]:
    """Extract info from a feed module directory."""
    init_file = module_dir / "__init__.py"
    if not init_file.exists():
        return None
    
    name = module_dir.name
    enabled_map = _load_enabled()
    info = {
        "name": name,
        "type": "module",
        "enabled": enabled_map.get(name, False),
        "poll_interval": 300,
        "has_auth": False,
        "description": None,
    }
    
    # Try to import the module to get its info
    if name not in _ALLOWED_MODULES:
        return info
    try:
        import importlib
        module = importlib.import_module(f"Feeds.sources.{name}")
        
        # Check for event types
        if hasattr(module, f"{name.upper()}_EVENT_TYPES"):
            event_types = getattr(module, f"{name.upper()}_EVENT_TYPES")
            info["event_count"] = len(event_types)
        
        # Check for OAuth config
        if hasattr(module, f"{name.upper()}_OAUTH_CONFIG"):
            info["has_auth"] = True
            info["auth_method"] = "oauth2"
        
        # Get description from docstring
        if module.__doc__:
            info["description"] = module.__doc__.strip().split("\n")[0]
        
    except Exception as e:
        print(f"Failed to inspect module {name}: {e}")
    
    return info


@router.get("/sources", response_model=List[FeedSourceSummary])
async def list_sources():
    """List all configured feed modules (directories in sources/)"""
    sources = []
    
    if not SOURCES_DIR.exists():
        SOURCES_DIR.mkdir(parents=True, exist_ok=True)
        return sources
    
    # Scan for directories (feed modules)
    for item in SOURCES_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_") and not item.name.startswith("."):
            info = _get_module_info(item)
            if info:
                sources.append(FeedSourceSummary(
                    name=info["name"],
                    type=info["type"],
                    enabled=info["enabled"],
                    poll_interval=info["poll_interval"],
                    has_auth=info["has_auth"],
                    description=info.get("description"),
                ))
    
    return sources


@router.get("/sources/{name}")
async def get_source(name: str):
    """Get full config for a feed module"""
    module_dir = SOURCES_DIR / name
    
    if not module_dir.exists() or not module_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Feed module '{name}' not found")
    
    info = _get_module_info(module_dir)
    if not info:
        raise HTTPException(status_code=404, detail=f"Invalid feed module '{name}'")
    
    # Get event types from the events registry
    from .events import get_event_types
    event_types = get_event_types(name)
    
    return {
        **info,
        "event_types": event_types.get(name, []),
        "auth": {"method": info.get("auth_method")} if info["has_auth"] else {},
        "pull": {},
        "push": {},
    }


@router.post("/sources/{name}/toggle")
async def toggle_source(name: str):
    """Toggle enabled state for a feed module."""
    module_dir = SOURCES_DIR / name

    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Feed module '{name}' not found")

    state = _load_enabled()
    current = state.get(name, False)
    state[name] = not current
    _save_enabled(state)

    return {"name": name, "enabled": state[name]}


@router.post("/sources/{name}/test")
async def test_source(name: str):
    """Test connection to a feed module"""
    module_dir = SOURCES_DIR / name
    
    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Feed module '{name}' not found")
    if name not in _ALLOWED_MODULES:
        raise HTTPException(status_code=403, detail=f"Module '{name}' is not whitelisted")
    
    # Check if module is properly configured
    try:
        import importlib
        module = importlib.import_module(f"Feeds.sources.{name}")
        return {
            "status": "ok",
            "message": f"Module {name} loaded successfully"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/templates")
async def list_templates():
    """List available feed module templates for adding new integrations"""
    # These are the feeds we support but haven't been added yet
    available = [
        {"name": "slack", "description": "Slack - DMs and channel mentions", "icon": "💬"},
        {"name": "sms", "description": "SMS via Twilio", "icon": "📱"},
        {"name": "telegram", "description": "Telegram - Bot messages", "icon": "✈️"},
        {"name": "github", "description": "GitHub - Notifications, issues, PRs", "icon": "🐙"},
        {"name": "linear", "description": "Linear - Issue tracking", "icon": "📐"},
        {"name": "notion", "description": "Notion - Database items", "icon": "📓"},
        {"name": "twitter", "description": "Twitter/X - Mentions and DMs", "icon": "🐦"},
        {"name": "whatsapp", "description": "WhatsApp Business API", "icon": "💚"},
        {"name": "teams", "description": "Microsoft Teams - Chat messages", "icon": "👥"},
        {"name": "gcal", "description": "Google Calendar - Events", "icon": "📅"},
        {"name": "webhook", "description": "Generic webhook endpoint", "icon": "🔗"},
    ]
    
    # Check which ones already exist as modules
    existing = set()
    if SOURCES_DIR.exists():
        for item in SOURCES_DIR.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                existing.add(item.name)
    
    return [
        {**t, "exists": t["name"] in existing}
        for t in available
    ]


# ============================================================================
# Secrets Management
# ============================================================================

class SecretCreate(BaseModel):
    key: str
    value: str
    secret_type: str = "api_key"
    metadata: Optional[Dict[str, Any]] = None


@router.get("/secrets")
async def list_secrets(feed_name: Optional[str] = None):
    """List secrets (metadata only, not values) for a feed or all feeds."""
    from agent.core.secrets import list_secrets as _list_secrets
    return _list_secrets(feed_name)


@router.get("/secrets/{feed_name}")
async def get_feed_secrets(feed_name: str):
    """Get secret keys for a specific feed (no values exposed)."""
    from agent.core.secrets import list_secrets
    return list_secrets(feed_name)


@router.post("/secrets/{feed_name}")
async def store_feed_secret(feed_name: str, secret: SecretCreate):
    """Store a secret for a feed."""
    from agent.core.secrets import store_secret
    
    secret_id = store_secret(
        key=secret.key,
        value=secret.value,
        feed_name=feed_name,
        secret_type=secret.secret_type,
        metadata=secret.metadata,
    )
    return {"status": "stored", "secret_id": secret_id}


@router.delete("/secrets/{feed_name}/{key}")
async def delete_feed_secret(feed_name: str, key: str):
    """Delete a specific secret."""
    from agent.core.secrets import delete_secret
    
    if delete_secret(key, feed_name):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Secret not found")


@router.delete("/secrets/{feed_name}")
async def delete_all_feed_secrets(feed_name: str):
    """Delete all secrets for a feed (disconnect)."""
    from agent.core.secrets import delete_secrets_for_feed
    
    count = delete_secrets_for_feed(feed_name)
    return {"status": "deleted", "count": count}


# ============================================================================
# OAuth Flows
# ============================================================================

@router.get("/{feed_name}/oauth/start")
async def start_oauth(feed_name: str, provider: Optional[str] = None, redirect_uri: Optional[str] = None):
    """
    Start OAuth flow for a feed.
    Returns the OAuth authorization URL to redirect the user to.
    For multi-provider feeds (like email), pass provider query param.
    """
    import uuid
    
    state = str(uuid.uuid4())
    
    # Email (multi-provider: gmail, outlook, proton)
    if feed_name == "email":
        from .sources.email import get_oauth_url
        if not provider:
            provider = "gmail"  # Default provider
        try:
            url = get_oauth_url(provider, state)
            return {"auth_url": url, "state": state, "provider": provider}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # GitHub - uses Device Flow now, redirect to device flow endpoint
    if feed_name == "github":
        raise HTTPException(
            status_code=400, 
            detail="GitHub uses Device Flow. Use POST /api/feeds/github/device/start instead"
        )
    
    # Discord
    if feed_name == "discord":
        # Discord uses bot token, not OAuth for our use case
        raise HTTPException(status_code=400, detail="Discord uses bot token authentication. Add your bot token in settings.")
    
    raise HTTPException(status_code=400, detail=f"OAuth not supported for {feed_name}")


# ============================================================================
# GitHub Device Flow Endpoints
# ============================================================================

@router.post("/github/device/start")
async def github_device_start():
    """
    Start GitHub Device Flow login.
    
    Returns user_code to display and device_code to poll with.
    User visits github.com/login/device and enters the code.
    """
    from .sources.github import start_device_flow
    
    try:
        result = await start_device_flow()
        return {
            "user_code": result["user_code"],
            "verification_uri": result["verification_uri"],
            "device_code": result["device_code"],
            "expires_in": result.get("expires_in", 900),
            "interval": result.get("interval", 5),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"Failed to start device flow: {e}")
        raise HTTPException(status_code=500, detail="Failed to start device flow")


@router.post("/github/device/poll")
async def github_device_poll(device_code: str):
    """
    Poll for GitHub access token.
    
    Call this every `interval` seconds until you get a token or error.
    """
    from .sources.github import poll_for_token
    from agent.core.secrets import store_oauth_tokens
    
    try:
        result = await poll_for_token(device_code)
        
        # Check for errors
        if "error" in result:
            error = result["error"]
            if error == "authorization_pending":
                return {"status": "pending", "message": "Waiting for user to authorize..."}
            elif error == "slow_down":
                return {"status": "slow_down", "interval": result.get("interval", 10)}
            elif error == "expired_token":
                raise HTTPException(status_code=400, detail="Device code expired. Please start over.")
            elif error == "access_denied":
                raise HTTPException(status_code=400, detail="User denied access.")
            else:
                raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        # Success - got access token
        if "access_token" in result:
            # Store the token
            store_oauth_tokens("github", {
                "access_token": result["access_token"],
                "token_type": result.get("token_type", "bearer"),
                "scope": result.get("scope", ""),
            })
            return {"status": "success", "message": "GitHub connected!"}
        
        return {"status": "unknown", "result": result}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Poll failed: {e}")
        raise HTTPException(status_code=500, detail="Poll failed")


@router.get("/{feed_name}/oauth/callback")
async def oauth_callback(feed_name: str, code: str, state: Optional[str] = None, provider: Optional[str] = None):
    """
    Handle OAuth callback - exchange code for tokens.
    """
    from datetime import datetime, timedelta
    from agent.core.secrets import store_oauth_tokens
    
    try:
        # Email (multi-provider)
        if feed_name == "email":
            from .sources.email import exchange_code_for_tokens
            if not provider:
                provider = "gmail"
            
            tokens = await exchange_code_for_tokens(provider, code)
            expires_in = tokens.get("expires_in", 3600)
            expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()
            
            # Store tokens with provider-specific key
            store_oauth_tokens(
                f"email_{provider}",
                tokens["access_token"],
                tokens.get("refresh_token"),
                expires_at,
                tokens.get("scope", "").split(" ") if tokens.get("scope") else None,
            )
            
            return RedirectResponse(url=f"/feeds?connected=email&provider={provider}")
        
        # GitHub
        if feed_name == "github":
            from .sources.github import exchange_code_for_tokens
            
            tokens = await exchange_code_for_tokens(code)
            
            # GitHub tokens don't expire unless revoked
            store_oauth_tokens(
                "github",
                tokens["access_token"],
                None,  # GitHub doesn't use refresh tokens
                None,  # No expiry
                tokens.get("scope", "").split(",") if tokens.get("scope") else None,
            )
            
            return RedirectResponse(url="/feeds?connected=github")
        
        raise HTTPException(status_code=400, detail=f"OAuth not supported for {feed_name}")
        
    except Exception as e:
        print(f"OAuth exchange failed: {e}")
        raise HTTPException(status_code=400, detail="OAuth exchange failed")


@router.get("/{feed_name}/status")
async def feed_status(feed_name: str):
    """Check if a feed is connected (has valid tokens/credentials)."""
    from agent.core.secrets import get_oauth_tokens
    
    # Email - check all providers
    if feed_name == "email":
        status = {}
        for provider in ["gmail", "outlook", "proton"]:
            tokens = get_oauth_tokens(f"email_{provider}")
            status[provider] = {
                "connected": bool(tokens and tokens.get("access_token")),
            }
        return status
    
    # GitHub
    if feed_name == "github":
        tokens = get_oauth_tokens("github")
        if tokens and tokens.get("access_token"):
            # Try to get username
            try:
                from .sources.github import get_adapter
                adapter = get_adapter()
                user = await adapter.get_user()
                return {"connected": True, "username": user.get("login")}
            except:
                return {"connected": True, "username": None}
        return {"connected": False}
    
    # Discord
    if feed_name == "discord":
        from agent.core.secrets import get_secret
        token = get_secret("bot_token", "discord")
        return {"connected": bool(token)}
    
    # Generic check
    tokens = get_oauth_tokens(feed_name)
    if tokens and tokens.get("access_token"):
        return {"connected": True}
    return {"connected": False}


@router.get("/email/providers/status")
async def email_providers_status():
    """Get connection status for all email providers."""
    from agent.core.secrets import get_oauth_tokens, get_secret
    
    status = {}
    for provider in ["gmail", "outlook"]:
        tokens = get_oauth_tokens(f"email_{provider}")
        status[provider] = {
            "connected": bool(tokens and tokens.get("access_token")),
        }
    # Proton uses IMAP Bridge credentials, not OAuth tokens
    proton_user = get_secret("imap_user", "email_proton")
    proton_pass = get_secret("imap_password", "email_proton")
    status["proton"] = {
        "connected": bool(proton_user and proton_pass),
    }
    return status


@router.post("/{feed_name}/disconnect")
async def disconnect_feed(feed_name: str, provider: Optional[str] = None):
    """Disconnect a feed by removing all its secrets."""
    from agent.core.secrets import delete_secrets_for_feed
    
    # For multi-provider feeds
    key = f"{feed_name}_{provider}" if provider else feed_name
    count = delete_secrets_for_feed(key)
    
    # Log the disconnection
    try:
        from agent.threads.log.schema import log_event
        log_event(
            event_type="feed",
            data=f"Disconnected from {key}",
            metadata={"feed_name": feed_name, "provider": provider},
            source=f"feed.{feed_name}",
        )
    except ImportError:
        pass
    
    return {"status": "disconnected", "secrets_removed": count}


# ============================================================================
# Events & Triggers
# ============================================================================

@router.get("/events/types")
async def list_event_types(feed_name: Optional[str] = None):
    """Get all registered event types, optionally filtered by feed."""
    from .events import get_event_types
    return get_event_types(feed_name)


@router.get("/events/triggers")
async def list_triggers():
    """Get all available triggers for Reflex integration."""
    from .events import get_all_triggers
    return get_all_triggers()


@router.get("/events/recent")
async def get_recent_events(
    feed_name: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
):
    """Get recent feed events from the log."""
    from .events import get_recent_events
    return get_recent_events(feed_name, event_type, limit)


@router.post("/{feed_name}/webhook")
async def receive_webhook(feed_name: str, payload: Dict[str, Any]):
    """
    Receive a webhook event from an external service.
    The event will be logged and can trigger reflexes.
    """
    from .events import emit_event, EventPriority
    
    # Determine event type from payload (feed-specific logic)
    event_type = payload.get("event_type", payload.get("type", "webhook_received"))
    
    event = emit_event(
        feed_name=feed_name,
        event_type=event_type,
        payload=payload,
        priority=EventPriority.NORMAL,
    )
    
    return {"status": "received", "event": event.to_dict()}


# ============================================================================
# Polling & Bridge
# ============================================================================

@router.get("/polling/status")
async def polling_status():
    """Get the status of the background feed polling loop."""
    from .polling import get_polling_status
    return get_polling_status()


@router.post("/polling/start")
async def polling_start(interval: int = Query(300, ge=30, le=3600)):
    """Start the feed polling loop."""
    from .polling import start_polling
    start_polling(interval_seconds=interval)
    return {"status": "started", "interval": interval}


@router.post("/polling/stop")
async def polling_stop():
    """Stop the feed polling loop."""
    from .polling import stop_polling
    stop_polling()
    return {"status": "stopped"}


@router.get("/bridge/status")
async def bridge_status():
    """Get bridge configuration and recent responses."""
    from .bridge import get_bridge_status
    return get_bridge_status()


@router.get("/bridge/responses")
async def bridge_responses(limit: int = Query(20, ge=1, le=100)):
    """Get recent bridge response log."""
    from .bridge import get_response_log
    return get_response_log(limit)


# ============================================================================
# Integrations Hub — unified status for connecting feeds in Settings
# ============================================================================

class IntegrationConfig(BaseModel):
    """Configuration update for an integration."""
    key: str              # e.g. "bot_token", "client_id"
    value: str
    secret: bool = True   # store encrypted?


@router.get("/integrations")
async def list_integrations():
    """
    Unified integration status for the Settings UI.
    Returns all supported feeds with connection status, config requirements,
    and suggested reflex protocols.
    """
    from agent.core.secrets import get_oauth_tokens, get_secret

    integrations = []

    # ── Email ──────────────────────────────────────────────────
    email_providers = {}
    for provider in ["gmail", "outlook"]:
        tokens = get_oauth_tokens(f"email_{provider}")
        email_providers[provider] = {
            "connected": bool(tokens and tokens.get("access_token")),
            "label": provider.title(),
            "auth_method": "oauth2",
        }
    integrations.append({
        "id": "email",
        "name": "Email",
        "icon": "📧",
        "description": "Gmail and Outlook integration — inbox, send, drafts",
        "category": "communication",
        "providers": email_providers,
        "connected": any(p["connected"] for p in email_providers.values()),
        "auth_method": "oauth2",
        "config_fields": [
            {"key": "GOOGLE_CLIENT_ID", "label": "Google Client ID", "type": "env", "secret": False},
            {"key": "GOOGLE_CLIENT_SECRET", "label": "Google Client Secret", "type": "env", "secret": True},
        ],
        "suggested_protocols": ["email_triage", "morning_briefing"],
        "docs_url": "https://console.cloud.google.com/apis/credentials",
    })

    # ── GitHub ─────────────────────────────────────────────────
    gh_tokens = get_oauth_tokens("github")
    gh_connected = bool(gh_tokens and gh_tokens.get("access_token"))
    gh_username = None
    if gh_connected:
        try:
            from .sources.github import get_adapter
            adapter = get_adapter()
            import asyncio
            user = asyncio.get_event_loop().run_until_complete(adapter.get_user())
            gh_username = user.get("login")
        except Exception:
            pass
    integrations.append({
        "id": "github",
        "name": "GitHub",
        "icon": "🐙",
        "description": "Notifications, issues, PRs, code review alerts",
        "category": "development",
        "connected": gh_connected,
        "username": gh_username,
        "auth_method": "device_flow",
        "config_fields": [
            {"key": "GITHUB_CLIENT_ID", "label": "GitHub OAuth App Client ID", "type": "env", "secret": False},
        ],
        "suggested_protocols": ["github_review"],
        "docs_url": "https://github.com/settings/developers",
    })

    # ── Discord ────────────────────────────────────────────────
    discord_token = get_secret("bot_token", "discord")
    integrations.append({
        "id": "discord",
        "name": "Discord",
        "icon": "🎮",
        "description": "Bot messages, DMs, server monitoring",
        "category": "communication",
        "connected": bool(discord_token),
        "auth_method": "bot_token",
        "config_fields": [
            {"key": "bot_token", "label": "Discord Bot Token", "type": "secret", "secret": True},
        ],
        "suggested_protocols": [],
        "docs_url": "https://discord.com/developers/applications",
    })

    # ── Polling status ─────────────────────────────────────────
    from .polling import get_polling_status
    polling = get_polling_status()

    return {
        "integrations": integrations,
        "polling": polling,
    }


@router.post("/integrations/{feed_name}/connect")
async def connect_integration(feed_name: str, config: Optional[IntegrationConfig] = None):
    """
    Start connection flow for an integration.
    - email: redirects to OAuth (returns auth_url)
    - github: starts device flow (returns user_code)
    - discord: stores bot token directly
    """
    if feed_name == "email":
        provider = "gmail"
        if config and config.key == "provider":
            provider = config.value
        from .sources.email import get_oauth_url
        import uuid
        state = str(uuid.uuid4())
        try:
            url = get_oauth_url(provider, state)
            return {"action": "redirect", "auth_url": url, "state": state, "provider": provider}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if feed_name == "github":
        from .sources.github import start_device_flow
        try:
            result = await start_device_flow()
            return {
                "action": "device_flow",
                "user_code": result["user_code"],
                "verification_uri": result["verification_uri"],
                "device_code": result["device_code"],
                "expires_in": result.get("expires_in", 900),
                "interval": result.get("interval", 5),
            }
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    if feed_name == "discord":
        if not config or config.key != "bot_token" or not config.value:
            raise HTTPException(status_code=400, detail="Provide bot_token")
        from agent.core.secrets import store_secret
        store_secret("bot_token", config.value, feed_name="discord", secret_type="bot_token")
        return {"action": "stored", "connected": True}

    raise HTTPException(status_code=404, detail=f"Unknown integration: {feed_name}")


@router.post("/integrations/{feed_name}/disconnect")
async def disconnect_integration(feed_name: str, provider: Optional[str] = None):
    """Disconnect an integration (remove all tokens/secrets)."""
    from agent.core.secrets import delete_secrets_for_feed

    if feed_name == "email" and provider:
        count = delete_secrets_for_feed(f"email_{provider}")
    elif feed_name == "email":
        count = sum(delete_secrets_for_feed(f"email_{p}") for p in ["gmail", "outlook", "proton"])
    else:
        count = delete_secrets_for_feed(feed_name)

    return {"status": "disconnected", "secrets_removed": count}


@router.post("/integrations/{feed_name}/configure")
async def configure_integration(feed_name: str, body: Dict[str, Any]):
    """
    Update integration settings — polling interval, enabled state, env hints.
    """
    from .polling import get_polling_status

    # Toggle enabled
    if "enabled" in body:
        state = _load_enabled()
        state[feed_name] = bool(body["enabled"])
        _save_enabled(state)

    # Update polling interval goes through polling module
    if "poll_interval" in body:
        # Stored alongside feed state (future: per-feed intervals)
        pass

    return {"status": "ok", "polling": get_polling_status()}


# ─────────────────────────────────────────────────────────────
# Email — message endpoints
# ─────────────────────────────────────────────────────────────

class SendEmailBody(BaseModel):
    to: str
    subject: str
    body: str
    thread_id: Optional[str] = None


@router.get("/email/{provider}/messages")
async def email_messages(provider: str, max_results: int = Query(20, ge=1, le=100), q: Optional[str] = None):
    """Fetch inbox messages for a provider."""
    from .sources.email import get_adapter, EMAIL_PROVIDERS
    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    adapter = get_adapter(provider)
    try:
        return await adapter.list_messages(max_results=max_results, query=q)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"Email fetch error ({provider}): {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@router.get("/email/{provider}/drafts")
async def email_drafts(provider: str):
    """Get AI-generated draft responses for a provider."""
    from .bridge import get_response_log
    log = get_response_log(limit=50)
    # Filter to this provider
    drafts = [
        {
            "id": str(i),
            "to": entry.get("to", ""),
            "subject": entry.get("subject", ""),
            "body": entry.get("body", ""),
            "created": entry.get("timestamp", ""),
        }
        for i, entry in enumerate(log)
        if entry.get("provider") == provider or entry.get("feed_name") == f"email_{provider}"
    ]
    return drafts


@router.post("/email/{provider}/send")
async def email_send(provider: str, body: SendEmailBody):
    """Send an email through a connected provider."""
    from .sources.email import get_adapter, EMAIL_PROVIDERS
    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    adapter = get_adapter(provider)
    try:
        result = await adapter.send_message(
            to=body.to, subject=body.subject, body=body.body, thread_id=body.thread_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        print(f"Email send error ({provider}): {e}")
        raise HTTPException(status_code=500, detail="Failed to send email")


@router.post("/email/proton/connect")
async def connect_proton_bridge(body: Dict[str, Any]):
    """Store Proton Bridge IMAP/SMTP credentials."""
    from agent.core.secrets import store_secret

    required = ["imap_user", "imap_password"]
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"Missing: {field}")

    store_secret("imap_user", body["imap_user"], feed_name="email_proton", secret_type="credential")
    store_secret("imap_password", body["imap_password"], feed_name="email_proton", secret_type="credential")
    store_secret("imap_host", body.get("imap_host", "127.0.0.1"), feed_name="email_proton", secret_type="config")
    store_secret("imap_port", str(body.get("imap_port", 1143)), feed_name="email_proton", secret_type="config")
    store_secret("smtp_port", str(body.get("smtp_port", 1025)), feed_name="email_proton", secret_type="config")

    return {"status": "connected", "provider": "proton"}


# ─────────────────────────────────────────────────────────────
# Intelligence — LLM-powered email capabilities
# ─────────────────────────────────────────────────────────────


class ThreadSummarizeBody(BaseModel):
    messages: List[Dict[str, Any]]

    @property
    def capped(self) -> List[Dict[str, Any]]:
        """Return at most 25 messages to avoid context-window abuse."""
        return self.messages[:25]


class SmartReplyBody(BaseModel):
    message: Dict[str, Any]


@router.post("/email/{provider}/summarize")
async def email_summarize_thread(provider: str, body: ThreadSummarizeBody):
    """Summarize an email thread using the configured LLM."""
    from .sources.email import EMAIL_PROVIDERS
    from .intelligence import summarize_thread

    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    summary = summarize_thread(body.capped)
    if summary is None:
        raise HTTPException(status_code=502, detail="LLM unavailable")
    return {"summary": summary}


@router.post("/email/{provider}/action-items")
async def email_action_items(provider: str, body: ThreadSummarizeBody):
    """Extract action items from an email thread."""
    from .sources.email import EMAIL_PROVIDERS
    from .intelligence import extract_action_items

    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    items = extract_action_items(body.capped)
    return {"action_items": items}


@router.post("/email/{provider}/smart-replies")
async def email_smart_replies(provider: str, body: SmartReplyBody):
    """Generate 3 short reply suggestions for an email."""
    from .sources.email import EMAIL_PROVIDERS
    from .intelligence import smart_replies

    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    replies = smart_replies(body.message)
    return {"replies": replies}


@router.post("/email/{provider}/triage")
async def email_triage(provider: str, max_results: int = Query(20, ge=1, le=50)):
    """Fetch inbox then classify each message by priority and category."""
    from .sources.email import get_adapter, EMAIL_PROVIDERS
    from .intelligence import triage_emails

    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    adapter = get_adapter(provider)
    try:
        messages = await adapter.list_messages(max_results=max_results, query="is:unread")
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch messages")
    triaged = triage_emails(messages)
    return {"results": triaged}


@router.post("/email/{provider}/digest")
async def email_digest(provider: str, max_results: int = Query(30, ge=1, le=50)):
    """Generate a morning-briefing digest of recent emails."""
    from .sources.email import get_adapter, EMAIL_PROVIDERS
    from .intelligence import daily_digest

    if provider not in EMAIL_PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {provider}")
    adapter = get_adapter(provider)
    try:
        messages = await adapter.list_messages(max_results=max_results)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to fetch messages")
    digest = daily_digest(messages)
    if digest is None:
        raise HTTPException(status_code=502, detail="LLM unavailable")
    return {"digest": digest}


# ─────────────────────────────────────────────────────────────
# Calendar
# ─────────────────────────────────────────────────────────────

@router.get("/calendar/sources")
async def list_calendars():
    """List registered calendar sources."""
    from .sources.calendar import get_calendars
    return get_calendars()


class CalendarCreateBody(BaseModel):
    name: str
    ical_url: str
    lookahead_minutes: int = 30
    poll_interval: int = 300


@router.post("/calendar/sources")
async def create_calendar(body: CalendarCreateBody):
    """Register a new calendar source via iCal URL."""
    from .sources.calendar import add_calendar
    return add_calendar(
        name=body.name,
        ical_url=body.ical_url,
        lookahead_minutes=body.lookahead_minutes,
        poll_interval=body.poll_interval,
    )


@router.delete("/calendar/sources/{name}")
async def delete_calendar(name: str):
    """Remove a calendar source."""
    from .sources.calendar import remove_calendar
    ok = remove_calendar(name)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Calendar '{name}' not found")
    return {"status": "deleted", "name": name}


@router.post("/calendar/poll")
async def poll_calendars_now():
    """Trigger an immediate poll of all enabled calendars."""
    from .sources.calendar import poll_calendars
    count = poll_calendars()
    return {"status": "polled", "events_emitted": count}
