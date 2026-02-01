"""
Agent Feeds Module
-------------------
External feed sources and routing.

Exports:
- api_router: FastAPI router for feeds management endpoints
- FeedsRouter: Internal router for feeds processing
"""

from .api import router as api_router
from .router import FeedsRouter

# Import source modules to register their event types
try:
    from .sources import gmail
except ImportError:
    pass

try:
    from .sources import discord
except ImportError:
    pass

__all__ = ["api_router", "FeedsRouter"]
