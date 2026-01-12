"""Memory service facade.

Provides unified imports for memory extraction and consolidation without
exposing internal file layout.
"""

from Nola.services.memory_service import MemoryService
from Nola.services.consolidation_daemon import ConsolidationDaemon, ConsolidationConfig

__all__ = [
    "MemoryService",
    "ConsolidationDaemon",
    "ConsolidationConfig",
]
