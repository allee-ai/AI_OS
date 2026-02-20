"""
Identity Manager API endpoints.
Manages identity profile types, profiles, and identity facts.
Answers: "WHO am I? WHO are you?"
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import from local schema
from .schema import (
    get_profile_types, create_profile_type, delete_profile_type,
    get_profiles, create_profile, delete_profile,
    get_fact_types, create_fact_type,
    pull_profile_facts, push_profile_fact, delete_profile_fact, update_fact_weight
)

router = APIRouter(prefix="/api/identity", tags=["identity"])


# ============================================================================
# Models
# ============================================================================

class IdentityTypeCreate(BaseModel):
    type_name: str
    description: str = ""
    trust_level: int = 1
    context_priority: int = 2
    can_edit: bool = False


class IdentityProfileCreate(BaseModel):
    profile_id: str
    type_name: str
    display_name: str = ""


class IdentityFactCreate(BaseModel):
    profile_id: str
    key: str
    fact_type: str = "preference"
    l1_value: Optional[str] = None
    l2_value: Optional[str] = None
    l3_value: Optional[str] = None
    weight: Optional[float] = 0.5


class IdentityFactUpdate(BaseModel):
    fact_type: Optional[str] = None
    l1_value: Optional[str] = None
    l2_value: Optional[str] = None
    l3_value: Optional[str] = None
    weight: Optional[float] = None


class FactWeightUpdate(BaseModel):
    weight: float


# ============================================================================
# Identity Types (self, admin, family, friend, etc.)
# ============================================================================

@router.get("/types")
async def list_identity_types():
    """Get all identity profile types."""
    return get_profile_types()


@router.get("/fact-types")
async def list_identity_fact_types():
    """Get available fact types for identity profiles."""
    return get_fact_types()


@router.post("/types")
async def add_identity_type(data: IdentityTypeCreate):
    """Create or update an identity type."""
    create_profile_type(
        type_name=data.type_name,
        description=data.description,
        trust_level=data.trust_level,
        context_priority=data.context_priority,
        can_edit=data.can_edit
    )
    return {"status": "ok", "type_name": data.type_name}


@router.delete("/types/{type_name}")
async def remove_identity_type(type_name: str):
    """Delete an identity type (only if no profiles use it)."""
    success = delete_profile_type(type_name)
    if not success:
        raise HTTPException(400, "Cannot delete type with existing profiles")
    return {"status": "ok"}


# ============================================================================
# Identity Profiles
# ============================================================================

@router.get("")
async def list_identities(type_name: Optional[str] = None):
    """Get all identity profiles, optionally filtered by type."""
    return get_profiles(type_name)


@router.post("")
async def add_identity(data: IdentityProfileCreate):
    """Create or update an identity profile."""
    create_profile(
        profile_id=data.profile_id,
        type_name=data.type_name,
        display_name=data.display_name
    )
    return {"status": "ok", "profile_id": data.profile_id}


@router.delete("/{profile_id}")
async def remove_identity(profile_id: str):
    """Delete an identity profile and all its facts."""
    # Check if protected
    profiles = get_profiles()
    for p in profiles:
        if p.get("profile_id") == profile_id and p.get("protected"):
            raise HTTPException(403, "Cannot delete protected profile")
    
    success = delete_profile(profile_id)
    if not success:
        raise HTTPException(404, "Identity profile not found")
    return {"status": "ok"}


# ============================================================================
# Identity Facts (preferences, traits, knowledge)
# ============================================================================

@router.get("/{profile_id}/facts")
async def get_identity_facts(profile_id: str):
    """Get all identity facts for a profile."""
    return pull_profile_facts(profile_id=profile_id)


@router.post("/facts")
async def add_identity_fact(data: IdentityFactCreate):
    """Create or update an identity fact."""
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


@router.put("/{profile_id}/facts/{key}")
async def edit_identity_fact(profile_id: str, key: str, data: IdentityFactUpdate):
    """Edit an existing identity fact."""
    # Get existing fact to preserve values not being updated
    facts = pull_profile_facts(profile_id=profile_id)
    existing = next((f for f in facts if f.get("key") == key), None)
    
    if not existing:
        raise HTTPException(404, "Fact not found")
    
    # Merge existing with updates
    push_profile_fact(
        profile_id=profile_id,
        key=key,
        fact_type=data.fact_type if data.fact_type else existing.get("fact_type"),
        l1_value=data.l1_value if data.l1_value is not None else existing.get("l1_value"),
        l2_value=data.l2_value if data.l2_value is not None else existing.get("l2_value"),
        l3_value=data.l3_value if data.l3_value is not None else existing.get("l3_value"),
        weight=data.weight if data.weight is not None else existing.get("weight")
    )
    return {"status": "ok"}


@router.patch("/{profile_id}/facts/{key}/weight")
async def update_identity_fact_weight(profile_id: str, key: str, data: FactWeightUpdate):
    """Update the weight of a specific fact."""
    update_fact_weight(profile_id, key, data.weight)
    return {"status": "ok"}


@router.delete("/{profile_id}/facts/{key}")
async def remove_identity_fact(profile_id: str, key: str):
    """Delete an identity fact."""
    # Check if protected fact
    facts = pull_profile_facts(profile_id=profile_id)
    for f in facts:
        if f.get("key") == key and f.get("protected"):
            raise HTTPException(403, "Cannot delete protected fact key")
    
    success = delete_profile_fact(profile_id, key)
    if not success:
        raise HTTPException(404, "Fact not found")
    return {"status": "ok"}


# ============================================================================
# Introspection (Thread owns its state block)
# ============================================================================

@router.get("/introspect")
async def introspect_identity(level: int = 2, query: Optional[str] = None):
    """
    Get identity thread's contribution to STATE block.
    
    Each thread is responsible for building its own state.
    If query provided, filters to relevant facts via LinkingCore.
    """
    from .adapter import IdentityThreadAdapter
    adapter = IdentityThreadAdapter()
    result = adapter.introspect(context_level=level, query=query)
    return result.to_dict()


@router.get("/health")
async def get_identity_health():
    """Get identity thread health status."""
    from .adapter import IdentityThreadAdapter
    adapter = IdentityThreadAdapter()
    return adapter.health().to_dict()


@router.get("/table")
async def get_identity_table():
    """
    Get identity data in table format for UI display.
    
    Returns list of {key, type_name, l1, l2, l3, weight} matching old format.
    """
    rows = pull_profile_facts()
    # Transform to match expected frontend format
    table_rows = []
    for r in rows:
        table_rows.append({
            "key": r.get("key", ""),
            "metadata_type": r.get("type_name", "user"),
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


# ============================================================================
# Import Contacts (macOS)
# ============================================================================

@router.get("/import/preview")
async def preview_contacts_import(limit: int = 10):
    """
    Preview contacts from macOS Contacts.app before importing.
    
    Args:
        limit: Max contacts to preview (default 10)
    """
    try:
        from .import_contacts import preview_macos_contacts
        contacts = preview_macos_contacts(limit=limit)
        return {"contacts": contacts, "count": len(contacts)}
    except ImportError as e:
        raise HTTPException(501, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to preview contacts: {str(e)}")


@router.post("/import/contacts")
async def import_contacts(skip_existing: bool = True):
    """
    Import all contacts from macOS Contacts.app.
    
    Args:
        skip_existing: Skip contacts with matching profile names (default True)
    """
    try:
        from .import_contacts import import_all_macos_contacts
        result = import_all_macos_contacts(skip_existing=skip_existing)
        return result
    except ImportError as e:
        raise HTTPException(501, str(e))
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(500, f"Failed to import contacts: {str(e)}")
