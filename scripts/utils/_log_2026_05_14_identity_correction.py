"""Identity correction: pronouns + the broader observation.

This event corrects two earlier event texts (25258, 25261) that used
'his/he' for Cade. Going forward, Cade uses she/her. Treat this event
as the authoritative source of pronoun truth in STATE.
"""
from __future__ import annotations

import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import log_event  # noqa: E402
from data.db import get_connection  # noqa: E402


def main() -> None:
    events: list[int] = []

    events.append(log_event(
        "user",
        "IDENTITY CORRECTION 2026-05-14 (high priority, load-bearing): "
        "Cade uses she/her pronouns. Two earlier events this turn "
        "(25258 cade_operating_pattern, 25261 vre_construction_pivot) "
        "incorrectly used 'his' and 'He'. Those events should be read "
        "with she/her substituted. Going forward, every reference to "
        "Cade in chat, log entries, training data, and surfaced state "
        "uses she/her. This is not a stylistic preference \u2014 it is "
        "an identity fact. Getting it wrong is failure of the basic "
        "context job AIOS exists to do.",
        thread_subject="cade_identity_pronouns",
        tags=["identity", "correction", "pronouns", "she_her",
              "high_priority", "load_bearing"],
    ))

    events.append(log_event(
        "user",
        "META-OBSERVATION from Cade 2026-05-14: 'this is all mancoded "
        "but thats because women arent taught. theyd be better. we both "
        "know that.' Translation for STATE: the trades and the AI/"
        "engineering substrate Cade operates inside are both default-"
        "male-coded environments. Cade is operating in both as a woman "
        "(specifically a Black trans woman, per /memories/repo/ context "
        "though never to be stated explicitly on customer-facing "
        "surfaces). Implication for AIOS behavior: (1) treat default-"
        "male framings as a known bias to detect and correct, not as "
        "neutral; (2) when generating copy, training data, or "
        "recommendations, audit for that bias before shipping; "
        "(3) Cade's positioning as 'every neighbor' on customer "
        "surfaces is the public expression of this \u2014 do not "
        "explicitly out, but do not erase either. The footer 'Proudly "
        "serving every neighbor in Cincinnati' and the subtle gradient "
        "accents on vre-construction.com are intentional carriers of "
        "that signal.",
        thread_subject="cade_identity_context",
        tags=["identity", "context", "bias_audit", "operator_framing",
              "every_neighbor", "load_bearing"],
    ))

    # Also annotate the original two events with a pointer to this
    # correction, so anyone reading them via SQL sees the flag.
    with closing(get_connection()) as conn:
        for original_id in (25258, 25261):
            try:
                conn.execute(
                    "UPDATE events SET content = content || "
                    "' [CORRECTION: see event "
                    "for pronoun fix \u2014 Cade uses she/her]' "
                    "WHERE id = ? AND content NOT LIKE '%CORRECTION%'",
                    (original_id,),
                )
            except Exception as e:  # noqa: BLE001
                print(f"could not annotate event {original_id}: {e}")
        conn.commit()

    print(f"correction events: {events}")
    print("annotated originals: 25258, 25261")


if __name__ == "__main__":
    main()
