"""
Models API - Model Management & Provider Setup
===============================================
Exposes available models, provider configuration, and setup wizard endpoints.
Supports: ollama (local), openai (API), http (custom endpoint), mock.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, Literal, List, Dict, Any
import os
import json

router = APIRouter(prefix="/api/models", tags=["models"])

# In-memory state
_current_model = os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
_current_provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama")


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: str
    description: Optional[str] = None


class ModelsResponse(BaseModel):
    models: List[ModelInfo]
    current: str
    provider: str


class SetModelRequest(BaseModel):
    model_id: str
    provider: Optional[str] = None


class ProviderConfig(BaseModel):
    """Full provider configuration."""
    provider: str   # ollama | openai | http | mock
    model: str = ""
    api_key: Optional[str] = None
    endpoint: Optional[str] = None


class SetupStatus(BaseModel):
    """Whether the agent has a working provider configured."""
    configured: bool
    provider: str
    model: str
    connected: bool
    message: str


# Default models per provider
OLLAMA_DEFAULTS = [
    ModelInfo(id="qwen2.5:7b", name="Qwen 2.5 7B", provider="ollama", description="Local (recommended)"),
    ModelInfo(id="llama3.2:3b", name="Llama 3.2 3B", provider="ollama", description="Local, fast"),
    ModelInfo(id="mistral:7b", name="Mistral 7B", provider="ollama", description="Local"),
    ModelInfo(id="gemma2:9b", name="Gemma 2 9B", provider="ollama", description="Local"),
]

OPENAI_DEFAULTS = [
    ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini", provider="openai", description="Fast, affordable"),
    ModelInfo(id="gpt-4o", name="GPT-4o", provider="openai", description="Flagship"),
    ModelInfo(id="gpt-4.1-mini", name="GPT-4.1 Mini", provider="openai", description="Latest mini"),
    ModelInfo(id="gpt-4.1", name="GPT-4.1", provider="openai", description="Latest flagship"),
]


def get_available_models() -> List[ModelInfo]:
    """Get list of available models from all configured providers."""
    models = []
    provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama").lower()
    
    # Always try Ollama
    try:
        import ollama
        response = ollama.list()
        for m in response.get("models", []):
            model_name = m.get("name", m.get("model", ""))
            if not model_name:
                continue
            display_name = model_name.replace(":", " ").title()
            size = m.get("size", 0)
            size_str = f"{size / 1e9:.1f}GB" if size > 0 else ""
            models.append(ModelInfo(
                id=model_name, name=display_name,
                provider="ollama", description=f"Local {size_str}".strip()
            ))
    except Exception:
        if provider == "ollama":
            models = list(OLLAMA_DEFAULTS)
    
    # Add OpenAI models if key is present
    if os.getenv("OPENAI_API_KEY"):
        models.extend(OPENAI_DEFAULTS)
    
    # Add current model if not in list (custom http, etc.)
    current = os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    if not any(m.id == current for m in models):
        models.append(ModelInfo(
            id=current, name=current, provider=provider, description="Active"
        ))
    
    models.sort(key=lambda m: (0 if m.provider == provider else 1, m.id))
    return models if models else list(OLLAMA_DEFAULTS)


# =============================================================================
# Provider info
# =============================================================================

@router.get("/providers")
async def get_providers():
    """List all supported providers with their current status."""
    ollama_ok = False
    try:
        import urllib.request
        host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        urllib.request.urlopen(f"{host}/api/tags", timeout=3)
        ollama_ok = True
    except Exception:
        pass
    
    return {
        "providers": [
            {
                "id": "ollama",
                "name": "Ollama (Local)",
                "description": "Run models locally on your machine. Free, private, no API key needed.",
                "requires_key": False,
                "requires_endpoint": False,
                "connected": ollama_ok,
                "setup_url": "https://ollama.com",
            },
            {
                "id": "openai",
                "name": "OpenAI",
                "description": "GPT-4o, GPT-4.1, and more. Requires an API key.",
                "requires_key": True,
                "requires_endpoint": False,
                "connected": bool(os.getenv("OPENAI_API_KEY")),
                "setup_url": "https://platform.openai.com/api-keys",
            },
            {
                "id": "http",
                "name": "Custom Endpoint",
                "description": "Any OpenAI-compatible API (Together, Groq, local vLLM, LM Studio, etc.)",
                "requires_key": False,
                "requires_endpoint": True,
                "connected": bool(os.getenv("AIOS_MODEL_ENDPOINT")),
                "setup_url": None,
            },
        ],
        "current": os.getenv("AIOS_MODEL_PROVIDER", "ollama"),
    }


# =============================================================================
# Setup wizard
# =============================================================================

@router.get("/setup/status", response_model=SetupStatus)
async def get_setup_status():
    """Check if the agent has a working provider configured."""
    provider = os.getenv("AIOS_MODEL_PROVIDER", "ollama").lower()
    model = os.getenv("AIOS_MODEL_NAME", "qwen2.5:7b")
    
    # Check connectivity
    connected = False
    message = ""
    
    if provider == "ollama":
        try:
            import urllib.request
            host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            urllib.request.urlopen(f"{host}/api/tags", timeout=3)
            connected = True
            message = f"Ollama connected — using {model}"
        except Exception:
            message = "Ollama not running. Install from ollama.com or switch provider."
    
    elif provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if key:
            # Quick validation — just check that the key format is plausible
            connected = key.startswith("sk-") and len(key) > 20
            message = f"OpenAI configured — using {model}" if connected else "Invalid API key format"
        else:
            message = "No OpenAI API key configured"
    
    elif provider == "http":
        endpoint = os.getenv("AIOS_MODEL_ENDPOINT", "")
        if endpoint:
            try:
                import urllib.request
                urllib.request.urlopen(endpoint.rstrip("/"), timeout=5)
                connected = True
                message = f"Endpoint reachable — using {model}"
            except Exception:
                message = f"Endpoint not reachable: {endpoint}"
        else:
            message = "No endpoint URL configured"
    
    elif provider == "mock":
        connected = True
        message = "Mock provider (no real LLM)"
    
    return SetupStatus(
        configured=connected,
        provider=provider,
        model=model,
        connected=connected,
        message=message,
    )


@router.post("/setup/configure")
async def configure_provider(config: ProviderConfig):
    """Save provider configuration. Sets env vars for the running process and writes to .env."""
    global _current_model, _current_provider
    
    provider = config.provider.lower()
    if provider not in ("ollama", "openai", "http", "mock"):
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
    
    # Set env vars for the running process
    os.environ["AIOS_MODEL_PROVIDER"] = provider
    _current_provider = provider
    
    if config.model:
        os.environ["AIOS_MODEL_NAME"] = config.model
        _current_model = config.model
    
    if config.api_key is not None:
        os.environ["OPENAI_API_KEY"] = config.api_key
    
    if config.endpoint is not None:
        os.environ["AIOS_MODEL_ENDPOINT"] = config.endpoint
    
    # Persist to .env file so it survives restart
    _persist_env({
        "AIOS_MODEL_PROVIDER": provider,
        "AIOS_MODEL_NAME": config.model or _current_model,
        **({"OPENAI_API_KEY": config.api_key} if config.api_key else {}),
        **({"AIOS_MODEL_ENDPOINT": config.endpoint} if config.endpoint else {}),
    })
    
    return {
        "success": True,
        "provider": provider,
        "model": _current_model,
        "message": f"Provider set to {provider}, model: {_current_model}",
    }


@router.post("/setup/test")
async def test_provider(config: ProviderConfig):
    """Test a provider configuration without saving it."""
    provider = config.provider.lower()
    model = config.model or "qwen2.5:7b"
    
    test_messages = [
        {"role": "system", "content": "Reply with exactly: CONNECTION_OK"},
        {"role": "user", "content": "Test"},
    ]
    
    try:
        if provider == "ollama":
            import ollama
            resp = ollama.chat(model=model, messages=test_messages)
            return {"success": True, "response": resp["message"]["content"][:100]}
        
        elif provider == "openai":
            if not config.api_key:
                return {"success": False, "error": "API key required"}
            
            import urllib.request
            url = ((config.endpoint or "").rstrip("/") or "https://api.openai.com/v1") + "/chat/completions"
            payload = {"model": model, "messages": test_messages, "max_tokens": 20}
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
                return {"success": True, "response": text[:100]}
        
        elif provider == "http":
            if not config.endpoint:
                return {"success": False, "error": "Endpoint URL required"}
            
            import urllib.request
            req = urllib.request.Request(
                config.endpoint,
                data=json.dumps({"messages": test_messages}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body.get("message") or body.get("content") or str(body)
                return {"success": True, "response": str(text)[:100]}
        
        elif provider == "mock":
            return {"success": True, "response": "[Mock] CONNECTION_OK"}
        
        else:
            return {"success": False, "error": f"Unknown provider: {provider}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


def _persist_env(updates: Dict[str, str]):
    """Write/update key=value pairs in the project .env file."""
    from pathlib import Path
    env_path = Path(__file__).resolve().parents[2] / ".env"
    
    # Read existing
    lines = []
    if env_path.exists():
        lines = env_path.read_text().splitlines()
    
    # Update or append
    existing_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                existing_keys.add(key)
                continue
        new_lines.append(line)
    
    # Append any keys that weren't already in the file
    for key, val in updates.items():
        if key not in existing_keys:
            new_lines.append(f"{key}={val}")
    
    env_path.write_text("\\n".join(new_lines) + "\\n")


# =============================================================================
# Model list / switch  (existing endpoints, now provider-aware)
# =============================================================================

@router.get("", response_model=ModelsResponse)
async def get_models():
    """Get available models and current selection"""
    global _current_model, _current_provider
    models = get_available_models()
    return ModelsResponse(models=models, current=_current_model, provider=_current_provider)


@router.post("/current")
async def set_current_model(request: SetModelRequest):
    """Set the current model for generation"""
    global _current_model, _current_provider
    
    _current_model = request.model_id
    os.environ["AIOS_MODEL_NAME"] = request.model_id
    
    # If provider explicitly given, switch it
    if request.provider:
        _current_provider = request.provider.lower()
        os.environ["AIOS_MODEL_PROVIDER"] = _current_provider
    
    # Persist
    _persist_env({
        "AIOS_MODEL_NAME": request.model_id,
        **({"AIOS_MODEL_PROVIDER": _current_provider} if request.provider else {}),
    })
    
    return {
        "success": True,
        "model": request.model_id,
        "provider": _current_provider,
        "message": f"Switched to {request.model_id} ({_current_provider})"
    }


@router.get("/current")
async def get_current_model():
    """Get current model info"""
    global _current_model, _current_provider
    return {
        "model": {
            "id": _current_model,
            "name": _current_model,
            "provider": _current_provider,
        }
    }


# =============================================================================
# Pullable model library  (Ollama catalog for browse & download)
# =============================================================================

# Curated catalog of popular Ollama models.
# id = the tag you pass to `ollama pull`, size = approximate disk footprint.
OLLAMA_LIBRARY = [
    {"id": "qwen2.5:7b",      "name": "Qwen 2.5 7B",      "parameters": "7B",  "size": "4.7 GB", "description": "Strong all-rounder, recommended default"},
    {"id": "qwen2.5:3b",      "name": "Qwen 2.5 3B",      "parameters": "3B",  "size": "2.0 GB", "description": "Fast and lightweight"},
    {"id": "qwen2.5:14b",     "name": "Qwen 2.5 14B",     "parameters": "14B", "size": "9.0 GB", "description": "Higher quality, needs more RAM"},
    {"id": "llama3.2:3b",     "name": "Llama 3.2 3B",     "parameters": "3B",  "size": "2.0 GB", "description": "Meta, fast and capable"},
    {"id": "llama3.2:1b",     "name": "Llama 3.2 1B",     "parameters": "1B",  "size": "1.3 GB", "description": "Ultra-light, good for low-RAM machines"},
    {"id": "llama3.1:8b",     "name": "Llama 3.1 8B",     "parameters": "8B",  "size": "4.7 GB", "description": "Meta, solid general purpose"},
    {"id": "mistral:7b",      "name": "Mistral 7B",       "parameters": "7B",  "size": "4.1 GB", "description": "European, strong reasoning"},
    {"id": "gemma2:9b",       "name": "Gemma 2 9B",       "parameters": "9B",  "size": "5.4 GB", "description": "Google, well-rounded"},
    {"id": "gemma2:2b",       "name": "Gemma 2 2B",       "parameters": "2B",  "size": "1.6 GB", "description": "Google, tiny and fast"},
    {"id": "phi3:mini",       "name": "Phi-3 Mini",       "parameters": "3.8B","size": "2.3 GB", "description": "Microsoft, strong for its size"},
    {"id": "phi3:medium",     "name": "Phi-3 Medium",     "parameters": "14B", "size": "7.9 GB", "description": "Microsoft, high quality"},
    {"id": "deepseek-r1:8b",  "name": "DeepSeek R1 8B",   "parameters": "8B",  "size": "4.9 GB", "description": "Reasoning-focused"},
    {"id": "deepseek-r1:1.5b","name": "DeepSeek R1 1.5B", "parameters": "1.5B","size": "1.1 GB", "description": "Tiny reasoning model"},
    {"id": "codellama:7b",    "name": "Code Llama 7B",    "parameters": "7B",  "size": "3.8 GB", "description": "Code-specialised"},
    {"id": "nomic-embed-text", "name": "Nomic Embed Text", "parameters": "137M","size": "274 MB", "description": "Embedding model for search"},
]


@router.get("/library")
async def get_model_library():
    """Return the browsable catalog of Ollama models, annotated with install status."""
    # Get currently installed model names
    installed_ids: set = set()
    try:
        import ollama as _ollama
        response = _ollama.list()
        for m in response.get("models", []):
            name = m.get("name", m.get("model", ""))
            if name:
                installed_ids.add(name)
                # Also add without :latest suffix for matching
                if name.endswith(":latest"):
                    installed_ids.add(name.replace(":latest", ""))
    except Exception:
        pass  # Ollama not running — everything shows as not installed

    catalog = []
    for entry in OLLAMA_LIBRARY:
        catalog.append({
            **entry,
            "installed": entry["id"] in installed_ids,
        })

    return {"models": catalog}


class PullModelRequest(BaseModel):
    model: str


@router.post("/pull")
async def pull_model(request: PullModelRequest):
    """Pull (download) an Ollama model. Streams progress as newline-delimited JSON.

    ⚠️  Downloads can be several GB and may take minutes on slow connections.
    The response streams progress events so the UI can show a progress bar.
    """
    model_id = request.model.strip()
    if not model_id:
        raise HTTPException(status_code=400, detail="Model name is required")

    # Basic validation — only allow model tags that look reasonable
    import re
    if not re.match(r'^[a-zA-Z0-9._:/-]+$', model_id):
        raise HTTPException(status_code=400, detail="Invalid model name")

    def _stream_pull():
        try:
            import ollama as _ollama
            for progress in _ollama.pull(model_id, stream=True):
                event = {
                    "status": progress.get("status", ""),
                    "total": progress.get("total", 0),
                    "completed": progress.get("completed", 0),
                }
                yield json.dumps(event) + "\n"
            yield json.dumps({"status": "success"}) + "\n"
        except Exception as e:
            yield json.dumps({"status": "error", "error": str(e)}) + "\n"

    return StreamingResponse(
        _stream_pull(),
        media_type="application/x-ndjson",
    )
