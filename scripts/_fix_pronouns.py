"""Set pronouns/gender on primary_user as protected facts. Also remove the
mistakenly-set machine pronouns (Nola is a system, not gendered)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from contextlib import closing
from data.db import get_connection

with closing(get_connection()) as conn:
    cur = conn.cursor()

    # Put pronouns/gender on the USER, protected.
    for key, val in [("pronouns", "she/her"), ("gender", "female")]:
        cur.execute("""
            INSERT INTO profile_facts (profile_id, key, fact_type, l1_value, weight, protected, updated_at)
            VALUES ('primary_user', ?, 'name', ?, 1.0, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(profile_id, key) DO UPDATE SET
                l1_value = excluded.l1_value,
                weight = 1.0,
                protected = 1,
                fact_type = 'name',
                updated_at = CURRENT_TIMESTAMP
        """, (key, val))

    # Remove the mistaken machine pronouns. Nola is a system, not a person.
    cur.execute("DELETE FROM profile_facts WHERE profile_id='machine' AND key IN ('pronouns','gender')")

    # While we're here, lock down the rest of primary_user's curated identity
    # facts so they can't decay.
    cur.execute("""
        UPDATE profile_facts
        SET protected = 1
        WHERE profile_id = 'primary_user'
          AND key IN ('name','occupation','birthday','pronouns','gender')
    """)

    conn.commit()

    print("primary_user identity facts (protected):")
    for r in cur.execute("""
        SELECT key, fact_type, l1_value, weight, protected
        FROM profile_facts
        WHERE profile_id='primary_user' AND protected=1
        ORDER BY key
    """):
        print(f"  primary_user.{r['key']:12s} = {r['l1_value']!r:35s} w={r['weight']} p={r['protected']}")

    print()
    print("machine facts (after cleanup):")
    for r in cur.execute("""
        SELECT key, l1_value, weight, protected
        FROM profile_facts
        WHERE profile_id='machine' AND key IN ('pronouns','gender','name')
    """):
        print(f"  machine.{r['key']:10s} = {r['l1_value']!r}")
