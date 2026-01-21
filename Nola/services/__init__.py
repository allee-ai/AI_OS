"""
Nola Services Module
--------------------
Background services and API management.

Exports:
- router: FastAPI router for service management
- AgentService: Core agent connecting chat to HEA system
- FactExtractor: LLM-based fact extraction
- KernelService: Browser automation
- ImportService: Conversation imports
"""

from .api import router

__all__ = ["router"]