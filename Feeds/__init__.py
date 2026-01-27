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

__all__ = ["api_router", "FeedsRouter"]
