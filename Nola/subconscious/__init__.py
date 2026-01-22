"""
Nola Subconscious
=================
The central nervous system - builds and maintains all internal state.

Key insight: "Subconscious builds state, agent just reads it."

The agent becomes stateless. Before each response, agent_service calls
get_consciousness_context() to get assembled context from all registered
threads (identity, memory, logs, etc.).

Usage:
    from Nola.subconscious import wake, get_consciousness_context
    
    # At startup
    wake()
    
    # Before agent.generate()
    context = get_consciousness_context(level=2)
    response = agent.generate(user_input, context)

Architecture:
    ThreadRegistry ← holds adapters for each internal module
    SubconsciousCore ← orchestrates introspection and context
    BackgroundLoops ← periodic tasks (consolidation, sync, health)
    Triggers ← event-driven execution

Threads (built-in adapters):
    - identity: Core identity and user preferences (Nola.threads.identity)
    - temp_memory: Session facts pending consolidation (Nola.subconscious.temp_memory)
    - log_thread: Event timeline (Nola.log_thread)
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure Nola package is importable from any context
# This handles cases where we're imported from backend/ or other locations
_nola_dir = Path(__file__).resolve().parent.parent  # Nola/
_project_root = _nola_dir.parent  # AI_OS/
if str(_nola_dir) not in sys.path:
    sys.path.insert(0, str(_nola_dir))
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# Core components
from .core import (
    ThreadRegistry,
    SubconsciousCore,
    get_core,
)

# NEW: Orchestrator (uses schema.py)
from .orchestrator import (
    Subconscious,
    get_subconscious,
    build_context,
    record_interaction,
)

# API router
from .api import router as subconscious_router

# Thread interface (from Nola.threads, not local subdir)
from Nola.threads.base import (
    ThreadInterface,
    ThreadStatus,
    HealthReport,
    IntrospectionResult,
    BaseThreadAdapter,
)

# Contract (canonical location)
from .contract import (
    create_metadata,
    is_stale,
    should_sync,
    mark_synced,
    request_sync,
    get_age_seconds,
)

# Background loops
from .loops import (
    BackgroundLoop,
    LoopConfig,
    LoopStatus,
    ConsolidationLoop,
    SyncLoop,
    HealthLoop,
    LoopManager,
    create_default_loops,
)

# Triggers
from .triggers import (
    BaseTrigger,
    TriggerStatus,
    TriggerResult,
    TimeTrigger,
    EventTrigger,
    ThresholdTrigger,
    TriggerManager,
)


# Module-level state
_loop_manager: Optional[LoopManager] = None
_trigger_manager: Optional[TriggerManager] = None


def wake(start_loops: bool = True) -> None:
    """
    Initialize the subconscious and start background processes.
    
    Call this at application startup to:
    - Register built-in thread adapters
    - Start background loops (consolidation, sync, health)
    - Arm event triggers
    
    Args:
        start_loops: Whether to start background loops (default True)
    """
    global _loop_manager, _trigger_manager
    
    core = get_core()
    core.wake()
    
    if start_loops:
        _loop_manager = create_default_loops()
        _loop_manager.start_all()
    
    _trigger_manager = TriggerManager()


def sleep() -> None:
    """
    Gracefully shutdown the subconscious.
    
    Call this at application shutdown to:
    - Stop background loops
    - Flush pending state
    - Clean up resources
    """
    global _loop_manager, _trigger_manager
    
    if _loop_manager:
        _loop_manager.stop_all()
        _loop_manager = None
    
    if _trigger_manager:
        _trigger_manager.stop_check_loop()
        _trigger_manager = None
    
    core = get_core()
    core.sleep()


def get_context(level: int = 2) -> Dict[str, Any]:
    """
    Assemble context from all threads at the specified level.
    
    Args:
        level: Context detail level (1=minimal, 2=moderate, 3=full)
    
    Returns:
        Dict with 'facts' list and 'threads' detail dict
    """
    core = get_core()
    return core.get_context(level)


def get_consciousness_context(level: int = 2) -> str:
    """
    Format context as a string for system prompt injection.
    
    This is the main API for agent_service.py to call before
    generating a response. Returns a formatted string that can
    be prepended to the system prompt.
    
    Args:
        level: Context detail level (1=minimal, 2=moderate, 3=full)
    
    Returns:
        Formatted string suitable for system prompt
    
    Example:
        context = get_consciousness_context(level=2)
        system_prompt = f"{context}\\n\\n{base_system_prompt}"
    """
    core = get_core()
    return core.get_consciousness_context(level)


def get_status() -> Dict[str, Any]:
    """
    Get overall status of the subconscious for debugging/UI.
    
    Returns:
        Status dict with health, thread info, loop status, timing
    """
    core = get_core()
    status = core.get_status()
    
    # Add loop status
    if _loop_manager:
        status["loops"] = _loop_manager.get_stats()
    else:
        status["loops"] = []
    
    # Add trigger status
    if _trigger_manager:
        status["triggers"] = _trigger_manager.get_stats()
    else:
        status["triggers"] = []
    
    return status


def register_thread(adapter: ThreadInterface) -> None:
    """
    Register a custom thread adapter.
    
    Use this to add new data sources to the subconscious.
    The adapter must implement ThreadInterface (name, description,
    health(), introspect()).
    
    Args:
        adapter: Thread adapter implementing ThreadInterface
    """
    core = get_core()
    core.registry.register(adapter)


def get_thread(name: str) -> Optional[ThreadInterface]:
    """
    Get a registered thread adapter by name.
    
    Args:
        name: Thread name (e.g., "identity", "temp_memory", "log_thread")
    
    Returns:
        Thread adapter if found, None otherwise
    """
    core = get_core()
    return core.registry.get(name)


__all__ = [
    # Main API
    "wake",
    "sleep",
    "get_context",
    "get_consciousness_context",
    "get_status",
    "register_thread",
    "get_thread",
    
    # NEW: Orchestrator (uses schema.py)
    "Subconscious",
    "get_subconscious",
    "build_context",
    "record_interaction",
    
    # Core
    "ThreadRegistry",
    "SubconsciousCore",
    "get_core",
    
    # Thread interface
    "ThreadInterface",
    "ThreadStatus",
    "HealthReport",
    "IntrospectionResult",
    "BaseThreadAdapter",
    
    # Contract
    "create_metadata",
    "is_stale",
    "should_sync",
    "mark_synced",
    "request_sync",
    "get_age_seconds",
    
    # Loops
    "BackgroundLoop",
    "LoopConfig",
    "LoopStatus",
    "ConsolidationLoop",
    "SyncLoop",
    "HealthLoop",
    "LoopManager",
    "create_default_loops",
    
    # Triggers
    "BaseTrigger",
    "TriggerStatus",
    "TriggerResult",
    "TimeTrigger",
    "EventTrigger",
    "ThresholdTrigger",
    "TriggerManager",
]
