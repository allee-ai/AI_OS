"""
Agent Subconscious
=================
The central nervous system - builds and maintains all internal state.

Key insight: "Subconscious builds state, agent just reads it."

The agent becomes stateless. Before each response, agent_service calls
get_consciousness_context() to get assembled context from all registered
threads (identity, memory, logs, etc.).

Usage:
    from agent.subconscious import wake, get_consciousness_context
    
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
    - identity: Core identity and user preferences (agent.threads.identity)
    - temp_memory: Session facts pending consolidation (agent.subconscious.temp_memory)
    - log_thread: Event timeline (agent.log_thread)

Loops vs Reflexes:
    Both share the same memory bus — like a person's internal and external processes.
    
    Loops = internal cognitive operations
        Consolidation, extraction, concept linking, self-improvement.
        Run on timers / internal triggers. No direct external I/O.
        Loops CAN own reflex protocols (e.g. consolidation loop may
        trigger a reflex to notify user when done).
    
    Reflexes = external stimulus → external action
        Greetings, shortcuts, system triggers, tool invocations.
        Activated by outside input. Produce externally-visible results.
        Reflexes CANNOT own loops — exception: thought_loop, which
        bridges both (internal reasoning triggered by external input).
    
    Key rule: loops can own reflex protocols, but not vice versa
    (except thought_loop which bridges internal/external).
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure Agent package is importable from any context
# This handles cases where we're imported from backend/ or other locations
_aios_dir = Path(__file__).resolve().parent.parent  # agent/
_project_root = _aios_dir.parent  # AI_OS/
if str(_aios_dir) not in sys.path:
    sys.path.insert(0, str(_aios_dir))
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

# Thread interface (from agent.threads, not local subdir)
from agent.threads.base import (
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
    MemoryLoop,
    ConsolidationLoop,
    SyncLoop,
    HealthLoop,
    ThoughtLoop,
    CustomLoop,
    LoopManager,
    create_default_loops,
    CUSTOM_LOOP_SOURCES,
    CUSTOM_LOOP_TARGETS,
    THOUGHT_CATEGORIES,
    THOUGHT_PRIORITIES,
    TASK_STATUSES,
    save_custom_loop_config,
    get_custom_loop_configs,
    get_custom_loop_config,
    delete_custom_loop_config,
    get_thought_log,
    save_thought,
    mark_thought_acted,
    TaskPlanner,
    create_task,
    get_tasks,
    get_task,
    update_task_status,
    cancel_task,
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
        
        # Log custom loops loaded
        custom_count = sum(1 for l in _loop_manager._loops if isinstance(l, CustomLoop))
        if custom_count:
            print(f"  ✓ Loaded {custom_count} custom loop(s)")
    
    _trigger_manager = TriggerManager()
    
    # Wire built-in triggers
    from .triggers import create_pending_facts_trigger, create_error_trigger
    
    # When pending facts pile up, trigger an early consolidation
    def _trigger_consolidation():
        if _loop_manager:
            loop = _loop_manager.get_loop("consolidation")
            if loop and hasattr(loop, '_consolidate'):
                try:
                    loop._consolidate()
                except Exception as e:
                    print(f"⚠️ Triggered consolidation failed: {e}")
    
    pending_trigger = create_pending_facts_trigger(
        action=_trigger_consolidation,
        threshold=50,
    )
    _trigger_manager.add(pending_trigger)
    
    # Log errors for observability
    def _on_error_event():
        try:
            from agent.threads.log import log_event
            log_event("system:trigger", "error_trigger", "Error trigger fired")
        except Exception:
            pass
    
    error_trigger = create_error_trigger(
        action=_on_error_event,
        cooldown=60.0,
    )
    _trigger_manager.add(error_trigger)
    
    _trigger_manager.start_check_loop(interval=30.0)


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


def pause_loops(wait: bool = True, timeout: float = 120.0) -> None:
    """Pause all background loops, optionally waiting for in-progress tasks to finish."""
    if _loop_manager:
        _loop_manager.pause_all(wait=wait, timeout=timeout)
        print("[Subconscious] All loops paused")


def resume_loops() -> None:
    """Resume all previously paused background loops."""
    if _loop_manager:
        _loop_manager.resume_all()
        print("[Subconscious] All loops resumed")


def get_consciousness_context(level: int = 2, query: str = "") -> str:
    """
    Format context as a string for system prompt injection.
    
    This is the main API for agent_service.py to call before
    generating a response. Returns a formatted string that can
    be prepended to the system prompt.
    
    Now uses build_state() - the unified STATE + ASSESS architecture.
    
    Args:
        level: Context detail level (1=minimal, 2=moderate, 3=full) - maps to default scores
        query: The assess block content (user message, etc.) - for relevance scoring
    
    Returns:
        Formatted STATE block string with dot notation facts
    
    Example:
        context = get_consciousness_context(level=2, query=user_input)
        system_prompt = f"{context}\\n\\n{base_system_prompt}"
    """
    from .orchestrator import build_state
    return build_state(query=query)


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
    "pause_loops",
    "resume_loops",
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
    "MemoryLoop",
    "ConsolidationLoop",
    "SyncLoop",
    "HealthLoop",
    "ThoughtLoop",
    "CustomLoop",
    "LoopManager",
    "create_default_loops",
    "CUSTOM_LOOP_SOURCES",
    "CUSTOM_LOOP_TARGETS",
    "THOUGHT_CATEGORIES",
    "THOUGHT_PRIORITIES",
    "TASK_STATUSES",
    "save_custom_loop_config",
    "get_custom_loop_configs",
    "get_custom_loop_config",
    "delete_custom_loop_config",
    "get_thought_log",
    "save_thought",
    "mark_thought_acted",
    "TaskPlanner",
    "create_task",
    "get_tasks",
    "get_task",
    "update_task_status",
    "cancel_task",
    
    # Triggers
    "BaseTrigger",
    "TriggerStatus",
    "TriggerResult",
    "TimeTrigger",
    "EventTrigger",
    "ThresholdTrigger",
    "TriggerManager",
]
