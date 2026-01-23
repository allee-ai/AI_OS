"""Identity Thread - who am I, who are you."""
from .adapter import IdentityThreadAdapter
from .api import router
from .schema import (
    get_profile_types, create_profile_type, delete_profile_type,
    get_profiles, create_profile, delete_profile,
    get_fact_types, create_fact_type,
    pull_profile_facts, push_profile_fact, delete_profile_fact, update_fact_weight,
)


# =============================================================================
# Quick Accessors for Core Identity Values
# =============================================================================

def get_agent_name() -> str:
    """Get the agent's name. Used everywhere."""
    facts = pull_profile_facts(profile_id="self.agent")
    for f in facts:
        if f.get("key") == "name":
            return f.get("l1_value") or f.get("l2_value") or "Agent"
    return "Agent"


def get_agent_role() -> str:
    """Get the agent's role."""
    facts = pull_profile_facts(profile_id="self.agent")
    for f in facts:
        if f.get("key") == "role":
            return f.get("l1_value") or f.get("l2_value") or "assistant"
    return "assistant"


def get_user_name() -> str:
    """Get the primary user's name."""
    facts = pull_profile_facts(profile_id="user.primary")
    for f in facts:
        if f.get("key") == "name":
            return f.get("l1_value") or f.get("l2_value") or "User"
    return "User"


def get_core_identity() -> dict:
    """Get all core identity values as a dict."""
    return {
        "agent_name": get_agent_name(),
        "agent_role": get_agent_role(),
        "user_name": get_user_name(),
    }


__all__ = [
    "IdentityThreadAdapter",
    "router",
    "get_profile_types",
    "create_profile_type",
    "delete_profile_type",
    "get_profiles",
    "create_profile",
    "delete_profile",
    "get_fact_types",
    "create_fact_type",
    "pull_profile_facts",
    "push_profile_fact",
    "delete_profile_fact",
    "update_fact_weight",
    # Quick accessors
    "get_agent_name",
    "get_agent_role", 
    "get_user_name",
    "get_core_identity",
]
