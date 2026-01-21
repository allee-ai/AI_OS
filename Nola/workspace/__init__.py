"""
Nola Workspace Module
---------------------
Self-contained module for file management within a sandboxed workspace.

Exports:
- router: FastAPI router with all workspace endpoints
- WORKSPACE_ROOT: Path to the workspace directory
"""

from .api import router, WORKSPACE_ROOT

__all__ = ["router", "WORKSPACE_ROOT"]
