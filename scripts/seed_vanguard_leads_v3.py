"""Round-3 seed: large apartment portfolios + flippers + suburban PMs.

Towne / CMC / Fath alone manage thousands of doors in Cincy. Cash-buyer
flippers do 5-20 SFR rehabs/year apiece — every rehab needs electrical.

All BBB-verified. Idempotent.
"""
import os
import requests

API_BASE = "https://bycade.com"
ADMIN_USER = os.environ.get("VANGUARD_ADMIN_USER", "cade")
ADMIN_PASS = os.environ.get("VANGUARD_ADMIN_PASS", "peak2026!")

LEADS = [
    # ── Big apartment / multi-property managers (NOTE: above 3-fam rule, but
    #    they ALSO carry mixed-portfolio small res holdings + serve as 
    #    introducer to investor-owners they manage for) ──────────────────
    {"company_name": "Towne Properties", "contact_name": "Towne Properties dispatch", "contact_role": "pm", "phone": "(513) 381-8696", "address": "Multi-location HQ, Cincinnati, OH", "source": "BBB-PM", "notes": "MASSIVE — manages thousands of units across Cincy/W Chester/Fairfield + home-builders division. Long shot for SFR work but great for referrals to their owner-investors. Call HQ, ask for vendor coordinator."},
    {"company_name": "CMC Properties", "contact_name": "CMC vendor coordinator", "contact_role": "pm", "phone": "(513) 792-1248", "address": "11120 Luschek Dr, Blue Ash, OH 45241", "source": "BBB-PM", "notes": "Big apartment + office portfolio Blue Ash/Springdale. Apartments need constant fixture/breaker work."},
    {"company_name": "Fath Properties", "contact_name": "Fath maintenance", "contact_role": "pm", "phone": "(513) 721-4070", "address": "3569 Nantucket Dr, Loveland, OH 45140", "source": "BBB-PM", "notes": "Major apartment portfolio. Loveland-based but operates across Cincy."},
    {"company_name": "Lakefront Communities", "contact_name": "Lakefront/Mallard/Latitude office", "contact_role": "pm", "phone": "(513) 561-5080", "address": "4637 Wyndtree Dr, West Chester, OH 45069", "source": "BBB-PM", "notes": "Manages Lakefront at West Chester + Mallard Lakes Townhomes (Cincy 45246) + Latitude at Deerfield Crossing (Mason). Multi-property apartment operator."},
    {"company_name": "Nelson & Associates", "contact_name": "Nelson & Associates", "contact_role": "pm", "phone": "(513) 961-6011", "address": "5325 Deerfield Blvd Ste 142, Mason, OH 45040", "source": "BBB-PM", "notes": "Small Mason PM. Ideal niche size."},
    {"company_name": "Culmen Real Estate Services", "contact_name": "Culmen office", "contact_role": "pm", "phone": "(937) 956-7811", "address": "9349 Waterstone Blvd Ste 105, Cincinnati, OH 45249", "source": "BBB-PM", "notes": "Symmes/Mason. PM + RE Services."},
    {"company_name": "Associa Cincinnati", "contact_name": "Associa Mason office", "contact_role": "pm", "phone": "(877) 277-6242", "address": "5412 Courseview Dr, Mason, OH 45040", "source": "BBB-PM", "notes": "National HOA/condo mgmt powerhouse — Mason regional office. Condos = electrical scope (common-area panels, exterior lighting). Long sales cycle but big."},

    # ── Real Estate Investing / Cash Buyers / Flippers ─────────────────────
    {"company_name": "Cincy Sell for Cash", "contact_name": "Cincy Sell for Cash", "contact_role": "investor", "phone": "(513) 654-1331", "address": "2692 Madison Rd Ste N1 PMB 342, Cincinnati, OH 45208", "source": "BBB-INV", "notes": "Cash buyer / flipper. They acquire distressed homes and rehab — every rehab = panel upgrade + circuit work. Repeat customer profile."},
    {"company_name": "Lohmiller Real Estate", "contact_name": "Lohmiller", "contact_role": "investor", "phone": "(513) 371-5468", "address": "3654 Edwards Rd, Cincinnati, OH 45208", "source": "BBB-INV", "notes": "Hyde Park RE broker + investor. Mixed res deals."},
    {"company_name": "Eighteen Homes", "contact_name": "Eighteen Homes", "contact_role": "investor", "phone": "(513) 513-2280", "address": "6724 Roe St, Cincinnati, OH 45227", "source": "BBB-INV", "notes": "Mariemont/Madisonville flipper."},
    {"company_name": "HomeDeal Property Buyers", "contact_name": "HomeDeal", "contact_role": "investor", "phone": "(513) 875-1554", "address": "1455 Dalton Ave Ste 2, Cincinnati, OH 45214", "source": "BBB-INV", "notes": "Camp Washington-based cash buyer. They flip 10-30/yr."},
    {"company_name": "Hunn Homes", "contact_name": "Hunn Homes", "contact_role": "investor", "phone": "(513) 237-5229", "address": "Cincinnati, OH 45231", "source": "BBB-INV", "notes": "Construction Services + Lawn + Bath Remodel = full-service flipper. North side."},
    {"company_name": "HomeVestors - We Buy Ugly Houses", "contact_name": "HomeVestors Cincy franchisee", "contact_role": "investor", "phone": "(513) 236-3418", "address": "Cincinnati, OH 45208", "source": "BBB-INV", "notes": "National franchise flipper, local Cincy operator. Their whole business is buying old houses + rehabbing — knob-and-tube, ungrounded outlets, panel upgrades on every job."},
    {"company_name": "Burnett Home Buyers", "contact_name": "Burnett", "contact_role": "investor", "phone": "(513) 802-9870", "address": "3874 Paxton Ave, Cincinnati, OH 45209", "source": "BBB-INV", "notes": "Hyde Park / Oakley flipper."},
    {"company_name": "Rapid Fire Home Buyers", "contact_name": "Rapid Fire", "contact_role": "investor", "phone": "(513) 440-3549", "address": "133 W 4th St, Cincinnati, OH 45202", "source": "BBB-INV", "notes": "Downtown-based flipper. Higher volume implied by name."},
    {"company_name": "7th Capital Home Buyers", "contact_name": "7th Capital", "contact_role": "investor", "phone": "(513) 966-4340", "address": "105 E 4th St #1400, Cincinnati, OH 45202", "source": "BBB-INV", "notes": "Downtown investor + house flipping. Class-A office address = institutional-leaning."},
    {"company_name": "The Kind Home Buyer", "contact_name": "The Kind Home Buyer", "contact_role": "investor", "phone": "(513) 951-8663", "address": "311 Elm St Ste 280, Cincinnati, OH 45202", "source": "BBB-INV", "notes": "Downtown flipper."},
    {"company_name": "Touch2Finish", "contact_name": "Touch2Finish", "contact_role": "investor", "phone": "(513) 371-4288", "address": "250 E 5th St Fl 15, Cincinnati, OH 45202", "source": "BBB-INV", "notes": "RE Investing + Construction Services = they flip AND build. Direct sub-out customer."},

    # Plus 1 from extra round
    {"company_name": "Bishops Gate Apartments / Towne", "contact_name": "Bishops Gate office", "contact_role": "pm", "phone": "(513) 489-3575", "address": "8075 Somerset Chase, Cincinnati, OH 45249", "source": "BBB-PM", "notes": "Towne Properties property — Symmes apartments. Good direct line to onsite mgr."},
]


def login():
    r = requests.post(f"{API_BASE}/api/auth/login",
                      json={"username": ADMIN_USER, "password": ADMIN_PASS}, timeout=10)
    r.raise_for_status()
    return r.json()["token"]


def list_leads(token):
    r = requests.get(f"{API_BASE}/api/sales/leads",
                     headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    return r.json()


def create_lead(token, lead):
    r = requests.post(f"{API_BASE}/api/sales/leads", json=lead,
                      headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    return r.json()


def main():
    print(f"Logging in as {ADMIN_USER}…")
    token = login()
    print("  ok")

    existing = list_leads(token)
    existing_companies = {(l.get("company_name") or "").lower() for l in existing}
    print(f"Existing leads: {len(existing)}\n")

    created = skipped = failed = 0
    for lead in LEADS:
        if lead["company_name"].lower() in existing_companies:
            skipped += 1
            continue
        try:
            res = create_lead(token, lead)
            print(f"  ADD  id={res['id']:>3}  {lead['company_name']:42s}  {lead['phone']}")
            created += 1
        except requests.HTTPError as e:
            print(f"  FAIL {lead['company_name']}: {e.response.status_code} {e.response.text[:140]}")
            failed += 1

    final = list_leads(token)
    print(f"\nCreated {created}, skipped {skipped}, failed {failed}")
    print(f"Total leads in production: {len(final)}")


if __name__ == "__main__":
    main()
