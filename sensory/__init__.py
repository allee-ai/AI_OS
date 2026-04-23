"""sensory — uniform text-based sensory event bus. Exports router + init."""
from sensory.api import router
from sensory.schema import init_sensory_tables, record_event, get_recent_events
from sensory.salience import init_salience_tables
from sensory.consent import init_consent_tables, seed_consent_from_taxonomy

__all__ = [
    "router",
    "init_sensory_tables",
    "init_salience_tables",
    "init_consent_tables",
    "seed_consent_from_taxonomy",
    "record_event",
    "get_recent_events",
]
