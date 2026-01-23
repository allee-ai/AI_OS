"""
Agent Core Module
----------------
Core configuration and settings for the Agent system.

Exports:
- settings: Application settings instance
- Settings: Settings class for type hints
- models_router: FastAPI router for model management
"""

from .config import settings, Settings
from .models_api import router as models_router

__all__ = ["settings", "Settings", "models_router"]
