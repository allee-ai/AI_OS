"""
Triggers
========
Event-driven execution triggers for the subconscious.

Triggers allow actions to be taken in response to:
- Time: Periodic or scheduled execution
- Events: Specific log events (via log_thread)
- Thresholds: Metrics crossing boundaries

These complement the background loops by providing reactive
rather than periodic execution.
"""

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod


class TriggerStatus(Enum):
    """Status of a trigger."""
    DISABLED = "disabled"
    ARMED = "armed"
    FIRED = "fired"
    COOLDOWN = "cooldown"


@dataclass
class TriggerResult:
    """Result of a trigger firing."""
    triggered: bool
    trigger_name: str
    timestamp: str
    reason: str = ""
    data: Dict[str, Any] = field(default_factory=dict)


class BaseTrigger(ABC):
    """
    Abstract base for all trigger types.
    
    Implement check() to define when the trigger should fire.
    """
    
    def __init__(
        self,
        name: str,
        action: Callable[[], None],
        cooldown_seconds: float = 60.0,
        enabled: bool = True
    ):
        self.name = name
        self.action = action
        self.cooldown_seconds = cooldown_seconds
        self.enabled = enabled
        self._status = TriggerStatus.ARMED if enabled else TriggerStatus.DISABLED
        self._last_fired: Optional[str] = None
        self._fire_count = 0
    
    @property
    def status(self) -> TriggerStatus:
        return self._status
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self._status.value,
            "enabled": self.enabled,
            "last_fired": self._last_fired,
            "fire_count": self._fire_count,
            "cooldown": self.cooldown_seconds,
        }
    
    @abstractmethod
    def check(self) -> TriggerResult:
        """
        Check if trigger condition is met.
        
        Returns:
            TriggerResult indicating if trigger should fire
        """
        pass
    
    def fire(self) -> bool:
        """
        Fire the trigger (execute action).
        
        Returns:
            True if action executed, False if on cooldown or disabled
        """
        if not self.enabled or self._status == TriggerStatus.DISABLED:
            return False
        
        # Check cooldown
        if self._last_fired:
            try:
                last_dt = datetime.fromisoformat(self._last_fired)
                if last_dt.tzinfo is None:
                    last_dt = last_dt.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if age < self.cooldown_seconds:
                    self._status = TriggerStatus.COOLDOWN
                    return False
            except Exception:
                pass
        
        # Execute action
        try:
            self._status = TriggerStatus.FIRED
            self.action()
            self._last_fired = datetime.now(timezone.utc).isoformat()
            self._fire_count += 1
            self._status = TriggerStatus.ARMED
            return True
        except Exception as e:
            # Log error
            try:
                from Nola.threads.log import log_error
                log_error(f"trigger:{self.name}", e, context="trigger fire")
            except Exception:
                pass
            self._status = TriggerStatus.ARMED
            return False
    
    def arm(self) -> None:
        """Enable and arm the trigger."""
        self.enabled = True
        self._status = TriggerStatus.ARMED
    
    def disarm(self) -> None:
        """Disable the trigger."""
        self.enabled = False
        self._status = TriggerStatus.DISABLED


class TimeTrigger(BaseTrigger):
    """
    Trigger that fires after a time interval.
    
    Unlike loops which run continuously, time triggers fire once
    when checked after the interval has passed.
    """
    
    def __init__(
        self,
        name: str,
        action: Callable[[], None],
        interval_seconds: float,
        cooldown_seconds: float = 0.0,
        enabled: bool = True
    ):
        super().__init__(name, action, cooldown_seconds, enabled)
        self.interval_seconds = interval_seconds
        self._last_check = datetime.now(timezone.utc).isoformat()
    
    def check(self) -> TriggerResult:
        """Check if interval has passed."""
        now = datetime.now(timezone.utc)
        
        try:
            last_dt = datetime.fromisoformat(self._last_check)
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            elapsed = (now - last_dt).total_seconds()
            
            if elapsed >= self.interval_seconds:
                self._last_check = now.isoformat()
                return TriggerResult(
                    triggered=True,
                    trigger_name=self.name,
                    timestamp=now.isoformat(),
                    reason=f"Interval of {self.interval_seconds}s elapsed",
                    data={"elapsed": elapsed}
                )
        except Exception:
            pass
        
        return TriggerResult(
            triggered=False,
            trigger_name=self.name,
            timestamp=now.isoformat()
        )


class EventTrigger(BaseTrigger):
    """
    Trigger that fires when specific event types occur.
    
    Monitors log_thread for matching events.
    """
    
    def __init__(
        self,
        name: str,
        action: Callable[[], None],
        event_types: List[str],
        cooldown_seconds: float = 60.0,
        enabled: bool = True
    ):
        super().__init__(name, action, cooldown_seconds, enabled)
        self.event_types: Set[str] = set(event_types)
        self._seen_events: Set[str] = set()  # Track seen event IDs
    
    def check(self) -> TriggerResult:
        """Check for matching events in log_thread."""
        now = datetime.now(timezone.utc)
        
        try:
            from Nola.threads.log import read_events
            
            # Check recent events for any matching types
            for event_type in self.event_types:
                events = read_events(event_type=event_type, limit=10)
                
                if events:
                    for event in events:
                        event_id = f"{event.get('ts', '')}:{event.get('event_type', '')}"
                        
                        if event_id not in self._seen_events:
                            self._seen_events.add(event_id)
                            
                            # Limit seen events cache
                            if len(self._seen_events) > 1000:
                                self._seen_events = set(list(self._seen_events)[-500:])
                            
                            return TriggerResult(
                                triggered=True,
                                trigger_name=self.name,
                                timestamp=now.isoformat(),
                                reason=f"Event '{event_type}' detected",
                                data={"event": event}
                            )
        except Exception:
            pass
        
        return TriggerResult(
            triggered=False,
            trigger_name=self.name,
            timestamp=now.isoformat()
        )


class ThresholdTrigger(BaseTrigger):
    """
    Trigger that fires when a metric crosses a threshold.
    
    Useful for resource monitoring, queue depths, etc.
    """
    
    def __init__(
        self,
        name: str,
        action: Callable[[], None],
        metric_fn: Callable[[], float],
        threshold: float,
        direction: str = "above",  # "above" or "below"
        cooldown_seconds: float = 300.0,
        enabled: bool = True
    ):
        super().__init__(name, action, cooldown_seconds, enabled)
        self.metric_fn = metric_fn
        self.threshold = threshold
        self.direction = direction
        self._last_value: Optional[float] = None
        self._was_triggered = False
    
    def check(self) -> TriggerResult:
        """Check if metric has crossed threshold."""
        now = datetime.now(timezone.utc)
        
        try:
            value = self.metric_fn()
            self._last_value = value
            
            # Check threshold crossing
            if self.direction == "above":
                triggered = value > self.threshold
            else:
                triggered = value < self.threshold
            
            # Only trigger on transition
            if triggered and not self._was_triggered:
                self._was_triggered = True
                return TriggerResult(
                    triggered=True,
                    trigger_name=self.name,
                    timestamp=now.isoformat(),
                    reason=f"Metric {self.direction} threshold ({value} vs {self.threshold})",
                    data={"value": value, "threshold": self.threshold}
                )
            
            # Reset if back to normal
            if not triggered:
                self._was_triggered = False
                
        except Exception as e:
            return TriggerResult(
                triggered=False,
                trigger_name=self.name,
                timestamp=now.isoformat(),
                reason=f"Error checking metric: {e}"
            )
        
        return TriggerResult(
            triggered=False,
            trigger_name=self.name,
            timestamp=now.isoformat()
        )


class TriggerManager:
    """
    Manages multiple triggers.
    
    Can run a check loop or be polled manually.
    """
    
    def __init__(self):
        self._triggers: Dict[str, BaseTrigger] = {}
        self._check_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def add(self, trigger: BaseTrigger) -> None:
        """Add a trigger to be managed."""
        self._triggers[trigger.name] = trigger
    
    def remove(self, name: str) -> bool:
        """Remove a trigger by name."""
        if name in self._triggers:
            del self._triggers[name]
            return True
        return False
    
    def get(self, name: str) -> Optional[BaseTrigger]:
        """Get a trigger by name."""
        return self._triggers.get(name)
    
    def check_all(self) -> List[TriggerResult]:
        """
        Check all triggers and fire any that are triggered.
        
        Returns:
            List of results for triggers that fired
        """
        results = []
        
        for trigger in self._triggers.values():
            if not trigger.enabled:
                continue
            
            result = trigger.check()
            if result.triggered:
                if trigger.fire():
                    results.append(result)
        
        return results
    
    def start_check_loop(self, interval: float = 5.0) -> None:
        """Start a background loop that checks all triggers."""
        if self._check_thread and self._check_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._check_thread = threading.Thread(
            target=self._check_loop,
            args=(interval,),
            name="trigger-manager",
            daemon=True
        )
        self._check_thread.start()
    
    def stop_check_loop(self) -> None:
        """Stop the background check loop."""
        self._stop_event.set()
        if self._check_thread and self._check_thread.is_alive():
            self._check_thread.join(timeout=5.0)
    
    def _check_loop(self, interval: float) -> None:
        """Background loop that checks triggers."""
        while not self._stop_event.is_set():
            self.check_all()
            self._stop_event.wait(timeout=interval)
    
    def get_stats(self) -> List[Dict[str, Any]]:
        """Get stats for all triggers."""
        return [t.stats for t in self._triggers.values()]


# Convenience factories for common triggers

def create_pending_facts_trigger(
    action: Callable[[], None],
    threshold: int = 50
) -> ThresholdTrigger:
    """
    Create a trigger that fires when pending facts exceed threshold.
    
    Useful for triggering consolidation when memory is filling up.
    """
    def get_pending_count() -> float:
        try:
            from Nola.temp_memory import get_all_pending
            pending = get_all_pending()
            return float(len(pending) if pending else 0)
        except Exception:
            return 0.0
    
    return ThresholdTrigger(
        name="pending_facts_high",
        action=action,
        metric_fn=get_pending_count,
        threshold=float(threshold),
        direction="above",
        cooldown_seconds=300.0
    )


def create_error_trigger(
    action: Callable[[], None],
    cooldown: float = 60.0
) -> EventTrigger:
    """
    Create a trigger that fires on error events.
    
    Useful for alerting or recovery actions.
    """
    return EventTrigger(
        name="error_alert",
        action=action,
        event_types=["error", "system:error"],
        cooldown_seconds=cooldown
    )


__all__ = [
    "BaseTrigger",
    "TriggerStatus",
    "TriggerResult",
    "TimeTrigger",
    "EventTrigger",
    "ThresholdTrigger",
    "TriggerManager",
    "create_pending_facts_trigger",
    "create_error_trigger",
]
