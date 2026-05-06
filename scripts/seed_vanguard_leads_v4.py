"""Round-4 seed: Hamilton/Fairfield/Covington/Norwood suburb PMs.

Hits the 100-lead threshold.
"""
import os
import requests

API_BASE = "https://bycade.com"
ADMIN_USER = os.environ.get("VANGUARD_ADMIN_USER", "cade")
ADMIN_PASS = os.environ.get("VANGUARD_ADMIN_PASS", "peak2026!")

LEADS = [
    {"company_name": "PLK Communities", "contact_name": "PLK Communities HQ", "contact_role": "pm", "phone": "(513) 561-5080", "address": "2700 Park Ave, Norwood, OH 45212", "source": "BBB-PM", "notes": "Parent of Lakefront/Mallard/Latitude/Gatherall/Factory 52/A L'aise/ila/Seminary Square/Duveneck/Elevation 800/Remington Lake. Manages Norwood + Hyde Park + W Chester + Mason + Hamilton + Covington luxury apt buildings. SAME PHONE as the Lakefront entry — call HQ once, not each property."},
    {"company_name": "Bed & Breakfast Property Management", "contact_name": "Bed & Breakfast PM", "contact_role": "pm", "phone": "(513) 737-8963", "address": "3189 Princeton Rd #298, Fairfield Township, OH 45011", "source": "BBB-PM", "notes": "Property Mgmt + Real Estate Investing. Fairfield Twp small operator."},
    {"company_name": "JTF Properties", "contact_name": "JTF Properties", "contact_role": "pm", "phone": "(513) 860-9835", "address": "4235 Muhlhauser Rd, Fairfield, OH 45014", "source": "BBB-PM", "notes": "Small Fairfield PM. Niche fit."},
    {"company_name": "TB Properties", "contact_name": "TB Properties", "contact_role": "pm", "phone": "(513) 829-1287", "address": "5284 Winton Rd, Fairfield, OH 45014", "source": "BBB-PM", "notes": "Real Estate Development + PM. Fairfield."},
    {"company_name": "R.F. Miller Homes", "contact_name": "R.F. Miller Homes", "contact_role": "pm", "phone": "(513) 829-4446", "address": "526 Nilles Rd Ste 6, Fairfield, OH 45014", "source": "BBB-PM", "notes": "Property Mgmt + Apartments + Industrial PM. Fairfield. Industrial = bigger electrical scope per call."},
    {"company_name": "Management Plus Realty Service", "contact_name": "Management Plus", "contact_role": "pm", "phone": "(513) 772-2570", "address": "9916 Windisch Rd, West Chester, OH 45069", "source": "BBB-PM", "notes": "PM + HOA. W Chester. HOA work = common-area lighting, panels, EV chargers."},
    {"company_name": "Eagle Realty Group", "contact_name": "Eagle Realty", "contact_role": "investor", "phone": "(513) 361-7700", "address": "301 E Fourth St 37th Fl, Cincinnati, OH 45202", "source": "BBB-INV", "notes": "Real Estate + PM + Investment Advisory. Western & Southern subsidiary — class-A. Long sales cycle but big portfolio."},
    {"company_name": "Towne Properties NKY", "contact_name": "Towne NKY office", "contact_role": "pm", "phone": "(859) 341-8558", "address": "109 Wrights Point Dr, Covington, KY 41011", "source": "BBB-PM", "notes": "Towne Properties NKY regional office — separate phone from OH HQ. Cover Covington/Newport portfolio."},
    {"company_name": "CMC Properties Brook Hollow", "contact_name": "Brook Hollow office", "contact_role": "pm", "phone": "(513) 863-8940", "address": "364 Hampshire Dr Brook Hollow Apts, Hamilton, OH 45011", "source": "BBB-PM", "notes": "CMC apartment property direct line. Hamilton."},
    {"company_name": "CMC Properties Fairfield North", "contact_name": "Fairfield North office", "contact_role": "pm", "phone": "(513) 737-1133", "address": "414 Hampshire Dr Fairfield North Apts, Hamilton, OH 45011", "source": "BBB-PM", "notes": "CMC apartment property direct line. Onsite mgr answers — better than HQ for fast jobs."},
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
