"""Set a fuller identity for primary_user — protected, decay-immune.

Pronouns alone weren't the answer. Cade is a trans woman from America who
built AI_OS. The system should know that, and the rules section should read
like context about its origin, not a he/she correction.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import closing
from data.db import get_connection

# Facts that the rules-renderer will weave together. Each is its own row
# so the linking_core can score them independently and the user can
# edit any one without touching the others.
FACTS = [
    # Self
    ("identity",       "transgender woman",                    "name"),
    ("nationality",    "American",                             "location"),
    ("hometown",       "United States",                        "location"),

    # Creator relationship
    ("creator_of",     "AI_OS",                                "name"),
    ("relationship_to_machine",
                       "Nola's operator and creator. The voice this system speaks in is hers.",
                                                                "relationship"),

    # Cognitive shape — what shows up in the design
    ("cognitive_style",
                       "ADHD; pattern recognition as primary mode; builds external structure to hold what working memory can't.",
                                                                "note"),
    ("design_signature",
                       "Refuses 'AI as service'; insists on 'AI as partner'. Builds memory systems because she knows what it costs when memory fails.",
                                                                "note"),
]


with closing(get_connection()) as conn:
    cur = conn.cursor()
    for key, val, ftype in FACTS:
        cur.execute("""
            INSERT INTO profile_facts (profile_id, key, fact_type, l1_value, weight, protected, updated_at)
            VALUES ('primary_user', ?, ?, ?, 1.0, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, key) DO UPDATE SET
                l1_value = excluded.l1_value,
                fact_type = excluded.fact_type,
                weight = 1.0,
                protected = 1,
                updated_at = CURRENT_TIMESTAMP
        """, (key, ftype, val))
    conn.commit()

    print("primary_user — protected facts:")
    for r in cur.execute("""
        SELECT key, fact_type, l1_value, weight
        FROM profile_facts
        WHERE profile_id='primary_user' AND protected=1
        ORDER BY key
    """):
        v = r['l1_value'] or ''
        if len(v) > 70: v = v[:67] + '...'
        print(f"  {r['key']:25s} type={r['fact_type']:12s} = {v}")
