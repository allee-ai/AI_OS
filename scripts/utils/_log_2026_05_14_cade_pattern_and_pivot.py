"""Log architectural insights about Cade's operating pattern + pending self-snapshot.

Three things to capture:
1. Jake-as-template insight (only the agent assistant knew this until now).
2. User is composing a self-snapshot letter to compare against STATE.
3. User has a business Facebook page that should connect to STATE as a feed.
4. Site pivot: from verbal/marketing voice to compendium-of-knowledge.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import log_event  # noqa: E402


def main() -> None:
    events: list[int] = []

    events.append(log_event(
        "system",
        "INSIGHT 2026-05-14: Jake / bid2 / jake-app is a TEMPLATE for how "
        "Cade operates, not an isolated relationship/project. The pattern: "
        "Cade scopes work for a specific operator with high-stakes "
        "real-world consequences (Jake = real-estate investor with deals "
        "in flight), delivers tooling/material under their constraints "
        "(timeline, vocabulary, communication style), and uses the "
        "engagement to surface his own working rhythms. Implication for "
        "STATE: when reading recent log/workspace events, treat "
        "Jake-shaped activity as Cade-operating-pattern data, not "
        "specifically about Jake. Other engagements (VRE Construction, "
        "Vanguard Relocations, future clients) inherit this template. "
        "Originally inferred and held implicitly by the agent assistant; "
        "logging explicitly so the pattern is in STATE for everyone "
        "(loops, future turns, user-facing introspection).",
        thread_subject="cade_operating_pattern",
        tags=["identity", "pattern", "jake", "template", "insight",
              "self_model"],
    ))

    events.append(log_event(
        "user",
        "User is composing a self-snapshot letter (handwritten / "
        "long-form) and intends to deliver it as a comparison artifact "
        "against STATE. Plan: read the letter, diff against what "
        "identity.primary_user.* / chat.recent / phil:* currently say, "
        "surface gaps and miscalibrations, propose adapter changes where "
        "STATE is missing facts the letter contains. This is a deliberate "
        "calibration pass on the self-model. Treat the letter as "
        "ground-truth source-of-record for identity facts when it "
        "arrives.",
        thread_subject="self_snapshot_pending",
        tags=["identity", "calibration", "snapshot", "user_input_pending",
              "ground_truth"],
    ))

    events.append(log_event(
        "user",
        "User has a business Facebook page (Vanguard Reconstruction). "
        "Should be wired into STATE as a feed source so social activity, "
        "messages, and reviews flow through the same score \u2192 level "
        "\u2192 threshold pipeline as everything else. Future thread/"
        "adapter task: feeds.facebook_business adapter that "
        "introspect()s recent posts, message count, review count, and "
        "scores them into STATE. Today is not the day to build it; "
        "logging as a backlog item.",
        thread_subject="feeds_facebook_business",
        tags=["feeds", "facebook", "backlog", "adapter", "integration",
              "vre_construction"],
    ))

    events.append(log_event(
        "user",
        "Direction shift on vre-construction.com: Cade does NOT want the "
        "site to be a verbal/marketing-voice surface. He wants it to be "
        "a COMPENDIUM OF KNOWLEDGE. Goal: every section is independently "
        "copy-paste-able across channels (Facebook posts, Nextdoor "
        "replies, cold-email answers, GBP Q&A). The site is the "
        "single source of truth; social platforms are syndication "
        "endpoints. Crew: 4 people total (Cade running shop, manager, "
        "two electricians). Nobody is licensed \u2014 site language "
        "removed all 'licensed/insured/inspector-ready' claims. "
        "Implemented: new /knowledge.html with 10-section reference "
        "(panel sizing, EV chargers, breaker trips, knob-and-tube, GFCI/"
        "AFCI, photos for quoting, pre-purchase walkthrough, price "
        "ranges, questions to ask any contractor, when to flip the "
        "main). Nav updated across all pages. Sitemap updated. "
        "FAQPage JSON-LD added to knowledge page.",
        thread_subject="vre_construction_pivot",
        tags=["vre_construction", "site", "compendium", "knowledge",
              "copy_paste_first", "direction_change", "no_license_claim"],
    ))

    print(f"events: {events}")


if __name__ == "__main__":
    main()
