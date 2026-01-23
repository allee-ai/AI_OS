"""
Agent Core Threads
=================

The 6 psychological structures that compose the agent's mind.

Each thread:
- Has a specific psychological function
- Contains modules that provide context slices
- Reports metadata to the subconscious
- Implements the ThreadInterface protocol

ARCHITECTURE:

    ┌─────────────────────────────────────────────────────┐
    │                  SUBCONSCIOUS                       │
    │  (assembles state from all threads)                 │
    └────────────────────┬────────────────────────────────┘
                         │
    ┌────────────────────┴────────────────────────────────┐
    │                                                     │
    ▼                    ▼                    ▼           │
┌──────────┐      ┌──────────┐      ┌──────────┐         │
│ IDENTITY │      │   LOG    │      │ LINKING  │         │
│          │      │          │      │   CORE   │         │
│ who am I │      │ temporal │      │relevance │         │
│ who r u  │      │ history  │      │ scoring  │         │
└──────────┘      └──────────┘      └──────────┘         │
                                                          │
    ▼                    ▼                    ▼           │
┌──────────┐      ┌──────────┐      ┌──────────┐         │
│   FORM   │      │PHILOSOPHY│      │  REFLEX  │         │
│          │      │          │      │          │         │
│ tool use │      │ values & │      │  quick   │         │
│ actions  │      │ reasoning│      │ patterns │         │
└──────────┘      └──────────┘      └──────────┘         │
    │                    │                    │           │
    └────────────────────┴────────────────────┴───────────┘

USAGE:

    from agent.threads import get_all_threads, get_thread
    
    # Get all thread adapters
    threads = get_all_threads()
    
    # Get specific thread
    identity = get_thread("identity")
    facts = identity.get_context(level=2)
"""

from typing import Dict, List, Optional

# Import base adapter
from .base import (
    BaseThreadAdapter,
    ThreadInterface,
    ThreadStatus,
    HealthReport,
    IntrospectionResult,
)

# Import thread adapters (all use schema.py)
from .identity.adapter import IdentityThreadAdapter
from .log.adapter import LogThreadAdapter
from .form.adapter import FormThreadAdapter
from .philosophy.adapter import PhilosophyThreadAdapter
from .reflex.adapter import ReflexThreadAdapter

# LinkingCore is a utility, not a data thread
from .linking_core.adapter import LinkingCoreThreadAdapter

# Thread registry
_THREADS: Dict[str, "BaseThreadAdapter"] = {}


def _register_threads():
    """Initialize all core threads."""
    global _THREADS
    _THREADS = {
        "identity": IdentityThreadAdapter(),
        "log": LogThreadAdapter(),
        "linking_core": LinkingCoreThreadAdapter(),
        "form": FormThreadAdapter(),
        "philosophy": PhilosophyThreadAdapter(),
        "reflex": ReflexThreadAdapter(),
    }


def get_all_threads() -> List:
    """Get all registered thread adapters."""
    if not _THREADS:
        _register_threads()
    return list(_THREADS.values())


def get_thread(name: str) -> Optional:
    """Get a specific thread by name."""
    if not _THREADS:
        _register_threads()
    return _THREADS.get(name)


def get_thread_names() -> List[str]:
    """Get names of all registered threads."""
    if not _THREADS:
        _register_threads()
    return list(_THREADS.keys())


# =============================================================================
# LinkingCore scoring utilities
# =============================================================================
from .linking_core import (
    score_relevance,
    rank_items,
)


__all__ = [
    # Base classes
    "BaseThreadAdapter",
    "ThreadInterface",
    "ThreadStatus",
    "HealthReport",
    "IntrospectionResult",
    
    # Thread adapters
    "get_all_threads",
    "get_thread",
    "get_thread_names",
    "IdentityThreadAdapter",
    "LogThreadAdapter",
    "LinkingCoreThreadAdapter",
    "FormThreadAdapter",
    "PhilosophyThreadAdapter",
    "ReflexThreadAdapter",
    
    # LinkingCore scoring
    "score_relevance",
    "rank_items",
]
