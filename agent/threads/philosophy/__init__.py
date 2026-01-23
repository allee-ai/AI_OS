"""Philosophy Thread - values, reasoning, and ethical bounds."""
from .adapter import PhilosophyThreadAdapter
from .api import router
from .schema import (
    get_philosophy_profile_types, create_philosophy_profile_type,
    get_philosophy_profiles, create_philosophy_profile, delete_philosophy_profile,
    pull_philosophy_profile_facts, push_philosophy_profile_fact, delete_philosophy_profile_fact,
)

__all__ = [
    "PhilosophyThreadAdapter",
    "router",
    "get_philosophy_profile_types",
    "create_philosophy_profile_type", 
    "get_philosophy_profiles",
    "create_philosophy_profile",
    "delete_philosophy_profile",
    "pull_philosophy_profile_facts",
    "push_philosophy_profile_fact",
    "delete_philosophy_profile_fact",
]
