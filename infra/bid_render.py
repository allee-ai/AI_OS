"""Render a bid PDF from an instant-quote submission.

Pure function: takes the structured payload posted by the stepper, returns
PDF bytes. No I/O, no DB. The form server calls this and attaches the bytes
to an outbound email.

The DYLD_FALLBACK_LIBRARY_PATH for WeasyPrint native libs (pango, cairo) is
set inside this module on macOS so callers don't have to worry about it.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# WeasyPrint on macOS needs the Homebrew libraries on the dyld path.
if sys.platform == "darwin" and "/opt/homebrew/lib" not in os.environ.get(
    "DYLD_FALLBACK_LIBRARY_PATH", ""
):
    existing = os.environ.get("DYLD_FALLBACK_LIBRARY_PATH", "")
    os.environ["DYLD_FALLBACK_LIBRARY_PATH"] = (
        "/opt/homebrew/lib" + (":" + existing if existing else "")
    )

import jinja2
import yaml
import weasyprint  # noqa: E402  — must come after env var set


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workspace" / "vre-construction-src"


# --- helpers -----------------------------------------------------------------

PROPERTY_LABELS = {
    "home":         "Owner-occupied home",
    "rental":       "Rental property",
    "flip":         "Flip in progress",
    "walkthrough":  "Pre-purchase walkthrough",
}

INVESTOR_PROPS = {"rental", "flip"}


def classify_track(property_type: str) -> str:
    """Return 'investor' or 'homeowner' from the stepper's property field."""
    return "investor" if property_type in INVESTOR_PROPS else "homeowner"


def make_bid_id(client_email: str | None = None) -> str:
    """Generate a short, human-readable bid id like VRE-260514-A1B2."""
    import hashlib
    now = datetime.now(timezone.utc)
    seed = f"{now.isoformat()}|{client_email or ''}"
    h = hashlib.sha256(seed.encode()).hexdigest()[:4].upper()
    return f"VRE-{now.strftime('%y%m%d')}-{h}"


def _load_site() -> dict:
    return yaml.safe_load((SRC / "site.yaml").read_text())


def _group_items_by_category(items: list[dict]) -> list[dict]:
    """Take the flat items list from the payload, group by category, preserve order."""
    by_cat: dict[str, dict] = {}
    order: list[str] = []
    for it in items:
        cat = it.get("cat") or "Other"
        if cat not in by_cat:
            by_cat[cat] = {"label": cat, "items": []}
            order.append(cat)
        by_cat[cat]["items"].append({
            "label": it.get("label", it.get("id", "")),
            "qty":   int(it.get("qty", 0)),
            "low":   int(it.get("low", 0)),
            "high":  int(it.get("high", 0)),
        })
    return [by_cat[k] for k in order]


# --- main entrypoint ---------------------------------------------------------

def render_bid_pdf(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    """Render a bid PDF.

    Returns: (pdf_bytes, bid_id, track) where track is 'investor' or 'homeowner'.
    """
    site = _load_site()
    contact = payload.get("contact") or {}
    items = payload.get("items") or []
    mods = payload.get("mods") or []
    property_type = payload.get("property") or "home"
    track = classify_track(property_type)
    bid_id = make_bid_id(contact.get("email"))

    grouped = _group_items_by_category(items)

    items_low = sum(it["low"] * it["qty"] for cat in grouped for it in cat["items"])
    items_high = sum(it["high"] * it["qty"] for cat in grouped for it in cat["items"])

    total_low = int(payload.get("total_low") or 0) or items_low
    total_high = int(payload.get("total_high") or 0) or items_high
    total_mid = (total_low + total_high) // 2

    issued = datetime.now(timezone.utc).strftime("%B %-d, %Y")
    valid_until = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%B %-d, %Y")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(SRC / "templates"),
        autoescape=jinja2.select_autoescape(["html"]),
    )
    tmpl = env.get_template("bid.html.j2")
    html = tmpl.render(
        site=site,
        bid_id=bid_id,
        issued=issued,
        valid_until=valid_until,
        client=contact,
        property_label=PROPERTY_LABELS.get(property_type, property_type),
        track=track,
        grouped=grouped,
        items_low=items_low,
        items_high=items_high,
        mods=mods,
        total_low=total_low,
        total_high=total_high,
        total_mid=total_mid,
    )

    pdf_bytes = weasyprint.HTML(
        string=html,
        base_url=str(SRC / "templates"),
    ).write_pdf()
    return pdf_bytes, bid_id, track


# --- CLI smoke test ----------------------------------------------------------

if __name__ == "__main__":
    sample = {
        "site": "vre-construction.com",
        "property": "flip",
        "items": [
            {"id": "outlet_replace", "label": "Replace standard outlet",
             "cat": "Outlets & switches", "qty": 8, "low": 115, "high": 185},
            {"id": "switch_dimmer", "label": "Replace with LED-rated dimmer",
             "cat": "Outlets & switches", "qty": 4, "low": 155, "high": 235},
            {"id": "panel_200", "label": "200A panel replacement (same location)",
             "cat": "Panel & service upgrade", "qty": 1, "low": 2485, "high": 3785},
            {"id": "smoke_full", "label": "Full home retrofit (typical 3-bedroom)",
             "cat": "Smoke, CO & safety", "qty": 1, "low": 685, "high": 1485},
        ],
        "mods": [
            {"id": "plaster", "label": "Plaster & lath walls (pre-1940 home)", "pct": 25},
            {"id": "occupied", "label": "Tenants occupying during the work", "pct": 10},
        ],
        "total_low": 5360, "total_high": 9135,
        "contact": {
            "name": "Sample Investor",
            "email": "test@example.com",
            "phone": "(513) 555-0119",
            "address": "123 Northside Ave, Cincinnati OH 45223",
            "notes": "Closing in 12 days. Need this scoped firmly before then.",
        },
    }
    pdf, bid_id, track = render_bid_pdf(sample)
    out = ROOT / "tmp" / f"{bid_id}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pdf)
    print(f"wrote {out} ({len(pdf):,} bytes) — track={track}")
