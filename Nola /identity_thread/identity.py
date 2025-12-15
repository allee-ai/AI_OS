from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent import get_state, set_state
from utils import load_json, save_json
from contract import create_metadata, should_sync, mark_synced

IDENTITY_FILE = Path(__file__).parent / "identity.json"


def pull_identity() -> dict:
    """Pull the IdentityConfig section from Nola.json."""
    section = get_state().get("IdentityConfig", {})
    return section.get("data", section)  # Handle both old and new format


def get_identity_metadata() -> dict:
    """Get metadata for IdentityConfig section from Nola.json."""
    section = get_state().get("IdentityConfig", {})
    return section.get("metadata", {})


def sync_submodules() -> dict:
    """Check submodule metadata and sync if needed.
    
    Reads metadata from identity.json submodules (machineID, userID)
    and refreshes their data if they signal needs_sync or are stale.
    
    Returns:
        Aggregated data from all submodules
    """
    identity = load_json(IDENTITY_FILE)
    
    # Check machineID metadata
    machine_section = identity.get("machineID", {})
    machine_meta = machine_section.get("metadata", {})
    if should_sync(machine_meta):
        # Re-pull from machineID module
        from identity_thread.machineID.machineID import push_machine
        push_machine()
        identity = load_json(IDENTITY_FILE)  # Reload after push
        machine_section = identity.get("machineID", {})
    
    # Check userID metadata
    user_section = identity.get("userID", {})
    user_meta = user_section.get("metadata", {})
    if should_sync(user_meta):
        from identity_thread.userID.user import push_user
        push_user()
        identity = load_json(IDENTITY_FILE)  # Reload after push
        user_section = identity.get("userID", {})
    
    # Return aggregated data
    return {
        "machineID": machine_section.get("data", {}),
        "userID": user_section.get("data", {})
    }


def push_identity(identity_data: dict = None, context_level: int = 1) -> dict:  # type: ignore
    """Push identity to the IdentityConfig section in Nola.json.
    
    Args:
        identity_data: Data to push (syncs submodules if None)
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    If `identity_data` is None, syncs submodules first and aggregates their data.
    """
    if identity_data is None:
        # Aggregate from submodules (checks their metadata)
        identity_data = sync_submodules()
    
    # Create section with metadata
    identity_section = {
        "metadata": create_metadata(
            context_level=context_level,
            status="ready",
            needs_sync=False,
            source_file=str(IDENTITY_FILE)
        ),
        "data": identity_data
    }
    
    set_state("IdentityConfig", identity_section)
    return identity_data


def sync_for_stimuli(stimuli_type: str = "realtime") -> dict:
    """Sync identity optimized for stimuli type.
    
    HEA Stimuli Type → Context Level Mapping:
        "realtime" → L1 (~10 tokens): Quick responses, minimal context
        "conversational" → L2 (~50 tokens): Standard chat, moderate context
        "analytical" → L3 (~200 tokens): Deep analysis, full context
    
    Args:
        stimuli_type: "realtime", "conversational", or "analytical"
    
    Returns:
        Synced identity data (filtered to appropriate level)
    """
    # Map stimuli type to context level
    level_map = {
        "realtime": 1,       # L1: ~10 tokens - quick responses
        "conversational": 2, # L2: ~50 tokens - standard chat
        "analytical": 3      # L3: ~200 tokens - deep analysis
    }
    context_level = level_map.get(stimuli_type, 2)  # Default to L2
    
    # Sync submodules with the appropriate context level
    # This triggers push_machine() and push_user() with level filtering
    from identity_thread.machineID.machineID import push_machine
    from identity_thread.userID.user import push_user
    
    # Each push filters data to only include level_N and writes to identity.json
    machine_data = push_machine(context_level=context_level)
    user_data = push_user(context_level=context_level)
    
    # Aggregate the already-filtered data
    filtered_identity = {
        "machineID": machine_data,
        "userID": user_data
    }
    
    # Push aggregated filtered identity to Nola.json (pass data directly to avoid re-sync)
    return push_identity(identity_data=filtered_identity, context_level=context_level)
