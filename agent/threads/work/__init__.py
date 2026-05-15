"""
Work Thread — Sales & Operations Awareness
==========================================

Surfaces the live state of the work dashboard (jake-app, deployed on bycade)
into AI_OS STATE so the agent knows the funnel without being asked.

This thread does NOT own the data — work_dashboard does. It's a read-only
introspection layer that hits the live API and caches results so STATE
assembly stays cheap.

Facts surfaced:
  - work.leads.<status>: count
  - work.calls.today: N
  - work.packets.today: N
  - work.walkthroughs.today: N
  - work.wins.today: N
  - work.recent_lead.<n>: name (status) — for top-3 most recent
"""

from .adapter import WorkThreadAdapter

__all__ = ["WorkThreadAdapter"]
