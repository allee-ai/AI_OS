import threading

# Global lock for memory/DB writes
# We use RLock (Reentrant Lock) so that if a thread already holds the lock
# (e.g. inside a high-level transaction), it can acquire it again without deadlocking.
MEMORY_WRITE_LOCK = threading.RLock()
