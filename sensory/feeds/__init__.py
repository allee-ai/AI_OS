"""sensory.feeds — workers that poll external sources and write to sensory_events.

Each worker exposes:
    poll_once(feed: dict) -> dict
        feed:   row from sensory.schema.get_feeds(); config in feed['config']
        return: {polled: int, recorded: int, error: str|None, cursor: str|None}

Workers are invoked by scripts/email_poll.py (and future cron triggers).
They never call set_consent themselves — consent is granted out-of-band
when the user enables the feed via scripts/sensory_feeds.py --enable.
"""
