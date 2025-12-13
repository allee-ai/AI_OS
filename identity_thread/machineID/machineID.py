from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils import load_json, save_json
from contract import create_metadata, should_sync, mark_synced, request_sync

MACHINE_FILE = Path(__file__).parent / "machineID.json"
IDENTITY_FILE = Path(__file__).parent.parent / "identity.json"


def pull_machine() -> dict:
    """Pull the machineID section from parent identity.json."""
    section = load_json(IDENTITY_FILE).get("machineID", {})
    return section.get("data", section)  # Handle both old and new format


def get_machine_metadata() -> dict:
    """Get metadata for machineID section."""
    section = load_json(IDENTITY_FILE).get("machineID", {})
    return section.get("metadata", {})


def push_machine(machine_data: dict = None, context_level: int = 1) -> dict:  # type: ignore
    """Push machine data to the machineID section in parent identity.json.
    
    Args:
        machine_data: Data to push (loads from machineID.json if None)
        context_level: Detail level (1=minimal, 2=moderate, 3=full)
    
    Updates the "machineID" key in identity.json with metadata + data structure.
    """
    if machine_data is None:
        machine_data = load_json(MACHINE_FILE)
    
    # Create section with metadata
    machine_section = {
        "metadata": create_metadata(
            context_level=context_level,
            status="ready",
            needs_sync=False,
            source_file=str(MACHINE_FILE)
        ),
        "data": machine_data
    }
    
    identity_data = load_json(IDENTITY_FILE)
    identity_data["machineID"] = machine_section
    save_json(IDENTITY_FILE, identity_data)
    
    return machine_data


def signal_sync_needed() -> None:
    """Signal to parent (identity.py) that machineID needs to be synced."""
    identity_data = load_json(IDENTITY_FILE)
    section = identity_data.get("machineID", {})
    metadata = section.get("metadata", {})
    
    section["metadata"] = request_sync(metadata) if metadata else create_metadata(needs_sync=True)
    identity_data["machineID"] = section
    save_json(IDENTITY_FILE, identity_data)
