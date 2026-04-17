"""
Background Loops Package
========================
Periodic tasks that run in the subconscious to maintain state.

All public symbols are re-exported here so that existing imports
like ``from agent.subconscious.loops import MemoryLoop`` continue
to work after the split from a single file into a package.
"""

# Base classes
from .base import (
    BackgroundLoop,
    LoopConfig,
    LoopStatus,
    acquire_ollama_gate,
    release_ollama_gate,
)

# Individual loops
from .memory import MemoryLoop
from .consolidation import ConsolidationLoop
from .sync import SyncLoop
from .health import HealthLoop

# Thought loop + helpers
from .thought import (
    ThoughtLoop,
    THOUGHT_CATEGORIES,
    THOUGHT_PRIORITIES,
    get_thought_log,
    save_thought,
    mark_thought_acted,
)

# Custom loops + helpers
from .custom import (
    CustomLoop,
    CUSTOM_LOOP_SOURCES,
    CUSTOM_LOOP_TARGETS,
    save_custom_loop_config,
    get_custom_loop_configs,
    get_custom_loop_config,
    delete_custom_loop_config,
)

# Task planner
from .task_planner import (
    TaskPlanner,
    TASK_STATUSES,
    create_task,
    get_tasks,
    get_task,
    update_task_status,
    cancel_task,
)

# Goal generation
from .goals import (
    GoalLoop,
    propose_goal,
    get_proposed_goals,
    resolve_goal,
)

# Self-improvement
from .self_improve import (
    SelfImprovementLoop,
    propose_improvement,
    get_proposed_improvements,
    resolve_improvement,
    apply_improvement,
)

# Training data generator
from .training_gen import (
    TrainingGenLoop,
    get_generated_examples,
    get_generated_count,
    get_generated_stats,
    clear_generated,
)

# Conversation concept extraction (backfill imported conversations)
from .convo_concepts import (
    ConvoConceptLoop,
    get_backfill_status,
    reset_backfill,
)

# Evolution (autonomous 3-model showdown)
from .evolve import (
    EvolutionLoop,
    get_evolution_log,
)

# Manager + factory
from .manager import (
    LoopManager,
    create_default_loops,
)


__all__ = [
    # Base
    "BackgroundLoop",
    "LoopConfig",
    "LoopStatus",
    # Loops
    "MemoryLoop",
    "ConsolidationLoop",
    "SyncLoop",
    "HealthLoop",
    "ThoughtLoop",
    "CustomLoop",
    # Manager
    "LoopManager",
    "create_default_loops",
    # Constants
    "CUSTOM_LOOP_SOURCES",
    "CUSTOM_LOOP_TARGETS",
    "THOUGHT_CATEGORIES",
    "THOUGHT_PRIORITIES",
    "TASK_STATUSES",
    # Custom loop helpers
    "save_custom_loop_config",
    "get_custom_loop_configs",
    "get_custom_loop_config",
    "delete_custom_loop_config",
    # Thought helpers
    "get_thought_log",
    "save_thought",
    "mark_thought_acted",
    # Task planner
    "TaskPlanner",
    "create_task",
    "get_tasks",
    "get_task",
    "update_task_status",
    "cancel_task",
    # Goal generation
    "GoalLoop",
    "propose_goal",
    "get_proposed_goals",
    "resolve_goal",
    # Self-improvement
    "SelfImprovementLoop",
    "propose_improvement",
    "get_proposed_improvements",
    "resolve_improvement",
    "apply_improvement",
    # Conversation concept extraction
    "ConvoConceptLoop",
    "get_backfill_status",
    "reset_backfill",
    # Evolution
    "EvolutionLoop",
    "get_evolution_log",
]
