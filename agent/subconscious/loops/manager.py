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
from .workspace_qa import WorkspaceQALoop


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

    Intervals are in days (converted to seconds) so loops run infrequently.
    Loops start PAUSED by default — the user must explicitly start them
    (except health, which auto-starts).

    Returns:
        Configured LoopManager ready to start
    """
    manager = LoopManager()

    DAY = 86400  # seconds in a day

    # ── Tier 1 — operational  (health auto-starts, task paused) ─────
    health = HealthLoop(
        interval=float(os.getenv("AIOS_HEALTH_INTERVAL", str(DAY))),  # 1 day
    )
    health.config.initial_delay = 10  # fire ~10s after boot
    manager.add(health)

    task = TaskPlanner(
        interval=float(os.getenv("AIOS_TASK_INTERVAL", str(DAY))),  # 1 day
        enabled=os.getenv("AIOS_TASK_PLANNER", "1") == "1",
    )
    task.config.initial_delay = 300  # +5 min
    manager.add(task)

    # ── Tier 2 — knowledge work  (every 1-2 days) ──────────────────
    mem = MemoryLoop()
    mem.config.interval_seconds = float(os.getenv("AIOS_MEMORY_INTERVAL", str(DAY)))  # 1 day
    mem.config.initial_delay = 600  # +10 min
    manager.add(mem)

    consol = ConsolidationLoop()
    consol.config.interval_seconds = float(os.getenv("AIOS_CONSOLIDATION_INTERVAL", str(DAY)))  # 1 day
    consol.config.initial_delay = 900  # +15 min
    manager.add(consol)

    thought = ThoughtLoop(
        interval=float(os.getenv("AIOS_THOUGHT_INTERVAL", str(DAY))),  # 1 day
        enabled=os.getenv("AIOS_THOUGHT_LOOP", "1") == "1",
    )
    thought.config.initial_delay = 1500  # +25 min
    manager.add(thought)

    convo = ConvoConceptLoop(
        interval=float(os.getenv("AIOS_CONVO_CONCEPTS_INTERVAL", str(DAY))),  # 1 day
        enabled=os.getenv("AIOS_CONVO_CONCEPTS", "1") == "1",
    )
    convo.config.initial_delay = 1800  # +30 min
    manager.add(convo)

    sy = SyncLoop()
    sy.config.interval_seconds = float(os.getenv("AIOS_SYNC_INTERVAL", str(2 * DAY)))  # 2 days
    sy.config.initial_delay = 2400  # +40 min
    manager.add(sy)

    # ── Tier 3 — heavy LLM work  (every 2-3 days) ─────────────────
    goal = GoalLoop(
        interval=float(os.getenv("AIOS_GOAL_INTERVAL", str(2 * DAY))),  # 2 days
        enabled=os.getenv("AIOS_GOAL_LOOP", "1") == "1",
    )
    goal.config.initial_delay = 3000  # +50 min
    manager.add(goal)

    demo = DemoAuditLoop(
        interval=float(os.getenv("AIOS_DEMO_AUDIT_INTERVAL", str(2 * DAY))),  # 2 days
        enabled=os.getenv("AIOS_DEMO_AUDIT", "1") == "1",
    )
    demo.config.initial_delay = 3900  # +65 min
    manager.add(demo)

    ws_qa = WorkspaceQALoop(
        interval=float(os.getenv("AIOS_WORKSPACE_QA_INTERVAL", str(3 * DAY))),  # 3 days
        enabled=os.getenv("AIOS_WORKSPACE_QA", "1") == "1",
    )
    ws_qa.config.initial_delay = 4800  # +80 min
    manager.add(ws_qa)

    # ── Tier 4 — very heavy / infrequent  (every 3 days) ──────────
    improve = SelfImprovementLoop(
        interval=float(os.getenv("AIOS_SELF_IMPROVE_INTERVAL", str(3 * DAY))),  # 3 days
        enabled=os.getenv("AIOS_SELF_IMPROVE", "1") == "1",
    )
    improve.config.initial_delay = 5700  # +95 min
    manager.add(improve)

    tgen = TrainingGenLoop(
        interval=float(os.getenv("AIOS_TRAINING_GEN_INTERVAL", str(3 * DAY))),  # 3 days
        enabled=os.getenv("AIOS_TRAINING_GEN", "1") == "1",
    )
    tgen.config.initial_delay = 6600  # +110 min
    manager.add(tgen)

    # Load user-defined custom loops from DB
    try:
        manager.load_custom_loops()
    except Exception as e:
        print(f"⚠️ Failed to load custom loops: {e}")
    
    return manager
