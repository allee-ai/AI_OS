"""
Profile Manager API endpoints.
Manages user-defined profile types, profiles, and facts.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import sys
from pathlib import Path

# Add threads to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "threads"))
from schema import (
    get_profile_types, create_profile_type, delete_profile_type,
    get_profiles, create_profile, delete_profile,
    get_fact_types, create_fact_type, delete_fact_type,
    pull_profile_facts, push_profile_fact, update_fact_weight, delete_profile_fact,
    delete_all_profile_facts, delete_all_profiles,
    migrate_identity_to_profiles
)

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


# ============================================================================
# Models
# ============================================================================

class ProfileTypeCreate(BaseModel):
    type_name: str
    trust_level: int = 1
    context_priority: int = 2
    can_edit: bool = False
    description: str = ""


class ProfileCreate(BaseModel):
    profile_id: str
    type_name: str
    display_name: str = ""


class FactTypeCreate(BaseModel):
    fact_type: str
    description: str = ""
    default_weight: float = 0.5


class FactCreate(BaseModel):
    profile_id: str
    key: str
    fact_type: str
    l1_value: Optional[str] = None
    l2_value: Optional[str] = None
    l3_value: Optional[str] = None
    weight: Optional[float] = None


class FactWeightUpdate(BaseModel):
    weight: float


# ============================================================================
# Profile Types
# ============================================================================

@router.get("/types")
async def list_profile_types():
    """Get all profile types."""
    return get_profile_types()


@router.post("/types")
async def add_profile_type(data: ProfileTypeCreate):
    """Create or update a profile type."""
    create_profile_type(
        type_name=data.type_name,
        trust_level=data.trust_level,
        context_priority=data.context_priority,
        can_edit=data.can_edit,
        description=data.description
    )
    return {"status": "ok", "type_name": data.type_name}


@router.delete("/types/{type_name}")
async def remove_profile_type(type_name: str):
    """Delete a profile type."""
    if not delete_profile_type(type_name):
        raise HTTPException(400, "Cannot delete type with existing profiles")
    return {"status": "ok"}


# ============================================================================
# Profiles
# ============================================================================

@router.get("")
async def list_profiles(type_name: Optional[str] = None):
    """Get all profiles, optionally filtered by type."""
    return get_profiles(type_name)


@router.post("")
async def add_profile(data: ProfileCreate):
    """Create or update a profile."""
    create_profile(
        profile_id=data.profile_id,
        type_name=data.type_name,
        display_name=data.display_name
    )
    return {"status": "ok", "profile_id": data.profile_id}


@router.delete("/{profile_id}")
async def remove_profile(profile_id: str):
    """Delete a profile and all its facts."""
    delete_profile(profile_id)
    return {"status": "ok"}


# ============================================================================
# Fact Types
# ============================================================================

@router.get("/fact-types")
async def list_fact_types():
    """Get all fact types."""
    return get_fact_types()


@router.post("/fact-types")
async def add_fact_type(data: FactTypeCreate):
    """Create or update a fact type."""
    create_fact_type(
        fact_type=data.fact_type,
        description=data.description,
        default_weight=data.default_weight
    )
    return {"status": "ok", "fact_type": data.fact_type}


@router.delete("/fact-types/{fact_type}")
async def remove_fact_type(fact_type: str):
    """Delete a fact type."""
    if not delete_fact_type(fact_type):
        raise HTTPException(400, "Cannot delete fact type in use")
    return {"status": "ok"}


# ============================================================================
# Profile Facts
# ============================================================================

@router.get("/{profile_id}/facts")
async def get_facts(profile_id: str, fact_type: Optional[str] = None):
    """Get all facts for a profile."""
    return pull_profile_facts(profile_id=profile_id, fact_type=fact_type)


@router.post("/facts")
async def add_fact(data: FactCreate):
    """Create or update a fact."""
    push_profile_fact(
        profile_id=data.profile_id,
        key=data.key,
        fact_type=data.fact_type,
        l1_value=data.l1_value,
        l2_value=data.l2_value,
        l3_value=data.l3_value,
        weight=data.weight
    )
    return {"status": "ok"}


@router.put("/{profile_id}/facts/{key}/weight")
async def set_fact_weight(profile_id: str, key: str, data: FactWeightUpdate):
    """Update a fact's weight."""
    update_fact_weight(profile_id, key, data.weight)
    return {"status": "ok"}


@router.delete("/{profile_id}/facts/{key}")
async def remove_fact(profile_id: str, key: str):
    """Delete a fact."""
    delete_profile_fact(profile_id, key)
    return {"status": "ok"}


# ============================================================================
# Bulk Operations
# ============================================================================

@router.delete("/all-facts")
async def remove_all_facts():
    """Delete ALL facts from all profiles."""
    count = delete_all_profile_facts()
    return {"status": "ok", "deleted": count}


@router.delete("/all-profiles")
async def remove_all_profiles():
    """Delete ALL profiles and their facts."""
    count = delete_all_profiles()
    return {"status": "ok", "deleted": count}


# ============================================================================
# Migration
# ============================================================================

@router.post("/migrate")
async def migrate_from_identity():
    """Migrate data from identity_flat to profile_facts."""
    count = migrate_identity_to_profiles()
    return {"status": "ok", "migrated": count}
