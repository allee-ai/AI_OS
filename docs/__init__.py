"""
Docs Module
-----------
Serve markdown documentation files via API.

Exports:
- router: FastAPI router for docs endpoints
"""

from .api import router

__all__ = ["router"]
