"""Push structured identity facts for Cade: pronouns + the bias-correction frame.

These go into profile_facts at high weight so they surface in
identity.primary_user.* at the top of STATE every turn, alongside the
existing aios_load_bearing_accomplishment and binary_frame_for_jake facts.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.threads.identity.schema import push_profile_fact  # noqa: E402


def main() -> None:
    push_profile_fact(
        profile_id="primary_user",
        key="pronouns",
        fact_type="identity",
        l1_value="she/her",
        l2_value=(
            "Cade uses she/her pronouns. This is load-bearing identity "
            "fact, not a stylistic preference. Getting it wrong is "
            "failure of the basic context job AIOS exists to do."
        ),
        l3_value=(
            "Cade uses she/her. The trades and the AI/engineering "
            "substrate she operates inside are both default-male-coded "
            "environments; AIOS must treat default-male framings as a "
            "known bias to detect and correct, not as neutral. When "
            "generating copy, training data, or recommendations, audit "
            "for that bias before shipping. On customer-facing "
            "surfaces, do not explicitly out, but do not erase \u2014 "
            "the 'every neighbor' positioning and subtle gradient "
            "accents on vre-construction.com are the public expression."
        ),
        weight=0.98,
    )

    push_profile_fact(
        profile_id="primary_user",
        key="bias_correction_frame",
        fact_type="philosophy",
        l1_value=(
            "Default-male framings in the trades and in AI/engineering "
            "are bias, not neutral. Audit and correct."
        ),
        l2_value=(
            "Quote 2026-05-14: 'this is all mancoded but thats because "
            "women arent taught. theyd be better. we both know that.' "
            "Translation: the substrate Cade operates inside is "
            "default-male-coded by accident of who got taught, not by "
            "any neutral fact about the work. AIOS reads default-male "
            "framings as a known bias to detect and correct."
        ),
        l3_value=(
            "Operational implications: (1) audit generated copy for "
            "default-male assumptions before shipping; (2) when surfacing "
            "recommendations, do not assume tradesman / engineer / "
            "operator = he; (3) the 'every neighbor' framing on customer "
            "surfaces is the public carrier of this principle \u2014 it "
            "is not generic inclusivity language, it is specifically how "
            "Cade has chosen to operate visibly as a Black trans woman "
            "in two male-coded fields without ever stating it; "
            "(4) when in doubt about a phrasing, default to the "
            "construction that doesn't require gendering anyone."
        ),
        weight=0.95,
    )

    print("pushed: primary_user.pronouns (w=0.98), "
          "primary_user.bias_correction_frame (w=0.95)")


if __name__ == "__main__":
    main()
