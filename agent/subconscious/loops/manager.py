"""
Loop Manager
=============
Manages all background loops (built-in + custom).
"""

import os
from typing import Optional, Dict, Any, List

from .base import BackgroundLoop, LoopConfig, LoopStatus
from .memory import MemoryLoop
from .consolidation import ConsolidationLoop
from .sync import SyncLoop
from .health import HealthLoop
from .thought import ThoughtLoop
from .training_gen import TrainingGenLoop
from .custom import CustomLoop, get_custom_loop_configs
from .task_planner import TaskPlanner
from .goals import GoalLoop
from .self_improve import SelfImprovementLoop
from .convo_concepts import ConvoConceptLoop
from .demo_audit import DemoAuditLoop


class LoopManager:
    """
    Manages all background loops (built-in + custom).
    
    Provides unified start/stop and status reporting.
    """
    
    def __init__(self):
        self._loops: List[BackgroundLoop] = []
    
    def add(self, loop: BackgroundLoop) -> None:
        """Add a loop to be managed."""
        self._loops.append(loop)
    
    def remove(self, name: str) -> bool:
        """Remove and stop a loop by name."""
        for i, loop in enumerate(self._loops):
            if loop.config.name == name:
                loop.stop()
                self._loops.pop(i)
                return True
        return False
    
    def start_all(self) -> None:
        """Start all managed loops."""
        for loop in self._loops:
            loop.start()
    
    def stop_all(self) -> None:
        """Stop all managed loops."""
        for loop in self._loops:
            loop.stop()

    def pause_all(self, wait: bool = True, timeout: float = 120.0) -> None:
        """Pause all loops. If *wait*, block until every in-progress task finishes."""
        for loop in self._loops:
            loop.pause()
        if wait:
            for loop in self._loops:
                loop.wait_idle(timeout=timeout)

    def resume_all(self) -> None:
        """Resume all paused loops."""
        for loop in self._loops:
            loop.resume()
    
    def get_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all loops."""
        return [loop.stats for loop in self._loops]
    
    def get_loop(self, name: str) -> Optional[BackgroundLoop]:
        """Get a specific loop by name."""
        for loop in self._loops:
            if loop.config.name == name:
                return loop
        return None
    
    def load_custom_loops(self) -> int:
        """Load custom loops from DB and add them to the manager. Returns count loaded."""
        configs = get_custom_loop_configs()
        loaded = 0
        for cfg in configs:
            if not cfg["enabled"]:
                continue
            if self.get_loop(cfg["name"]):
                continue
            loop = CustomLoop(
                name=cfg["name"],
                source=cfg["source"],
                target=cfg["target"],
                interval=cfg["interval_seconds"],
                model=cfg["model"],
                prompt=cfg["prompt"],
                enabled=cfg["enabled"],
                max_iterations=cfg.get("max_iterations", 1),
                max_tokens_per_iter=cfg.get("max_tokens_per_iter", 2048),
            )
            loop.config.context_aware = cfg.get("context_aware", False)
            self.add(loop)
            loop.start()
            loaded += 1
        return loaded


def create_default_loops() -> LoopManager:
    """
    Create a LoopManager with all default background loops.
    
    Returns:
        Configured LoopManager ready to start
    """
    manager = LoopManager()
    manager.add(MemoryLoop())       # Extract facts from conversations
    manager.add(ConsolidationLoop()) # Promote approved facts
    manager.add(SyncLoop())          # Sync state across threads
    manager.add(HealthLoop())        # Monitor thread health
    
    # Thought loop — proactive agent reasoning
    thought_enabled = os.getenv("AIOS_THOUGHT_LOOP", "1") == "1"
    thought_interval = float(os.getenv("AIOS_THOUGHT_INTERVAL", "120"))
    manager.add(ThoughtLoop(
        interval=thought_interval,
        enabled=thought_enabled,
    ))
    
    # Task planner — context-aware multi-step task execution
    task_enabled = os.getenv("AIOS_TASK_PLANNER", "1") == "1"
    task_interval = float(os.getenv("AIOS_TASK_INTERVAL", "30"))
    manager.add(TaskPlanner(
        interval=task_interval,
        enabled=task_enabled,
    ))
    
    # Goal generation — proposes goals from recurring concepts + values
    goal_enabled = os.getenv("AIOS_GOAL_LOOP", "1") == "1"
    goal_interval = float(os.getenv("AIOS_GOAL_INTERVAL", "600"))
    manager.add(GoalLoop(
        interval=goal_interval,
        enabled=goal_enabled,
    ))

    # Self-improvement — proposes small code fixes for human approval
    improve_enabled = os.getenv("AIOS_SELF_IMPROVE", "1") == "1"
    improve_interval = float(os.getenv("AIOS_SELF_IMPROVE_INTERVAL", "3600"))
    manager.add(SelfImprovementLoop(
        interval=improve_interval,
        enabled=improve_enabled,
    ))

    # Training data generator — LLM generates synthetic training examples
    training_gen_enabled = os.getenv("AIOS_TRAINING_GEN", "1") == "1"
    training_gen_interval = float(os.getenv("AIOS_TRAINING_GEN_INTERVAL", "7200"))
    manager.add(TrainingGenLoop(
        interval=training_gen_interval,
        enabled=training_gen_enabled,
    ))

    # Conversation concept extraction — backfill imported conversations into graph
    convo_concepts_enabled = os.getenv("AIOS_CONVO_CONCEPTS", "1") == "1"
    convo_concepts_interval = float(os.getenv("AIOS_CONVO_CONCEPTS_INTERVAL", "300"))
    manager.add(ConvoConceptLoop(
        interval=convo_concepts_interval,
        enabled=convo_concepts_enabled,
    ))

    # Demo audit — audits demo-data.json with Kimi K2
    demo_audit_enabled = os.getenv("AIOS_DEMO_AUDIT", "1") == "1"
    demo_audit_interval = float(os.getenv("AIOS_DEMO_AUDIT_INTERVAL", "900"))
    manager.add(DemoAuditLoop(
        interval=demo_audit_interval,
        enabled=demo_audit_enabled,
    ))
    
    # Load user-defined custom loops from DB
    try:
        manager.load_custom_loops()
    except Exception as e:
        print(f"⚠️ Failed to load custom loops: {e}")
    
    return manager
