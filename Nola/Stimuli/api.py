"""
Stimuli API - Manage external stimuli sources
============================================
CRUD for stimuli source configurations.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from pathlib import Path
import yaml

router = APIRouter(prefix="/api/stimuli", tags=["stimuli"])

# Paths relative to this module
STIMULI_DIR = Path(__file__).resolve().parent
SOURCES_DIR = STIMULI_DIR / "sources"


class StimuliSourceConfig(BaseModel):
    """Stimuli source configuration"""
    name: str
    type: str = "rest"
    enabled: bool = False
    poll_interval: int = 300
    auth: Dict[str, Any] = {}
    pull: Dict[str, Any] = {}
    push: Dict[str, Any] = {}
    description: Optional[str] = None


class StimuliSourceSummary(BaseModel):
    """Summary for list view"""
    name: str
    type: str
    enabled: bool
    poll_interval: int
    has_auth: bool
    description: Optional[str] = None


@router.get("/sources", response_model=List[StimuliSourceSummary])
async def list_sources():
    """List all configured stimuli sources"""
    sources = []
    
    if not SOURCES_DIR.exists():
        SOURCES_DIR.mkdir(parents=True, exist_ok=True)
        return sources
    
    for yaml_file in SOURCES_DIR.glob("*.yaml"):
        if yaml_file.name.startswith("_"):
            continue  # Skip templates
        
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            
            sources.append(StimuliSourceSummary(
                name=data.get("name", yaml_file.stem),
                type=data.get("type", "rest"),
                enabled=data.get("enabled", False),
                poll_interval=data.get("poll_interval", 300),
                has_auth=bool(data.get("auth", {}).get("method")),
                description=data.get("description"),
            ))
        except Exception as e:
            print(f"Failed to parse {yaml_file}: {e}")
    
    return sources


@router.get("/sources/{name}", response_model=StimuliSourceConfig)
async def get_source(name: str):
    """Get full config for a source"""
    yaml_path = SOURCES_DIR / f"{name}.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    return StimuliSourceConfig(
        name=data.get("name", name),
        type=data.get("type", "rest"),
        enabled=data.get("enabled", False),
        poll_interval=data.get("poll_interval", 300),
        auth=data.get("auth", {}),
        pull=data.get("pull", {}),
        push=data.get("push", {}),
        description=data.get("description"),
    )


@router.post("/sources", response_model=StimuliSourceConfig)
async def create_source(config: StimuliSourceConfig):
    """Create a new stimuli source"""
    yaml_path = SOURCES_DIR / f"{config.name}.yaml"
    
    if yaml_path.exists():
        raise HTTPException(status_code=400, detail=f"Source '{config.name}' already exists")
    
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    
    data = {
        "name": config.name,
        "type": config.type,
        "enabled": config.enabled,
        "poll_interval": config.poll_interval,
        "description": config.description,
        "auth": config.auth,
        "pull": config.pull,
        "push": config.push,
    }
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    return config


@router.put("/sources/{name}", response_model=StimuliSourceConfig)
async def update_source(name: str, config: StimuliSourceConfig):
    """Update an existing source"""
    yaml_path = SOURCES_DIR / f"{name}.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    
    data = {
        "name": config.name,
        "type": config.type,
        "enabled": config.enabled,
        "poll_interval": config.poll_interval,
        "description": config.description,
        "auth": config.auth,
        "pull": config.pull,
        "push": config.push,
    }
    
    # If name changed, rename file
    if config.name != name:
        new_path = SOURCES_DIR / f"{config.name}.yaml"
        if new_path.exists():
            raise HTTPException(status_code=400, detail=f"Source '{config.name}' already exists")
        yaml_path.unlink()
        yaml_path = new_path
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    return config


@router.delete("/sources/{name}")
async def delete_source(name: str):
    """Delete a stimuli source"""
    yaml_path = SOURCES_DIR / f"{name}.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    
    yaml_path.unlink()
    return {"status": "deleted", "name": name}


@router.post("/sources/{name}/toggle")
async def toggle_source(name: str):
    """Toggle enabled state for a source"""
    yaml_path = SOURCES_DIR / f"{name}.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    
    data["enabled"] = not data.get("enabled", False)
    
    with open(yaml_path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    return {"name": name, "enabled": data["enabled"]}


@router.post("/sources/{name}/test")
async def test_source(name: str):
    """Test connection to a stimuli source"""
    yaml_path = SOURCES_DIR / f"{name}.yaml"
    
    if not yaml_path.exists():
        raise HTTPException(status_code=404, detail=f"Source '{name}' not found")
    
    try:
        from .router import StimuliRouter
        router_instance = StimuliRouter()
        
        if name not in router_instance.sources:
            return {
                "status": "error",
                "message": f"Source not loaded (enabled: false or auth missing)"
            }
        
        messages = router_instance.pull(name)
        return {
            "status": "ok",
            "message": f"Connected successfully, found {len(messages)} messages"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@router.get("/templates")
async def list_templates():
    """List available source templates"""
    templates = []
    
    template_path = SOURCES_DIR / "_template.yaml"
    if template_path.exists():
        with open(template_path) as f:
            templates.append({
                "name": "blank",
                "description": "Empty template - configure from scratch",
                "content": f.read()
            })
    
    # Add preset templates
    presets = [
        {"name": "gmail", "description": "Google Gmail - Email via OAuth2", "icon": "📧"},
        {"name": "slack", "description": "Slack - DMs and channel mentions", "icon": "💬"},
        {"name": "sms", "description": "SMS via Twilio", "icon": "📱"},
        {"name": "discord", "description": "Discord - DMs and server messages", "icon": "🎮"},
        {"name": "telegram", "description": "Telegram - Bot messages", "icon": "✈️"},
        {"name": "github", "description": "GitHub - Notifications, issues, PRs", "icon": "🐙"},
        {"name": "linear", "description": "Linear - Issue tracking", "icon": "📐"},
        {"name": "notion", "description": "Notion - Database items", "icon": "📓"},
        {"name": "twitter", "description": "Twitter/X - Mentions and DMs", "icon": "🐦"},
        {"name": "whatsapp", "description": "WhatsApp Business API", "icon": "💚"},
        {"name": "teams", "description": "Microsoft Teams - Chat messages", "icon": "👥"},
        {"name": "intercom", "description": "Intercom - Customer conversations", "icon": "💬"},
        {"name": "zendesk", "description": "Zendesk - Support tickets", "icon": "🎫"},
        {"name": "jira", "description": "Jira - Issue tracking", "icon": "📋"},
        {"name": "airtable", "description": "Airtable - Database records", "icon": "📊"},
        {"name": "todoist", "description": "Todoist - Tasks", "icon": "✅"},
        {"name": "gcal", "description": "Google Calendar - Events", "icon": "📅"},
        {"name": "shopify", "description": "Shopify - Orders", "icon": "🛒"},
        {"name": "hubspot", "description": "HubSpot - CRM contacts", "icon": "🧡"},
        {"name": "webhook", "description": "Generic webhook endpoint", "icon": "🔗"},
    ]
    
    for preset in presets:
        preset_path = SOURCES_DIR / f"{preset['name']}.yaml"
        templates.append({
            **preset,
            "exists": preset_path.exists()
        })
    
    return templates
