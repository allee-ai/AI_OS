"""
Nola Core Module
----------------
Core configuration and settings for the Nola system.

Exports:
- settings: Application settings instance
- Settings: Settings class for type hints
"""

from .config import settings, Settings

__all__ = ["settings", "Settings"]
