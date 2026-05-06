"""Seed the Vanguard sales pipeline with real Cincinnati property managers.

Targets the niche: residential, ≤3-family, 513 area code. The giant multifamily
operators (Towne, Fath, CMC, PLK, Factory 52) are deliberately excluded — they
run their own in-house maintenance crews and don't subcontract small res. work.

Source: BBB Cincinnati property-management listings (verified phone+address).
Run from your Mac:
    .venv/bin/python scripts/seed_vanguard_leads.py

Idempotent — skips any lead whose contact_name already exists in the DB.
"""
import os
import sys
import json
import requests

API_BASE = "https://bycade.com"
ADMIN_USER = os.environ.get("VANGUARD_ADMIN_USER", "cade")
ADMIN_PASS = os.environ.get("VANGUARD_ADMIN_PASS", "peak2026!")

# ── The list ──────────────────────────────────────────────────────────────
# All phones verified from BBB Cincinnati 4/2026. Roles = best-guess from
# business profile. Notes give the salesperson an opening hook.
LEADS = [
    {
        "company_name": "B & L Company",
        "contact_name": "B&L office",
        "contact_role": "pm",
        "phone": "(513) 281-7170",
        "address": "4025 Paddock Rd Ste 100, Cincinnati, OH 45229",
        "neighborhoods": "Bond Hill / Avondale",
        "source": "BBB",
        "notes": "Mid-size local PM, BBB A+. Likely older portfolio = panel/wiring upgrade ammo. Ask who handles their electrical sub.",
    },
    {
        "company_name": "Uptown Rental Properties",
        "contact_name": "Uptown front desk",
        "contact_role": "pm",
        "phone": "(513) 861-9394",
        "address": "2718 Short Vine St, Cincinnati, OH 45219",
        "neighborhoods": "Clifton / UC / Uptown",
        "source": "BBB",
        "notes": "Student housing near UC — high turnover, lots of small fixes. Call between semesters. They also run One41 Wellington.",
    },
    {
        "company_name": "PMI Gatekeeper Realty",
        "contact_name": "PMI Gatekeeper",
        "contact_role": "pm",
        "phone": "(513) 389-0949",
        "address": "1172 W Galbraith Rd Ste 211, Cincinnati, OH 45231",
        "neighborhoods": "Finneytown / North College Hill",
        "source": "BBB",
        "notes": "PMI franchise — these usually focus on SFR + small multi. Strong fit for our 1-3 family niche. Section 8 angle works here.",
    },
    {
        "company_name": "Anchor Brothers Properties",
        "contact_name": "Anchor Brothers",
        "contact_role": "pm",
        "phone": "(513) 771-0124",
        "address": "7102 Gracely Dr Apt 1, Cincinnati, OH 45233",
        "neighborhoods": "Sayler Park / Westside",
        "source": "BBB",
        "notes": "Small westside operator. Lead with reliability — these guys hate waiting on electricians. Probably 1-3 fam stuff.",
    },
    {
        "company_name": "Rock Island Realty",
        "contact_name": "Rock Island",
        "contact_role": "pm",
        "phone": "(513) 952-9200",
        "address": "4014 Spring Grove Ave, Cincinnati, OH 45223",
        "neighborhoods": "Northside / Spring Grove",
        "source": "BBB",
        "notes": "Does remodeling + property mgmt — they SUB OUT electrical on jobs. Very hot lead. Ask for their GC or rehab manager.",
    },
    {
        "company_name": "Camden Management",
        "contact_name": "Camden office",
        "contact_role": "pm",
        "phone": "(513) 722-2441",
        "address": "3450 Kleybolte Ave, Cincinnati, OH 45226",
        "neighborhoods": "Mt Lookout / OTR (Sax Properties on W. McMicken)",
        "source": "BBB",
        "notes": "Owns properties in Mt Lookout AND OTR (W. McMicken). Mixed niche — older buildings, wiring issues likely.",
    },
    {
        "company_name": "Prestige Properties",
        "contact_name": "Prestige office",
        "contact_role": "pm",
        "phone": "(513) 861-9037",
        "address": "4415 Marburg Ave, Cincinnati, OH 45209",
        "neighborhoods": "Oakley / Hyde Park",
        "source": "BBB",
        "notes": "Oakley/Hyde Park area. Older homes = knob-and-tube, FPE/Zinsco risk. Lead with safety + insurance angle.",
    },
    {
        "company_name": "Majestic Properties",
        "contact_name": "Majestic office",
        "contact_role": "pm",
        "phone": "(513) 702-2508",
        "address": "PO Box 19391, Cincinnati, OH 45219",
        "neighborhoods": "Walnut Hills / Uptown",
        "source": "BBB",
        "notes": "Small operator — building contractors+rentals. Probably handles their own work but might overflow to subs.",
    },
    {
        "company_name": "Prosper Communities",
        "contact_name": "Prosper office",
        "contact_role": "pm",
        "phone": "(513) 940-0033",
        "address": "PO Box 8671, Cincinnati, OH 45208",
        "neighborhoods": "Hyde Park / East side",
        "source": "BBB",
        "notes": "BBB A. Smaller portfolio. Hyde Park area = older homes, panel upgrades likely.",
    },
    {
        "company_name": "HBC Facility Management",
        "contact_name": "HBC office",
        "contact_role": "pm",
        "phone": "(513) 397-5412",
        "address": "PO Box 780, Cincinnati, OH 45201",
        "neighborhoods": "Mixed / unknown specific",
        "source": "BBB",
        "notes": "Facility mgmt firm — may handle small res properties as side business. Cold lead, ask what they manage.",
    },
    {
        "company_name": "AJW Property Services",
        "contact_name": "AJW office",
        "contact_role": "pm",
        "phone": "(513) 766-9119",
        "address": "PO Box 128754, Cincinnati, OH 45212",
        "neighborhoods": "Norwood / Oakley",
        "source": "BBB",
        "notes": "Construction + property mgmt + remodeling = they sub electrical work out for sure. Position as the reliable sub they always wanted.",
    },
]


def login():
    r = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": ADMIN_USER, "password": ADMIN_PASS},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["token"]


def list_leads(token):
    r = requests.get(
        f"{API_BASE}/api/sales/leads",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def create_lead(token, lead):
    r = requests.post(
        f"{API_BASE}/api/sales/leads",
        json=lead,
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def main():
    print(f"Logging in to {API_BASE} as {ADMIN_USER}…")
    token = login()
    print("  ok\n")

    existing = list_leads(token)
    existing_companies = {(l.get("company_name") or "").lower() for l in existing}
    print(f"Existing leads: {len(existing)}\n")

    created = 0
    skipped = 0
    for lead in LEADS:
        if lead["company_name"].lower() in existing_companies:
            print(f"  SKIP  {lead['company_name']} (already exists)")
            skipped += 1
            continue
        try:
            res = create_lead(token, lead)
            print(f"  ADD   {lead['company_name']:35s}  id={res['id']}  {lead['phone']}")
            created += 1
        except requests.HTTPError as e:
            print(f"  FAIL  {lead['company_name']}: {e.response.status_code} {e.response.text[:100]}")

    print(f"\nDone. Created {created}, skipped {skipped}.")
    print(f"Salesperson opens https://bycade.com/sales — leads will be there.")


if __name__ == "__main__":
    main()
