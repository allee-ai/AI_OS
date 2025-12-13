from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import load_json, save_json
from contract import create_metadata, should_sync, mark_synced, request_sync

USER_FILE = Path(__file__).parent / "user.json"
IDENTITY_FILE = Path(__file__).parent.parent / "identity.json"


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
    """
    if user_data is None:
        user_data = load_json(USER_FILE)
    
    # Create section with metadata
    user_section = {
        "metadata": create_metadata(
            context_level=context_level,
            status="ready",
            needs_sync=False,
            source_file=str(USER_FILE)
        ),
        "data": user_data
    }
    
    identity_data = load_json(IDENTITY_FILE)
    identity_data["userID"] = user_section
    save_json(IDENTITY_FILE, identity_data)
    
    return user_data


def signal_sync_needed() -> None:
    """Signal to parent (identity.py) that userID needs to be synced."""
    identity_data = load_json(IDENTITY_FILE)
    section = identity_data.get("userID", {})
    metadata = section.get("metadata", {})
    
    section["metadata"] = request_sync(metadata) if metadata else create_metadata(needs_sync=True)
    identity_data["userID"] = section
    save_json(IDENTITY_FILE, identity_data)