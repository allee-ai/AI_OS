"""Populate the machine (Nola) profile with operating-environment facts.

User clarified: assistant@alleeai.com is Nola's email. The domain Cade
actually owns and uses is allee-ai.com (with dash) — Proton routes
EVERYTHING at that domain to alleeroden@pm.me via catch-all, so
`assistant@allee-ai.com` is functionally Nola's mailbox already.

Run idempotently: push_profile_fact UPSERTs.
"""
import platform
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.identity.schema import (  # noqa: E402
    create_profile,
    push_profile_fact,
)

# Make sure the profile's display_name reads "Nola" (not "Machine")
create_profile(profile_id="machine", type_name="machine", display_name="Nola")

py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
os_str = f"macOS {platform.mac_ver()[0]} ({platform.machine()})"

FACTS = [
    # key, fact_type, L1, L2, L3
    (
        "name", "name",
        "Nola",
        "Nola — the persistent AI on Cade's machine. Lives in /Users/cade/Desktop/AI_OS.",
        None,
    ),
    (
        "email", "email",
        "assistant@allee-ai.com",
        "assistant@allee-ai.com — routes via Proton catch-all on allee-ai.com to alleeroden@pm.me. "
        "Same Bridge endpoint (127.0.0.1:1143) used by sensory feed #3.",
        None,
    ),
    (
        "operator", "relationship",
        "Cade Roden (primary_user)",
        "Cade Roden built me. He's the only person whose memory I am protecting and ranking signal for.",
        None,
    ),
    (
        "organization", "organization",
        "allee-ai",
        "allee-ai is Cade's project / domain. AI_OS is the codebase.",
        None,
    ),
    (
        "role", "occupation",
        "Persistent local AI assistant",
        "Always-on companion. Reads sensory feeds, maintains identity/log/goals, runs reflex loops, "
        "talks via chat, executes tools through the form thread.",
        None,
    ),
    (
        "host", "location",
        "Cade's MacBook (localhost)",
        f"Runs locally at /Users/cade/Desktop/AI_OS. Mirrors to the AIOS host at /opt/aios. "
        f"Listens on 127.0.0.1; FastAPI server in scripts/server.py.",
        None,
    ),
    (
        "os", "os",
        os_str,
        f"{os_str}. Bridge IMAP feed expects macOS Keychain for credentials "
        "(service=AIOS-Proton-Bridge).",
        None,
    ),
    (
        "runtime", "note",
        f"Python {py_ver} in .venv",
        f"Local: .venv/bin/python (Python {py_ver}). Remote AIOS host: /opt/aios/.venv/bin/python. "
        "Never run inline multiline Python in the terminal — write a script.",
        None,
    ),
    (
        "datastore", "note",
        "SQLite WAL at data/db/state.db",
        "Source of truth for identity/log/goals/sensory/reflex/form/chat. Use `from data.db import "
        "get_connection`. WAL, foreign_keys, busy_timeout pre-set.",
        None,
    ),
    (
        "llm_routing", "note",
        "agent/services/llm.py — role-based",
        "Always call generate(prompt, role='ROLE'). Roles: CHAT, EXTRACT, SUMMARY, NAMING, GOAL, "
        "MEMORY, THOUGHT, PLANNER, EVOLVE, AUDIT, TRAINING, SELF_IMPROVE, CONCEPTS, REFLEX, FACT.",
        None,
    ),
    (
        "sensory_feeds", "note",
        "email/imap #3 'allee-ai' live",
        "Active: feed #3 allee-ai (Proton Bridge IMAP, every 5 min via reflex trigger #94). "
        "Bus: sensory_events. Drops: sensory_dropped. Consent gates per source/kind.",
        None,
    ),
    (
        "core_directive", "note",
        "Read the system before changing it. Change it so the next read is better.",
        None,
        None,
    ),
]

for key, ftype, l1, l2, l3 in FACTS:
    push_profile_fact(
        profile_id="machine",
        key=key,
        fact_type=ftype,
        l1_value=l1,
        l2_value=l2,
        l3_value=l3,
    )
    print(f"  set machine.{key} = {l1[:60]}")

print()
print(f"Set {len(FACTS)} machine facts. Profile display_name → 'Nola'.")
