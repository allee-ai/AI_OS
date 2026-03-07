"""
Background Loop Base Classes
============================
Core abstractions for periodic background tasks.
"""

import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


class LoopStatus(Enum):
    """Status of a background loop."""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class LoopConfig:
    """Configuration for a background loop."""
    interval_seconds: float
    name: str
    enabled: bool = True
    max_errors: int = 3  # Stop after this many consecutive errors
    error_backoff: float = 2.0  # Multiply interval by this on error


class BackgroundLoop:
    """
    Base class for background loops.
    
    Runs a task function periodically on a daemon thread.
    Handles error recovery, backoff, and graceful shutdown.
    """
    
    def __init__(self, config: LoopConfig, task: Callable[[], None]):
        self.config = config
        self.task = task
        self._status = LoopStatus.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._consecutive_errors = 0
        self._last_run: Optional[str] = None
        self._run_count = 0
        self._error_count = 0
    
    @property
    def status(self) -> LoopStatus:
        return self._status
    
    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "name": self.config.name,
            "status": self._status.value,
            "interval": self.config.interval_seconds,
            "enabled": self.config.enabled,
            "max_errors": self.config.max_errors,
            "error_backoff": self.config.error_backoff,
            "last_run": self._last_run,
            "run_count": self._run_count,
            "error_count": self._error_count,
            "consecutive_errors": self._consecutive_errors,
        }
    
    def start(self) -> None:
        """Start the background loop."""
        if self._status == LoopStatus.RUNNING:
            return
        
        if not self.config.enabled:
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"loop-{self.config.name}",
            daemon=True
        )
        self._status = LoopStatus.RUNNING
        self._thread.start()
    
    def stop(self) -> None:
        """Stop the background loop gracefully."""
        if self._status != LoopStatus.RUNNING:
            return
        
        self._stop_event.set()
        self._status = LoopStatus.STOPPED
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
    
    def pause(self) -> None:
        """Pause the loop (keeps thread alive but skips tasks)."""
        if self._status == LoopStatus.RUNNING:
            self._status = LoopStatus.PAUSED
    
    def resume(self) -> None:
        """Resume a paused loop."""
        if self._status == LoopStatus.PAUSED:
            self._status = LoopStatus.RUNNING
    
    def _run_loop(self) -> None:
        """Main loop runner (runs on background thread)."""
        interval = self.config.interval_seconds
        
        while not self._stop_event.is_set():
            # Wait for interval or stop signal
            if self._stop_event.wait(timeout=interval):
                break
            
            # Skip if paused
            if self._status == LoopStatus.PAUSED:
                continue
            
            # Run the task
            try:
                self.task()
                self._last_run = datetime.now(timezone.utc).isoformat()
                self._run_count += 1
                self._consecutive_errors = 0
                interval = self.config.interval_seconds  # Reset interval
                
            except Exception as e:
                self._error_count += 1
                self._consecutive_errors += 1
                
                # Log error
                try:
                    from agent.threads.log import log_error
                    log_error(f"loop:{self.config.name}", e, context="background loop")
                except Exception:
                    pass
                
                # Apply backoff
                interval = min(
                    self.config.interval_seconds * (self.config.error_backoff ** self._consecutive_errors),
                    3600  # Cap at 1 hour
                )
                
                # Stop if too many errors
                if self._consecutive_errors >= self.config.max_errors:
                    self._status = LoopStatus.ERROR
                    break
