from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import load_json, save_json
from contract import create_metadata, should_sync, mark_synced, request_sync

USER_FILE = Path(__file__).parent / "user.json"
IDENTITY_FILE = Path(__file__).parent.parent / "identity.json"


def extract_level_data(data: dict, level: int) -> dict:
    """Extract only the data for a specific context level.
    
    HEA Context Levels:
        L1 (~10 tokens): Minimal - just essentials for quick responses
        L2 (~50 tokens): Moderate - conversational context
        L3 (~200 tokens): Full - analytical depth
    
    Args:
        data: Full JSON data (may have nested level_1, level_2, level_3 keys)
        level: Context level (1, 2, or 3)
    
    Returns:
        Filtered dict containing only the requested level's data
    """
    level_key = f"level_{level}"
    result = {}
    
    for key, value in data.items():
        if isinstance(value, dict):
            # Check if this dict contains level keys
            if level_key in value:
                # Extract only the specified level
                result[key] = value[level_key]
            elif any(f"level_{i}" in value for i in [1, 2, 3]):
                # Has level structure but not our level - skip or use closest
                # Fallback: use level_1 if requested level not found
                fallback_key = f"level_{min(level, 3)}"
                while fallback_key not in value and level > 0:
                    level -= 1
                    fallback_key = f"level_{level}"
                result[key] = value.get(fallback_key, value.get("level_1", value))
            else:
                # Recurse into nested dicts
                result[key] = extract_level_data(value, level)
        else:
            # Non-dict values pass through (metadata, etc.)
            result[key] = value
    
    return result


def pull_user() -> dict:
    """Pull the userID section from parent identity.json."""
    section = load_json(IDENTITY_FILE).get("userID", {})
    return section.get("data", section)  # Handle both old and new format


def get_user_metadata() -> dict:
    """Get metadata for userID section."""
    section = load_json(IDENTITY_FILE).get("userID", {})
    return section.get("metadata", {})


def push_user(user_data: dict = None, context_level: int = 1) -> dict:  # type: ignore
    """Push user data to the userID section in parent identity.json.
    
    Args:
        user_data: Data to push (loads from user.json if None)
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    Updates the "userID" key in identity.json with metadata + data structure.
    Data is FILTERED to only include the specified context level.
    """
    if user_data is None:
        user_data = load_json(USER_FILE)
    
    # Extract only the data for the requested level (HEA filtering)
    filtered_data = extract_level_data(user_data, context_level)
    
    # Create section with metadata
    user_section = {
        "metadata": create_metadata(
            context_level=context_level,
            status="ready",
            needs_sync=False,
            source_file=str(USER_FILE)
        ),
        "data": filtered_data
    }
    
    identity_data = load_json(IDENTITY_FILE)
    identity_data["userID"] = user_section
    save_json(IDENTITY_FILE, identity_data)
    
    return filtered_data


def signal_sync_needed() -> None:
    """Signal to parent (identity.py) that userID needs to be synced."""
    identity_data = load_json(IDENTITY_FILE)
    section = identity_data.get("userID", {})
    metadata = section.get("metadata", {})
    
    section["metadata"] = request_sync(metadata) if metadata else create_metadata(needs_sync=True)
    identity_data["userID"] = section
    save_json(IDENTITY_FILE, identity_data)