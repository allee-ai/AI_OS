"""
Background Loop Base Classes
============================
Core abstractions for periodic background tasks.

Concurrency strategy:
- All loop tasks share a bounded ThreadPoolExecutor (_loop_pool)
  so heavy LLM / embedding work can't spawn unlimited threads.
- An Ollama semaphore (_ollama_gate) limits concurrent Ollama calls
  to 1 by default (env AIOS_OLLAMA_CONCURRENCY), preventing loops
  from starving the chat endpoint of inference capacity.
- Loop worker threads are niced +10 (best-effort) so the main
  uvicorn thread wins GIL / CPU contention.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum


# ── Process-wide resources shared by all BackgroundLoops ────

_POOL_SIZE = int(os.getenv("AIOS_LOOP_POOL_SIZE", "2"))
_loop_pool = ThreadPoolExecutor(
    max_workers=_POOL_SIZE,
    thread_name_prefix="loop-worker",
)

# Ollama semaphore: prevents multiple loops from calling Ollama at the
# same time (embedding + inference).  Chat requests bypass this gate
# because they go through agent_service directly.
_OLLAMA_CONCURRENCY = int(os.getenv("AIOS_OLLAMA_CONCURRENCY", "1"))
_ollama_gate = threading.Semaphore(_OLLAMA_CONCURRENCY)


def acquire_ollama_gate(timeout: float = 300.0) -> bool:
    """Acquire the Ollama semaphore (blocks until available or timeout)."""
    return _ollama_gate.acquire(timeout=timeout)


def release_ollama_gate() -> None:
    """Release the Ollama semaphore."""
    _ollama_gate.release()


def _nice_thread() -> None:
    """Best-effort: lower this thread's scheduling priority."""
    try:
        os.nice(10)
    except (OSError, AttributeError):
        pass  # Windows or permission denied — not critical


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
    context_aware: bool = False  # When True, loop injects orchestrator STATE into prompts
    initial_delay: float = 0.0  # Seconds to wait before first tick (stagger starts)


class BackgroundLoop:
    """
    Base class for background loops.
    
    Runs a task function periodically on a daemon thread.
    Heavy task work is dispatched to a bounded thread pool so at most
    AIOS_LOOP_POOL_SIZE (default 2) loops execute simultaneously.
    Handles error recovery, backoff, and graceful shutdown.
    """
    
    def __init__(self, config: LoopConfig, task: Callable[[], None]):
        self.config = config
        self.task = task
        self._status = LoopStatus.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._busy = threading.Event()   # set while a task is executing
        self._consecutive_errors = 0
        self._last_run: Optional[str] = None
        self._run_count = 0
        self._error_count = 0
        self._last_duration: Optional[float] = None  # seconds
        self._durations: list = []  # last N run durations for averaging

    @property
    def is_busy(self) -> bool:
        """True when the loop is currently executing a task."""
        return self._busy.is_set()

    def wait_idle(self, timeout: float = 120.0) -> bool:
        """Block until the current task (if any) finishes. Returns True if idle."""
        if not self._busy.is_set():
            return True
        # Spin-wait: _busy is cleared at the end of _execute_task
        deadline = __import__('time').time() + timeout
        while self._busy.is_set():
            remaining = deadline - __import__('time').time()
            if remaining <= 0:
                return False
            __import__('time').sleep(min(0.5, remaining))
        return True
    
    @property
    def status(self) -> LoopStatus:
        return self._status
    
    @property
    def stats(self) -> Dict[str, Any]:
        durations = self._durations
        return {
            "name": self.config.name,
            "status": self._status.value,
            "is_busy": self._busy.is_set(),
            "interval": self.config.interval_seconds,
            "initial_delay": self.config.initial_delay,
            "enabled": self.config.enabled,
            "context_aware": self.config.context_aware,
            "max_errors": self.config.max_errors,
            "error_backoff": self.config.error_backoff,
            "last_run": self._last_run,
            "run_count": self._run_count,
            "error_count": self._error_count,
            "consecutive_errors": self._consecutive_errors,
            "last_duration": round(self._last_duration, 2) if self._last_duration is not None else None,
            "avg_duration": round(sum(durations) / len(durations), 2) if durations else None,
            "min_duration": round(min(durations), 2) if durations else None,
            "max_duration": round(max(durations), 2) if durations else None,
        }

    def _get_state(self, query: str = "") -> str:
        """
        Fetch the orchestrator's STATE block for context-aware loops.

        Returns the full STATE (identity, philosophy, linking, log, etc.)
        when ``self.config.context_aware`` is True, otherwise returns "".
        """
        try:
            if not self.config.context_aware:
                return ""
        except AttributeError:
            return ""
        try:
            from agent.subconscious.orchestrator import build_state
            return build_state(query)
        except Exception as e:
            print(f"[{self.config.name}] Failed to get STATE: {e}")
            return ""
    
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
        """Main loop runner (runs on background thread).
        
        The timer lives here but actual task execution is dispatched to the
        shared thread pool so we never exceed AIOS_LOOP_POOL_SIZE concurrent
        heavy operations.

        initial_delay is measured from server start: the loop waits that long
        then fires immediately, then repeats every interval after that.
        """
        # Stagger startup: wait initial_delay, then fire immediately
        first_wait = self.config.initial_delay if self.config.initial_delay > 0 else self.config.interval_seconds
        if self._stop_event.wait(timeout=first_wait):
            return

        interval = self.config.interval_seconds
        
        while not self._stop_event.is_set():
            # Skip if paused
            if self._status == LoopStatus.PAUSED:
                if self._stop_event.wait(timeout=5.0):
                    break
                continue
            
            # Dispatch task to the bounded pool instead of running inline.
            # .result() blocks this timer thread until the pool worker
            # finishes, which is fine — each loop has its own timer thread,
            # and the pool bounds actual concurrency.
            try:
                future = _loop_pool.submit(self._execute_task)
                # Wait for completion but respect stop signal
                while not future.done():
                    if self._stop_event.wait(timeout=1.0):
                        future.cancel()
                        break
                if future.done() and not future.cancelled():
                    future.result()  # re-raise any exception
                    
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
                # Wait with backoff before retrying
                if self._stop_event.wait(timeout=interval):
                    break
                continue

            # Success — reset
            interval = self.config.interval_seconds

            # Wait for next interval (sleep AFTER execution)
            if self._stop_event.wait(timeout=interval):
                break

    def _execute_task(self) -> None:
        """Run the task on a pool worker thread (niced, with stats bookkeeping)."""
        _nice_thread()
        self._busy.set()
        t0 = time.monotonic()
        try:
            self.task()
            elapsed = time.monotonic() - t0
            self._last_duration = elapsed
            self._durations.append(elapsed)
            if len(self._durations) > 20:
                self._durations.pop(0)
            self._last_run = datetime.now(timezone.utc).isoformat()
            self._run_count += 1
            self._consecutive_errors = 0
        finally:
            self._busy.clear()
