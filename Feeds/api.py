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

router = APIRouter(prefix="/api/feeds", tags=["feeds"])

# Paths relative to this module
FEEDS_DIR = Path(__file__).resolve().parent
SOURCES_DIR = FEEDS_DIR / "sources"


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
    info = {
        "name": name,
        "type": "module",
        "enabled": False,  # Check if connected
        "poll_interval": 300,
        "has_auth": False,
        "description": None,
    }
    
    # Try to import the module to get its info
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
    """Toggle enabled state for a feed module"""
    module_dir = SOURCES_DIR / name
    
    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Feed module '{name}' not found")
    
    # TODO: Implement actual enable/disable logic
    return {"name": name, "enabled": True}


@router.post("/sources/{name}/test")
async def test_source(name: str):
    """Test connection to a feed module"""
    module_dir = SOURCES_DIR / name
    
    if not module_dir.exists():
        raise HTTPException(status_code=404, detail=f"Feed module '{name}' not found")
    
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
        raise HTTPException(status_code=500, detail=f"Failed to start device flow: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"Poll failed: {str(e)}")


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
        raise HTTPException(status_code=400, detail=f"OAuth exchange failed: {e}")


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
    from agent.core.secrets import get_oauth_tokens
    
    status = {}
    for provider in ["gmail", "outlook", "proton"]:
        tokens = get_oauth_tokens(f"email_{provider}")
        status[provider] = {
            "connected": bool(tokens and tokens.get("access_token")),
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
