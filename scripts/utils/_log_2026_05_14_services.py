"""One-shot: log service-restart + rename + focus into STATE.

Captures:
  - both droplets restarted + health verified
  - rename: 'jake app' -> 'business dashboard' (per-team dashboards future,
    all stream into AI_OS)
  - actual domains: vre-construction.com (registered 2026-05-14, expires 2027)
    and vanguardrelocations.com (expires 2027-03-03). Both at Namecheap.
  - DNS still points at Namecheap parking (162.255.119.x). Needs A record
    update to AIOS droplet 24.144.115.72 + matching Caddyfile blocks.
  - prior codebase refs 'vanguard-reconstruction.com' and
    'vanguard-relocations.com' -- those names do NOT exist in DNS. Rename
    needed across infra/, workspace/, sales docs before 5pm.
  - today's focus: vre-construction site live + marketing done by 5pm
  - local form-server + form-tunnel launchd jobs obsolete (droplet runs
    its own form-server on 8042; tunnel can never bind).
"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.threads.log.schema import log_event  # noqa: E402
from agent.subconscious.loops.goals import propose_goal  # noqa: E402


ids = []

ids.append(log_event(
    "system",
    "Restarted AIOS droplet (hostname=Nola) caddy + jake droplet jake-app "
    "uvicorn. Health: bycade.com 200, allee-ai.com 200, local form-server "
    "/health 200. Both droplets had been off; user powered on (uptime ~3m).",
    metadata={
        "aios_droplet": {"ip": "24.144.115.72", "hostname": "Nola",
                          "ssh_alias": "AIOS",
                          "services": {"caddy": "active",
                                        "form_server": "active (port 8042)"}},
        "jake_droplet": {"ip": "159.223.195.100",
                          "hostname": "ubuntu-s-1vcpu-1gb-sfo3-01",
                          "services": {"jake-app": "active",
                                        "nginx": "active",
                                        "postgres": "active"},
                          "internal_port": 8348,
                          "public": "https://bycade.com"},
        "form_server_local": {"port": 8042, "health": "ok",
                                "obsolete": True,
                                "reason": "droplet runs its own form-server now"},
        "form_tunnel_local": {"status": "broken-by-design",
                               "error": "remote port forwarding failed for 8042",
                               "reason": "droplet already binds 8042"},
    },
    source="user",
    thread_subject="infra_health",
    tags=["restart", "droplet", "health", "infra", "form_server"],
))

ids.append(log_event(
    "user_action",
    "Rename: 'jake app' -> 'business dashboard'. Located at "
    "/Users/cade/Desktop/desktop 2/bid2/jake-app. Plan: expand to one "
    "dashboard per team; all feed into AI_OS as upstream data source. "
    "Repo path + systemd unit (jake-app) + db name (jake_app) unchanged for "
    "now -- conceptual rename only. Public URL bycade.com unchanged.",
    metadata={
        "old_name": "jake app",
        "new_name": "business dashboard",
        "repo_path": "/Users/cade/Desktop/desktop 2/bid2/jake-app",
        "droplet_path": "/opt/jake-app",
        "systemd_unit": "jake-app",
        "db_name": "jake_app",
        "public_url": "https://bycade.com",
        "future_architecture": "per-team dashboards feeding AI_OS",
        "scope": "name only; do not rename paths/units without separate goal",
    },
    source="user",
    thread_subject="business_dashboard",
    tags=["rename", "business_dashboard", "jake_app", "architecture", "aios_feed"],
))

ids.append(log_event(
    "user_action",
    "Domain reality check (2026-05-14): the registered domains are "
    "vre-construction.com (expires 2027-05-14) and vanguardrelocations.com "
    "(expires 2027-03-03), both at Namecheap. The codebase uses the WRONG "
    "names everywhere (vanguard-reconstruction.com, vanguard-relocations.com "
    "-- 'No match' in whois). DNS A records still point at Namecheap parking "
    "(162.255.119.231 / .246), not the AIOS droplet 24.144.115.72. User has "
    "Namecheap settings to update.",
    metadata={
        "domains_real": {
            "vre-construction.com": {
                "registrar": "Namecheap",
                "expires": "2027-05-14",
                "current_a": "162.255.119.246",
                "target_a": "24.144.115.72",
                "purpose": "reconstruction website",
            },
            "vanguardrelocations.com": {
                "registrar": "Namecheap",
                "expires": "2027-03-03",
                "current_a": "162.255.119.231",
                "target_a": "24.144.115.72",
                "purpose": "relocations site",
            },
        },
        "wrong_names_in_codebase": [
            "vanguard-reconstruction.com",
            "vanguard-relocations.com",
        ],
        "occurrences_to_fix": "~30 across infra/, workspace/, sales/",
        "pending_user_actions": [
            "Update Namecheap A records to 24.144.115.72",
            "(then) rename strings across codebase + Caddyfile blocks",
        ],
    },
    source="user",
    thread_subject="vre_construction_launch",
    tags=["domain", "dns", "namecheap", "rename", "blocker"],
))

ids.append(log_event(
    "user_action",
    "Today's focus (by 5pm 2026-05-14): vre-construction.com website live "
    "+ marketing assets done. Critical path: (1) Namecheap A records -> "
    "24.144.115.72; (2) rename codebase 'vanguard-reconstruction' -> "
    "'vre-construction' and 'vanguard-relocations' -> 'vanguardrelocations' "
    "in infra/form_server*.py, Caddyfile blocks, workspace HTML canonicals, "
    "sales/investor-onepager.md, contact form email; (3) deploy site to "
    "AIOS droplet via Caddy; (4) verify TLS issuance.",
    metadata={
        "deadline": "2026-05-14T17:00:00",
        "domains_to_use": ["vre-construction.com", "vanguardrelocations.com"],
        "critical_path": [
            "Namecheap A record update",
            "Codebase rename",
            "Caddyfile blocks on AIOS droplet",
            "Site deploy",
            "TLS cert (Caddy auto)",
            "Marketing assets finalized",
        ],
    },
    source="user",
    thread_subject="vre_construction_launch",
    tags=["focus", "today", "5pm", "vre", "reconstruction"],
))

gid_rename = propose_goal(
    goal=(
        "Codebase domain rename: 'vanguard-reconstruction.com' -> "
        "'vre-construction.com' and 'vanguard-relocations.com' -> "
        "'vanguardrelocations.com'. ~30 occurrences across infra/form_server.py, "
        "infra/form_server_droplet.py, infra/_patch_caddy_contact.py, "
        "infra/RUNBOOK_*.md, workspace/vanguard-reconstruction/*.html "
        "(canonical URLs + contact form action + mailto), "
        "workspace/vanguard-reconstruction/sales/investor-onepager.md. "
        "Block for 5pm site launch."
    ),
    rationale=(
        "Whois confirms the codebase is using non-existent domain names. "
        "Actual registrations at Namecheap are vre-construction.com and "
        "vanguardrelocations.com. Without rename, form-server route map, "
        "Caddy server_name, and HTML canonicals all break."
    ),
    priority="high",
    sources=["live-conversation", "infra-health-check", "whois-verification"],
)
ids.append(("goal", gid_rename))

gid_dns = propose_goal(
    goal=(
        "Update Namecheap DNS for vre-construction.com and "
        "vanguardrelocations.com: change A record from parking IPs "
        "(162.255.119.246 / .231) to AIOS droplet 24.144.115.72. Add www "
        "CNAME or matching A. Required for Caddy to issue TLS and serve "
        "the reconstruction site by 5pm 2026-05-14."
    ),
    rationale=(
        "Both domains are registered at Namecheap but still on parking "
        "nameservers' default A records. Until DNS points at the droplet, "
        "no traffic reaches Caddy, no TLS cert can be issued, and the 5pm "
        "site-live goal is blocked."
    ),
    priority="high",
    sources=["live-conversation", "dns-check"],
)
ids.append(("goal", gid_dns))

print(f"logged events + goals: {ids}")
