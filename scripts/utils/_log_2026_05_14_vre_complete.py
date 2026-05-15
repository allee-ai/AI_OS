"""Log: contact form e2e working, marketing assets drafted, architecture lesson."""
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
        "system",
        "vre-construction.com contact form is LIVE end-to-end. POST to "
        "/contact-submit returns HTTP 303 -> ?sent=1. Architecture: "
        "Caddy (droplet) -> SSH reverse tunnel (Mac:8042 -> droplet:8042) -> "
        "Mac form-server (Proton Bridge via keychain) -> smtp.protonmail.ch:587. "
        "Routes vre-construction.com -> allee@allee-ai.com; "
        "vanguardrelocations.com -> assistant@allee-ai.com.",
        thread_subject="vre_construction_launch",
        tags=["deploy", "contact_form", "e2e", "live", "complete"],
    ))

    events.append(log_event(
        "system",
        "ARCHITECTURE LESSON 2026-05-14: DigitalOcean droplets block ALL "
        "outbound SMTP (25 and 587 both BLOCKED at DO network level, "
        "tested smtp.protonmail.ch and smtp.gmail.com). UFW shows inbound "
        "rules only — the block is upstream. Conclusion: any form-server "
        "or mail-sending service must run on the Mac (via Proton Bridge) "
        "and be reverse-tunneled to the droplet, OR switch to an HTTPS "
        "email API (Resend/Postmark/Mailgun). Today's choice: revert to "
        "Mac form-server + SSH tunnel architecture (was the original "
        "working setup before the droplet-side experiment).",
        thread_subject="infra_smtp_egress",
        tags=["infra", "smtp", "digitalocean", "lesson", "architecture",
              "form_server"],
    ))

    events.append(log_event(
        "system",
        "Stopped + disabled aios-form-server.service on droplet (port 8042 "
        "freed). Reloaded com.allee.form-tunnel.plist on Mac. Tunnel "
        "established: droplet curl http://127.0.0.1:8042/health returns "
        "200 with new routes. Caddy reverse_proxy /contact-submit "
        "127.0.0.1:8042 now reaches Mac form-server transparently.",
        thread_subject="form_server_tunnel",
        tags=["infra", "form_server", "tunnel", "config_change"],
    ))

    events.append(log_event(
        "system",
        "Drafted marketing assets for vre-construction.com (saved to "
        "workspace/vre-construction/marketing/, robots.txt-excluded): "
        "(1) google-business-profile.md - paste-ready GBP listing copy "
        "with categories, service area, descriptions, services, Q&A, "
        "weekly posts, photo shot list. "
        "(2) social-posts.md - Facebook/Nextdoor/Instagram/LinkedIn post "
        "drafts + 30-day posting cadence + per-channel UTM tracking. "
        "(3) email-templates.md - signature, cold outreach, quote "
        "follow-up, review/referral asks. "
        "(4) flyer.html - printable letter-size flyer for door-hangers / "
        "hardware-store bulletin boards. "
        "All include placeholder fields ([YOUR CELL], price bands, "
        "license #) that user must fill in before publishing.",
        thread_subject="vre_construction_marketing",
        tags=["marketing", "vre_construction", "deliverable", "drafts"],
    ))

    events.append(log_event(
        "system",
        "SEO basics live on vre-construction.com: robots.txt with sitemap "
        "ref + /sales/ /marketing/ disallows; sitemap.xml listing 3 pages; "
        "JSON-LD Electrician schema on index with full business metadata "
        "(name, areaServed, hours, services, address: Cincinnati OH); "
        "JSON-LD ContactPage on contact.html; OpenGraph + Twitter Card "
        "tags on all 3 pages.",
        thread_subject="vre_construction_seo",
        tags=["seo", "vre_construction", "complete"],
    ))

    # Close goal #71 by marking it completed (most sub-tasks shipped).
    with closing(get_connection()) as conn:
        cur = conn.execute(
            "SELECT id, status FROM proposed_goals WHERE id = 71"
        )
        row = cur.fetchone()
        if row and row["status"] != "completed":
            conn.execute(
                "UPDATE proposed_goals SET status = 'completed', "
                "resolved_at = CURRENT_TIMESTAMP, "
                "rationale = rationale || ' [Resolved 2026-05-14: site "
                "live HTTP/2 200, Lets Encrypt certs issued, SEO files "
                "deployed (robots.txt, sitemap.xml, JSON-LD Electrician + "
                "ContactPage schemas, OpenGraph), contact form e2e working "
                "(Caddy->tunnel->Mac form-server->Proton, returns 303 ?sent=1), "
                "marketing assets drafted (GBP, social, email, flyer). "
                "Pending user input: fill [YOUR CELL], price bands $[X]/$[Y], "
                "license #[NUMBER] across marketing/ and sales/. "
                "Discrepancy noted: site says <=4-unit, sales materials say "
                "<=3-family - user call which is correct.]' "
                "WHERE id = 71"
            )
            conn.commit()
            events.append(("goal_71_closed",))

    print(f"events: {events}")


if __name__ == "__main__":
    main()
