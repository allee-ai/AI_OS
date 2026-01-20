"""
Philosophy Manager API endpoints.
Manages philosophy profile types, profiles, and philosophical stances/values.
Mirrors the identity profile system but for "WHY" instead of "WHO".
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import from local schema
from .schema import (
    get_philosophy_profile_types, create_philosophy_profile_type,
    get_philosophy_profiles, create_philosophy_profile, delete_philosophy_profile,
    pull_philosophy_profile_facts, push_philosophy_profile_fact, delete_philosophy_profile_fact
)

router = APIRouter(prefix="/api/philosophy", tags=["philosophy"])


# ============================================================================
# Models (same as profiles but for philosophy)
# ============================================================================

class PhilosophyTypeCreate(BaseModel):
    type_name: str
    description: str = ""
    priority: int = 5


class PhilosophyProfileCreate(BaseModel):
    profile_id: str
    type_name: str
    display_name: str = ""
    description: str = ""


class PhilosophyFactCreate(BaseModel):
    profile_id: str
    key: str
    fact_type: str = "stance"
    l1_value: Optional[str] = None
    l2_value: Optional[str] = None
    l3_value: Optional[str] = None
    weight: Optional[float] = 0.5


class FactWeightUpdate(BaseModel):
    weight: float


# ============================================================================
# Philosophy Types (value, ethic, constraint, principle, etc.)
# ============================================================================

@router.get("/types")
async def list_philosophy_types():
    """Get all philosophy profile types."""
    return get_philosophy_profile_types()


@router.get("/fact-types")
async def list_philosophy_fact_types():
    """Get available fact types for philosophy profiles."""
    return [
        {"type": "stance", "description": "A position or viewpoint on a topic"},
        {"type": "principle", "description": "A fundamental rule or belief"},
        {"type": "value", "description": "Something considered important or worthwhile"},
        {"type": "constraint", "description": "A limitation or boundary"},
        {"type": "preference", "description": "A favored choice or tendency"},
    ]


@router.post("/types")
async def add_philosophy_type(data: PhilosophyTypeCreate):
    """Create or update a philosophy type."""
    create_philosophy_profile_type(
        type_name=data.type_name,
        description=data.description,
        priority=data.priority
    )
    return {"status": "ok", "type_name": data.type_name}


# ============================================================================
# Philosophy Profiles
# ============================================================================

@router.get("")
async def list_philosophies(type_name: Optional[str] = None):
    """Get all philosophy profiles, optionally filtered by type."""
    return get_philosophy_profiles(type_name)


@router.post("")
async def add_philosophy(data: PhilosophyProfileCreate):
    """Create or update a philosophy profile."""
    create_philosophy_profile(
        profile_id=data.profile_id,
        type_name=data.type_name,
        display_name=data.display_name,
        description=data.description
    )
    return {"status": "ok", "profile_id": data.profile_id}


@router.delete("/{profile_id}")
async def remove_philosophy(profile_id: str):
    """Delete a philosophy profile and all its stances."""
    success = delete_philosophy_profile(profile_id)
    if not success:
        raise HTTPException(404, "Philosophy profile not found")
    return {"status": "ok"}


# ============================================================================
# Philosophy Facts (stances, values, principles)
# ============================================================================

@router.get("/{profile_id}/facts")
async def get_philosophy_facts(profile_id: str):
    """Get all philosophical stances/facts for a profile."""
    return pull_philosophy_profile_facts(profile_id=profile_id)


@router.post("/facts")
async def add_philosophy_fact(data: PhilosophyFactCreate):
    """Create or update a philosophical stance/fact."""
    push_philosophy_profile_fact(
        profile_id=data.profile_id,
        key=data.key,
        l1_value=data.l1_value,
        l2_value=data.l2_value,
        l3_value=data.l3_value,
        weight=data.weight
    )
    return {"status": "ok"}


@router.delete("/{profile_id}/facts/{key}")
async def remove_philosophy_fact(profile_id: str, key: str):
    """Delete a philosophical stance/fact."""
    success = delete_philosophy_profile_fact(profile_id, key)
    if not success:
        raise HTTPException(404, "Fact not found")
    return {"status": "ok"}


# ============================================================================
# Introspection (Thread owns its state block)
# ============================================================================

@router.get("/introspect")
async def introspect_philosophy(level: int = 2, query: Optional[str] = None):
    """
    Get philosophy thread's contribution to STATE block.
    
    Each thread is responsible for building its own state.
    If query provided, filters to relevant facts via LinkingCore.
    """
    from .adapter import PhilosophyThreadAdapter
    adapter = PhilosophyThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_philosophy_health():
    """Get philosophy thread health status."""
    from .adapter import PhilosophyThreadAdapter
    adapter = PhilosophyThreadAdapter()
    return adapter.health().to_dict()


@router.get("/table")
async def get_philosophy_table():
    """
    Get philosophy data in table format for UI display.
    
    Returns list of {key, type_name, l1, l2, l3, weight} matching old format.
    """
    rows = pull_philosophy_profile_facts()
    # Transform to match expected frontend format
    table_rows = []
    for r in rows:
        table_rows.append({
            "key": r.get("key", ""),
            "metadata_type": r.get("type_name", "value"),
            "metadata_desc": r.get("display_name", ""),
            "l1": r.get("l1_value", ""),
            "l2": r.get("l2_value", ""),
            "l3": r.get("l3_value", ""),
            "weight": r.get("weight", 0.5),
            "profile_id": r.get("profile_id", "")
        })
    return {
        "columns": ["key", "metadata_type", "metadata_desc", "l1", "l2", "l3", "weight"],
        "rows": table_rows,
        "row_count": len(table_rows)
    }
