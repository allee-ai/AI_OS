"""Round-2 seed: adjacent trade leads for Vanguard sales pipeline.

These are real Cincinnati-area Builders / GCs / Remodelers / Handyman / Home
Improvement firms — all of which subcontract electrical work or own portfolios
that need recurring electrical service. Plus more BBB-verified small property
managers and SFR landlords.

All names + phones + addresses verified from BBB Cincinnati directory listings.

Idempotent — skips by company_name. Run from Mac:
    .venv/bin/python scripts/seed_vanguard_leads_v2.py
"""
import os
import json
import requests

API_BASE = "https://bycade.com"
ADMIN_USER = os.environ.get("VANGUARD_ADMIN_USER", "cade")
ADMIN_PASS = os.environ.get("VANGUARD_ADMIN_PASS", "peak2026!")

# Categories used as `source`:
#   "BBB-PM"   = property mgmt firm
#   "BBB-SFR"  = single-family rental landlord
#   "BBB-GC"   = general contractor / builder (subs out electrical)
#   "BBB-REM"  = remodeler / home renovator (subs out electrical)
#   "BBB-HND"  = handyman / home improvement / multi-trade
LEADS = [
    # ── More small property managers (BBB pages 4-6) ───────────────────────
    {"company_name": "Weybridge Property Management", "contact_name": "Weybridge office", "contact_role": "pm", "phone": "(513) 407-8069", "address": "1663 Summit Rd, Cincinnati, OH 45237", "source": "BBB-PM", "notes": "Property mgmt + RE Investing + Property Maintenance — multi-trade, definitely subs out. Strong fit."},
    {"company_name": "University Investments of Cincinnati", "contact_name": "University Investments", "contact_role": "investor", "phone": "(513) 432-7362", "address": "2530 Spring Grove Ave Ste 1A, Cincinnati, OH 45214", "source": "BBB-PM", "notes": "PM + GC + Remodeling. Operates near UC. They do their own GC work = need electrical subs. HOT."},
    {"company_name": "RPM Midwest - Real Property Management", "contact_name": "RPM Midwest", "contact_role": "pm", "phone": "(513) 762-9000", "address": "2351 W McMicken Ave, Cincinnati, OH 45214", "source": "BBB-PM", "notes": "Real Property Management franchise — SFR-focused nationally. Strong niche fit."},
    {"company_name": "Hills Property Management", "contact_name": "Hills PM office", "contact_role": "pm", "phone": "(513) 984-0300", "address": "2335 Long Vista Ln, Cincinnati, OH 45234", "source": "BBB-PM", "notes": "PM + Construction Management. They run their own builds = sub electrical out."},
    {"company_name": "Hunt Property Management", "contact_name": "Hunt PM office", "contact_role": "pm", "phone": "(859) 866-1766", "address": "305 W 11th St, Newport, KY 41071", "source": "BBB-PM", "notes": "NKY operator. Home additions + concrete + tree services + PM = handles small res."},
    {"company_name": "Rentz Management", "contact_name": "Rentz office", "contact_role": "pm", "phone": "(859) 581-4815", "address": "421 Scott Blvd, Covington, KY 41011", "source": "BBB-PM", "notes": "Small NKY property manager. Covington/Newport portfolio likely older = wiring upgrades."},
    {"company_name": "Advantage Property Management", "contact_name": "Advantage PM office", "contact_role": "pm", "phone": "(513) 984-4114", "address": "7712 Blue Ash Rd, Cincinnati, OH 45236", "source": "BBB-PM", "notes": "Blue Ash / Madeira / Kenwood — established mixed res portfolio."},
    {"company_name": "Balanced Property Solutions", "contact_name": "Balanced PM office", "contact_role": "pm", "phone": "(513) 351-1412", "address": "1385 W Galbraith Rd, Cincinnati, OH 45231", "source": "BBB-PM", "notes": "North side small PM. Galbraith corridor."},
    # ── Single-family rental landlords (REITs + small) ─────────────────────
    {"company_name": "Wham Properties", "contact_name": "Wham Properties", "contact_role": "investor", "phone": "(513) 206-9757", "address": "PO Box 8233, Cincinnati, OH 45208", "source": "BBB-SFR", "notes": "Hyde Park-based RE rental + investing. Smaller landlord."},
    {"company_name": "Buchanan Homes", "contact_name": "Buchanan Homes", "contact_role": "investor", "phone": "(513) 620-8518", "address": "PO Box 30378, Cincinnati, OH 45230", "source": "BBB-SFR", "notes": "Anderson Twp area SFR rentals + leasing."},
    {"company_name": "Equitable Housing Solutions", "contact_name": "Equitable Housing", "contact_role": "investor", "phone": "(513) 442-3279", "address": "409 Terrace Pl Ste 227, Terrace Park, OH 45174", "source": "BBB-SFR", "notes": "Rent-to-own + RE Investing + Rentals = lots of rehab work, ideal sub-out customer."},
    {"company_name": "Vinebrook Homes Cincinnati", "contact_name": "Vinebrook ops", "contact_role": "investor", "phone": "(855) 513-5678", "address": "4856 Business Center Way, Cincinnati, OH 45246", "source": "BBB-SFR", "notes": "MASSIVE single-family REIT — owns 1000s of SFRs in Cincy. They sub ALL trades. THE biggest opportunity on this list. Ask for their maintenance director or vendor coordinator."},
    {"company_name": "American Homes 4 Rent", "contact_name": "AH4R Mason office", "contact_role": "investor", "phone": "(833) 736-8264", "address": "4700 Duke Dr Ste 170A, Mason, OH 45040", "source": "BBB-SFR", "notes": "Major SFR REIT, regional office in Mason. Vendor program — apply via portal but cold-call helps."},

    # ── Builders / GCs (sub out electrical) ────────────────────────────────
    {"company_name": "A.W. Limited", "contact_name": "A.W. Limited", "contact_role": "pm", "phone": "(513) 543-0811", "address": "4306 Floral Ave, Norwood, OH 45212", "source": "BBB-GC", "notes": "Building Contractors + Property Maintenance + Industrial PM = managing real properties + subbing trades. HOT."},
    {"company_name": "Hunt Builders Corporation", "contact_name": "Hunt Builders", "contact_role": "pm", "phone": "(513) 579-9770", "address": "221 E 4th St Ste 2510, Cincinnati, OH 45202", "source": "BBB-GC", "notes": "Construction Mgmt + GC. Downtown — likely commercial-leaning but worth a call for residential-side projects."},
    {"company_name": "Hy-Tech Builders", "contact_name": "Hy-Tech Builders", "contact_role": "pm", "phone": "(513) 884-4270", "address": "9133 Reading Rd, Cincinnati, OH 45215", "source": "BBB-GC", "notes": "Construction Services + GC + Home Improvement. Reading Rd = residential turf."},
    {"company_name": "Pope & Son Construction", "contact_name": "Pope & Son", "contact_role": "pm", "phone": "(513) 473-6671", "address": "570 Enright Ave, Cincinnati, OH 45205", "source": "BBB-GC", "notes": "Westside small builder. East Price Hill area."},
    {"company_name": "R & M Contracting", "contact_name": "R&M Contracting", "contact_role": "pm", "phone": "(513) 516-1166", "address": "63 Dunster Ct, Ft Mitchell, KY 41017", "source": "BBB-GC", "notes": "NKY small builder."},
    {"company_name": "Best Way Construction & Maintenance", "contact_name": "Best Way", "contact_role": "pm", "phone": "(513) 226-0787", "address": "10555 Montgomery Rd Apt 35, Montgomery, OH 45242", "source": "BBB-GC", "notes": "Building Contractors — name says maintenance = recurring small-job work."},
    {"company_name": "MDF Contracting", "contact_name": "MDF Contracting", "contact_role": "pm", "phone": "(513) 439-8163", "address": "594 Dorgene Ln, Cincinnati, OH 45244", "source": "BBB-GC", "notes": "GC + Siding Contractors — east side. Sub-out electrical on whole-house jobs."},
    {"company_name": "Jefferson Enterprises", "contact_name": "Jefferson Enterprises", "contact_role": "pm", "phone": "(513) 614-4775", "address": "PO Box 29104, Cincinnati, OH 45229", "source": "BBB-GC", "notes": "Small GC operator. Avondale area."},
    {"company_name": "HGC Construction", "contact_name": "HGC Construction", "contact_role": "pm", "phone": "(513) 861-8866", "address": "2814 Stanton Ave, Cincinnati, OH 45206", "source": "BBB-GC", "notes": "Mid-size Cincy GC, Walnut Hills. They sub electrical to specialty trades."},
    {"company_name": "Blue Seal Restoration", "contact_name": "Blue Seal", "contact_role": "pm", "phone": "(513) 493-7141", "address": "7367 Werner Ave, Cincinnati, OH 45231", "source": "BBB-GC", "notes": "GC + Roofing + Restoration. Insurance restoration jobs = burnt-wiring repairs."},
    {"company_name": "Forge & Frame Construction", "contact_name": "Forge & Frame", "contact_role": "pm", "phone": "(513) 913-9698", "address": "Cincinnati, OH 45238 (Westside)", "source": "BBB-GC", "notes": "Home Renovation + GC + Remodeling. Westside small operator."},
    {"company_name": "Zoe Consulting", "contact_name": "Zoe Consulting", "contact_role": "pm", "phone": "(513) 288-3668", "address": "1557 Tremont St, Cincinnati, OH 45214", "source": "BBB-GC", "notes": "GC + Home Improvement. Camp Washington area."},
    {"company_name": "Holmes by Troy", "contact_name": "Troy Holmes", "contact_role": "pm", "phone": "(859) 779-9883", "address": "Cincinnati, OH 45207", "source": "BBB-HND", "notes": "Handyman + GC + Construction Services. Multi-trade = perfect partnership candidate."},
    {"company_name": "Scott Segers & Company", "contact_name": "Scott Segers", "contact_role": "pm", "phone": "(513) 305-1107", "address": "345 Thrall St, Cincinnati, OH 45220", "source": "BBB-GC", "notes": "Small GC, Clifton/Corryville."},
    {"company_name": "Hibbards Quality Home Improvement", "contact_name": "Hibbards", "contact_role": "pm", "phone": "(513) 383-0320", "address": "4800 Kennedy Ave, Cincinnati, OH 45209", "source": "BBB-GC", "notes": "Norwood area. Long-established GC."},
    {"company_name": "R. Horton Construction", "contact_name": "R. Horton", "contact_role": "pm", "phone": "(513) 328-2067", "address": "1412 Ambrose Ave, Cincinnati, OH 45224", "source": "BBB-GC", "notes": "GC + Home Builders + Excavating = full-spectrum builder. They sub electrical for sure."},
    {"company_name": "Roth Star", "contact_name": "Roth Star", "contact_role": "pm", "phone": "(513) 300-0986", "address": "Tri-State Service Area, Cincinnati, OH 45202", "source": "BBB-HND", "notes": "Handyman + GC + Construction Services. Wide service area."},
    # ── Home improvement / handyman / multi-trade ─────────────────────────
    {"company_name": "DBG Builders", "contact_name": "DBG Builders", "contact_role": "pm", "phone": "(513) 289-7808", "address": "Cincinnati, OH 45212 (Norwood)", "source": "BBB-HND", "notes": "Construction + Painting + Handyman. Norwood. Recurring small jobs = perfect customer."},
    {"company_name": "First Choice Lead Abatement & Rehab", "contact_name": "First Choice Lead Abatement", "contact_role": "pm", "phone": "(513) 628-2777", "address": "1818 Lawn Ave, Cincinnati, OH 45237", "source": "BBB-GC", "notes": "Lead abatement + rehab = pre-1978 housing specialists. Knob-and-tube replacements bundled with lead remediation. HOT."},
    {"company_name": "Anderson Construction", "contact_name": "Anderson Construction", "contact_role": "pm", "phone": "(513) 706-3473", "address": "2843 Hocking Dr, Cincinnati, OH 45233", "source": "BBB-GC", "notes": "Construction + Home Improvement + Bath Remodel. Westside GC."},
    {"company_name": "JF Construction Pro", "contact_name": "JF Construction", "contact_role": "pm", "phone": "(513) 623-2323", "address": "Cincinnati, OH 45238 (Westside)", "source": "BBB-HND", "notes": "Home Improvement + Roofing + Handyman."},
    {"company_name": "L.E.G Home Improvement", "contact_name": "L.E.G", "contact_role": "pm", "phone": "(513) 237-6486", "address": "1926 W Kemper Rd, Cincinnati, OH 45240", "source": "BBB-HND", "notes": "Home Improvement + Construction + Drywall. Forest Park/Kemper area."},
    {"company_name": "Cincinnati Elite Construction", "contact_name": "Cincinnati Elite", "contact_role": "pm", "phone": "(513) 394-0151", "address": "Cincinnati, OH 45219 (Walnut Hills)", "source": "BBB-GC", "notes": "Construction + Painting + Fence."},
    {"company_name": "1GOOD Handyman Service", "contact_name": "1GOOD Handyman", "contact_role": "pm", "phone": "(513) 293-9138", "address": "4392 Glenhaven Rd, Cincinnati, OH 45238", "source": "BBB-HND", "notes": "Pure handyman. Likely refers electrical work out. Build a referral relationship."},
    {"company_name": "LuxCincy", "contact_name": "LuxCincy", "contact_role": "investor", "phone": "(513) 319-9501", "address": "3500 Columbia Pkwy Ste 125, Cincinnati, OH 45226", "source": "BBB-GC", "notes": "Real Estate + Home Improvement + Bath Remodel = property flippers. Hyde Park-area flips."},
    {"company_name": "Mil Mil Remodeling", "contact_name": "Mil Mil", "contact_role": "pm", "phone": "(513) 888-0018", "address": "Cincinnati, OH 45205 (Price Hill)", "source": "BBB-REM", "notes": "Construction + Roofing + Home Improvement."},
    # ── Home renovation / remodeler ───────────────────────────────────────
    {"company_name": "Ridge Renovations", "contact_name": "Ridge Renovations", "contact_role": "pm", "phone": "(513) 673-8760", "address": "3744 Indianview Ave, Cincinnati, OH 45227", "source": "BBB-REM", "notes": "Mt Washington / Mariemont area. Pure home renovation."},
    {"company_name": "Inspired Custom Homes", "contact_name": "Inspired Custom Homes", "contact_role": "pm", "phone": "(513) 543-4627", "address": "3931 Eileen Dr, Cincinnati, OH 45209", "source": "BBB-GC", "notes": "Home Renovation + Home Builders + Remodeling. Norwood/Hyde Park area builds."},
    {"company_name": "Modern Craftsman Remodeling", "contact_name": "Modern Craftsman", "contact_role": "pm", "phone": "(513) 202-3082", "address": "Cincinnati, OH 45220 (Clifton)", "source": "BBB-REM", "notes": "Bath/Kitchen remodeler. Clifton."},
    {"company_name": "Darwins Property Solutions", "contact_name": "Darwins", "contact_role": "pm", "phone": "(513) 563-2100", "address": "559 N Wayne Ave, Lockland, OH 45215", "source": "BBB-GC", "notes": "Construction + Home Renovation + Commercial Contractors. The name itself is a tell — they touch property work all day."},
    {"company_name": "New Vision Custom Remodeling", "contact_name": "New Vision", "contact_role": "pm", "phone": "(513) 221-2519", "address": "1881 Dixie Hwy Ste 100, Ft Wright, KY 41011", "source": "BBB-REM", "notes": "NKY remodeler. Patios+decks+remodeling, residential."},
    {"company_name": "Pro-Cut Construction", "contact_name": "Pro-Cut", "contact_role": "pm", "phone": "(513) 930-9418", "address": "107 Park Ave, Elsmere, KY 41018", "source": "BBB-REM", "notes": "Remodeling + Siding + Drywall. NKY."},
    {"company_name": "Integrity Home Renovation", "contact_name": "Integrity HR", "contact_role": "pm", "phone": "(513) 403-5058", "address": "Cincinnati, OH 45248 (Western Hills)", "source": "BBB-REM", "notes": "Pure remodeler — bath, decks. Western Hills."},
    {"company_name": "Lemus Home & Remodeling", "contact_name": "Lemus", "contact_role": "pm", "phone": "(859) 638-2999", "address": "Covington, KY 41011", "source": "BBB-REM", "notes": "Covington remodeler."},
    {"company_name": "He Builds", "contact_name": "He Builds", "contact_role": "pm", "phone": "(513) 500-6096", "address": "2937 Mignon Ave, Cincinnati, OH 45211", "source": "BBB-REM", "notes": "Westwood. Home renovation + commercial kitchen renos."},
    {"company_name": "O'Rourke Homes & Remodeling", "contact_name": "O'Rourke", "contact_role": "pm", "phone": "(513) 824-9044", "address": "PO Box 128766, Cincinnati, OH 45212", "source": "BBB-REM", "notes": "Norwood-based GC + roofing + siding. Established."},
    {"company_name": "Construction Solutions", "contact_name": "Construction Solutions", "contact_role": "pm", "phone": "(513) 973-4274", "address": "3151 Madison Rd Unit 1, Cincinnati, OH 45209", "source": "BBB-GC", "notes": "Oakley. Multi-trade GC."},
    {"company_name": "JPT Construction", "contact_name": "JPT Construction", "contact_role": "pm", "phone": "(513) 407-1551", "address": "9435 Waterstone Blvd #140-53, Symmes, OH 45249", "source": "BBB-GC", "notes": "Symmes/Mason area. Multi-trade GC."},
    {"company_name": "Kraftman Construction", "contact_name": "Kraftman", "contact_role": "pm", "phone": "(513) 501-5042", "address": "149 Church St, Cincinnati, OH 45217", "source": "BBB-GC", "notes": "Carthage area. Construction + Roofing + Painting."},
    {"company_name": "Feldhaus Home Improvement", "contact_name": "Feldhaus", "contact_role": "pm", "phone": "(513) 631-1222", "address": "2826 Norwood Ave, Cincinnati, OH 45212", "source": "BBB-GC", "notes": "Norwood. Bath/Kitchen remodels — long-established."},
    {"company_name": "JA Smith Construction", "contact_name": "JA Smith", "contact_role": "pm", "phone": "(859) 581-0652", "address": "735 Monmouth St Ste 2, Newport, KY 41071", "source": "BBB-GC", "notes": "NKY GC. Kitchen + Bath."},
    {"company_name": "McGrath & Company", "contact_name": "McGrath & Co", "contact_role": "pm", "phone": "(513) 631-1242", "address": "6545 Montgomery Rd, Cincinnati, OH 45213", "source": "BBB-GC", "notes": "Pleasant Ridge. Windows + Roofing + GC."},
    {"company_name": "JDL Warm Construction", "contact_name": "JDL Warm", "contact_role": "pm", "phone": "(513) 241-3787", "address": "1125 W 8th St Ste 100, Cincinnati, OH 45203", "source": "BBB-GC", "notes": "OTR/Lower Price Hill. Pure GC."},
    {"company_name": "Advanced Contracting & Remodeling", "contact_name": "Advanced Contracting", "contact_role": "pm", "phone": "(859) 635-1854", "address": "104 North St, Wilder, KY 41071", "source": "BBB-REM", "notes": "NKY. GC + Bath + Decks."},
    {"company_name": "Monture Construction", "contact_name": "Monture", "contact_role": "pm", "phone": "(513) 207-6485", "address": "Cincinnati, OH 45227 (Mariemont)", "source": "BBB-GC", "notes": "Home Improvement + GC + Construction Services. Mariemont/Madisonville."},
    {"company_name": "Glanton Carpentry & Contracting", "contact_name": "Glanton", "contact_role": "pm", "phone": "(513) 600-6908", "address": "Cincinnati, OH 45227 (Mariemont)", "source": "BBB-GC", "notes": "GC + Plumber + Painting. Multi-trade — they know they NEED an electrical sub."},
    {"company_name": "RLS Construction", "contact_name": "RLS Construction", "contact_role": "pm", "phone": "(513) 232-7663", "address": "7220 Beechmont Ave, Mt Washington, OH 45230", "source": "BBB-GC", "notes": "Mt Washington / Anderson. GC + Roofing."},
    {"company_name": "Homeworx Construction", "contact_name": "Homeworx", "contact_role": "pm", "phone": "(859) 781-8103", "address": "16 Wilbers Lane, Fort Thomas, KY 41075", "source": "BBB-GC", "notes": "NKY GC. Kitchen cabinets + GC work."},
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
            print(f"  FAIL {lead['company_name']}: {e.response.status_code} {e.response.text[:120]}")
            failed += 1

    final = list_leads(token)
    print(f"\nCreated {created}, skipped {skipped}, failed {failed}")
    print(f"Total leads in production: {len(final)}")


if __name__ == "__main__":
    main()
