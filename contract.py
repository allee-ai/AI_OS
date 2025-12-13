# contract.py - Metadata contract for inter-thread communication
"""
Defines the minimal protocol all modules must follow for state synchronization.

Metadata fields:
  - last_updated: ISO8601 timestamp of last write
  - context_level: Detail level (1=minimal, 2=moderate, 3=full)
  - status: "ready" | "updating" | "error" | "stale"
  - needs_sync: bool - signals parent thread to pull
  - source_file: path to raw data file
  - stale_threshold_seconds: max age before considered stale
"""

from datetime import datetime, timezone
from typing import Literal


def create_metadata(
    context_level: int = 1,
    status: Literal["ready", "updating", "error", "stale"] = "ready",
    needs_sync: bool = False,
    source_file: str = None,
    stale_threshold_seconds: int = 600,
    **kwargs
) -> dict:
    """Create a standard metadata dict with defaults.
    
    Args:
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
        status: Current state of the module
        needs_sync: Signal to parent that sync is needed
        source_file: Path to the raw data file
        stale_threshold_seconds: How long before data is considered stale
        **kwargs: Additional metadata fields
    
    Returns:
        Metadata dict following the contract
    """
    meta = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "context_level": context_level,
        "status": status,
        "needs_sync": needs_sync,
        "stale_threshold_seconds": stale_threshold_seconds,
    }
    if source_file:
        meta["source_file"] = source_file
    meta.update(kwargs)
    return meta


def is_stale(metadata: dict) -> bool:
    """Check if metadata indicates stale data.
    
    Args:
        metadata: Metadata dict to check
    
    Returns:
        True if data is stale (status="stale" or age > threshold)
    """
    if not metadata:
        return True
    
    if metadata.get("status") == "stale":
        return True
    
    last_updated = metadata.get("last_updated")
    threshold = metadata.get("stale_threshold_seconds", 600)
    
    if not last_updated:
        return True
    
    try:
        last_dt = datetime.fromisoformat(last_updated)
        # Handle naive datetime by assuming UTC
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - last_dt).total_seconds()
        return age > threshold
    except Exception:
        return True


def should_sync(metadata: dict) -> bool:
    """Check if metadata requests a sync.
    
    Args:
        metadata: Metadata dict to check
    
    Returns:
        True if needs_sync=True or data is stale
    """
    if not metadata:
        return True
    return metadata.get("needs_sync", False) or is_stale(metadata)


def mark_synced(metadata: dict) -> dict:
    """Update metadata to indicate successful sync.
    
    Args:
        metadata: Metadata dict to update
    
    Returns:
        Updated metadata with needs_sync=False and fresh timestamp
    """
    metadata = metadata.copy()
    metadata["last_updated"] = datetime.now(timezone.utc).isoformat()
    metadata["needs_sync"] = False
    metadata["status"] = "ready"
    return metadata


def request_sync(metadata: dict) -> dict:
    """Update metadata to signal sync is needed.
    
    Args:
        metadata: Metadata dict to update
    
    Returns:
        Updated metadata with needs_sync=True
    """
    metadata = metadata.copy()
    metadata["needs_sync"] = True
    return metadata
