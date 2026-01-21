"""
Models API - Model Management
=============================
Exposes available models and allows switching between them.
Works with both local Ollama models and cloud API models.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal, List
import os

router = APIRouter(prefix="/api/models", tags=["models"])

# In-memory state
_current_model = os.getenv("NOLA_MODEL_NAME", "qwen2.5:7b")


class ModelInfo(BaseModel):
    id: str
    name: str
    provider: Literal["ollama", "cloud"]
    description: Optional[str] = None


class ModelsResponse(BaseModel):
    models: List[ModelInfo]
    current: str


class SetModelRequest(BaseModel):
    model_id: str


# Default available models
DEFAULT_MODELS = [
    ModelInfo(id="qwen2.5:7b", name="Qwen 2.5 7B", provider="ollama", description="Local (default)"),
    ModelInfo(id="llama3.2:3b", name="Llama 3.2 3B", provider="ollama", description="Local, fast"),
    ModelInfo(id="mistral:7b", name="Mistral 7B", provider="ollama", description="Local"),
    ModelInfo(id="kimi-k2:1t-cloud", name="Kimi K2", provider="ollama", description="1T MoE agent (cloud)"),
    ModelInfo(id="gpt-oss:120b-cloud", name="GPT-OSS 120B", provider="ollama", description="120B reasoning (cloud)"),
    ModelInfo(id="gpt-oss:20b-cloud", name="GPT-OSS 20B", provider="ollama", description="20B fast (cloud)"),
]


def get_available_models() -> List[ModelInfo]:
    """Get list of available models from Ollama."""
    models = []
    
    try:
        import ollama
        response = ollama.list()
        
        for m in response.get("models", []):
            model_name = m.get("name", m.get("model", ""))
            if not model_name:
                continue
            
            is_cloud = "-cloud" in model_name or model_name.endswith("-cloud")
            display_name = model_name.replace("-cloud", " (cloud)").replace(":", " ").title()
            
            size = m.get("size", 0)
            size_str = f"{size / 1e9:.1f}GB" if size > 0 else ""
            desc = f"Cloud" if is_cloud else f"Local {size_str}".strip()
            
            models.append(ModelInfo(
                id=model_name,
                name=display_name,
                provider="ollama",
                description=desc
            ))
                    
    except Exception:
        models = list(DEFAULT_MODELS)
    
    models.sort(key=lambda m: (1 if "cloud" in m.id else 0, m.id))
    return models if models else list(DEFAULT_MODELS)


@router.get("", response_model=ModelsResponse)
async def get_models():
    """Get available models and current selection"""
    global _current_model
    models = get_available_models()
    return ModelsResponse(models=models, current=_current_model)


@router.post("/current")
async def set_current_model(request: SetModelRequest):
    """Set the current model for generation"""
    global _current_model
    
    models = get_available_models()
    valid_ids = {m.id for m in models}
    
    if request.model_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Unknown model: {request.model_id}")
    
    _current_model = request.model_id
    os.environ["NOLA_MODEL_NAME"] = request.model_id
    os.environ["NOLA_MODEL_PROVIDER"] = "ollama"
    
    model = next(m for m in models if m.id == request.model_id)
    
    return {
        "success": True,
        "model": model.model_dump(),
        "message": f"Switched to {model.name}"
    }


@router.get("/current")
async def get_current_model():
    """Get current model info"""
    global _current_model
    models = get_available_models()
    model = next((m for m in models if m.id == _current_model), None)
    
    if model:
        return {"model": model.model_dump()}
    return {"model": {"id": _current_model, "name": _current_model, "provider": "ollama"}}
