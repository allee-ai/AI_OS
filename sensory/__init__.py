"""sensory — uniform text-based sensory event bus. Exports router + init."""
from sensory.api import router
from sensory.schema import (
    init_sensory_tables,
    init_sensory_feeds_table,
    record_event,
    get_recent_events,
    register_feed,
    get_feeds,
    mark_feed_run,
    mark_feed_error,
    set_feed_enabled,
)
from sensory.salience import init_salience_tables
from sensory.consent import init_consent_tables, seed_consent_from_taxonomy

__all__ = [
    "router",
    "init_sensory_tables",
    "init_sensory_feeds_table",
    "init_salience_tables",
    "init_consent_tables",
    "seed_consent_from_taxonomy",
    "record_event",
    "get_recent_events",
    "register_feed",
    "get_feeds",
    "mark_feed_run",
    "mark_feed_error",
    "set_feed_enabled",
]
