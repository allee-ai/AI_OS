"""One-shot: seed pricing CSVs and the section YAML for vre-construction site.

Run once to bootstrap the source tree. After that, edit the CSVs in Numbers
and the YAML in any editor; the build script renders pricing.html.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "workspace" / "vre-construction-src"
TBL = SRC / "pricing"
TBL.mkdir(parents=True, exist_ok=True)

TABLES: dict[str, tuple[list[str], list[list[str]]]] = {
    "diagnostic.csv": (
        ["Service", "Range", "Includes"],
        [
            ["Standard diagnostic visit", "$95–$145",
             "First hour on site, basic testing, written findings. Credits toward repair if booked."],
            ["After-hours / weekend diagnostic", "$165–$225",
             "Same scope, evenings, Saturdays, Sundays."],
            ["Emergency same-day (power out, burning smell)", "$225–$350",
             "Priority dispatch, full diagnostic, temporary make-safe."],
            ["Each additional hour on site", "$95–$125",
             "If the diagnostic extends. We tell you before the meter runs over."],
            ["Photo & phone consult (no truck roll)", "free",
             "Send us photos and a description. If we can answer without coming out, we do."],
        ],
    ),
    "outlets.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Replace standard outlet (existing box)", "$95–$165", "Per outlet. Tamper-resistant, spec-grade. Discount on quantity."],
            ["Replace GFCI outlet", "$145–$215", "Per outlet. Includes proper labeling of downstream protected outlets."],
            ["Add new outlet, existing circuit, accessible", "$175–$295", "Open basement, attic, or unfinished wall above. Cut, fish, patch hole."],
            ["Add new outlet, finished wall, fish from below", "$275–$475", "Drywall stays mostly closed; we cut one or two access holes."],
            ["Add new outlet, plaster & lath wall", "$325–$575", "Older homes. More time, more care, occasional surgery."],
            ["Convert 2-prong to 3-prong (with ground)", "$185–$285", "Per outlet. Requires a real ground path, not a cheater plug."],
            ["Convert 2-prong to GFCI (no ground available)", "$165–$235", "Per outlet. Code-acceptable on older homes where running a ground is impractical."],
            ["USB / USB-C combination outlet", "$125–$185", "Add-on to any outlet replacement."],
            ["Dedicated 20A outlet (kitchen, office, fridge)", "$285–$525", "New circuit, dedicated breaker, single outlet. See \"new circuits\" below."],
            ["240V outlet for dryer / range (existing circuit)", "$165–$275", "Receptacle swap on a circuit that already exists."],
            ["Exterior weatherproof outlet (in-use cover)", "$285–$475", "Through-wall, GFCI-protected, code-compliant cover."],
        ],
    ),
    "switches.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Replace standard switch", "$85–$145", "Per switch. Spec-grade decora."],
            ["Replace with dimmer (LED-rated)", "$135–$215", "Per switch. Includes verifying the load is dimmable."],
            ["Convert single-pole to 3-way", "$285–$525", "Adds a second switch location. Wiring run pricing depends on access."],
            ["Smart switch install (your device)", "$135–$235", "Per switch. Requires a neutral in the box; we'll tell you before quoting."],
            ["Smart switch install (we provide)", "$185–$295", "Common-brand smart switches included."],
            ["Add a neutral wire to an old switch box", "$165–$385", "Often required for smart switches in older homes."],
            ["Occupancy / vacancy sensor switch", "$165–$245", "Per switch. Closets, bathrooms, laundry."],
            ["Whole-room smart-lighting commissioning", "$185–$385", "Per room, after install. App setup, scene programming, hand-off."],
        ],
    ),
    "lighting.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Swap light fixture (existing box, you supply)", "$135–$235", "Per fixture. Standard ceiling height. Chandeliers and large fixtures see below."],
            ["Chandelier install (under 50 lbs, 9ft ceiling)", "$235–$425", "Verifies fan-rated box, assembly, hang, level."],
            ["Chandelier, vaulted / 2-story foyer", "$485–$985", "Lift or scaffold required. Ceiling height and access dictate the range."],
            ["Ceiling fan swap (existing fan-rated box)", "$185–$295", "Per fan. Includes balance and remote pairing if applicable."],
            ["New ceiling fan, no existing box, attic access", "$385–$685", "Cut ceiling, install fan-rated brace box, run wire, switch."],
            ["New ceiling fan, no attic access", "$585–$985", "Working from below, more invasive cuts."],
            ["Recessed can light, attic access (each)", "$165–$285", "4\" or 6\" airtight LED can. Cuts ceiling, runs wire, trims."],
            ["Recessed can light, no attic access (each)", "$285–$485", "Working blind from below. Includes minor drywall patch."],
            ["Run of 4–6 cans in one room (attic access)", "$725–$1,485", "Per room, single dimmer, layout consult, balanced spacing."],
            ["Under-cabinet LED lighting", "$385–$885", "Per kitchen run. Hardwired, dimmable, transformer hidden."],
            ["Closet light with door switch", "$285–$485", "Per closet. LED panel, door-activated jamb switch."],
            ["Pendant lights over island (each, with wire run)", "$235–$485", "Per pendant. Discount when multiple are run together."],
            ["Track lighting head replacement", "$95–$165", "Per head. Full track install priced separately."],
        ],
    ),
    "circuits.csv": (
        ["Work", "Range", "Notes"],
        [
            ["15A or 20A circuit, panel to nearest wall (basement)", "$285–$485", "Short run, exposed conduit or NM cable, breaker, one outlet."],
            ["20A dedicated circuit, panel to kitchen / room", "$485–$985", "Mid-length run, breaker, one outlet, drywall patch."],
            ["20A dedicated circuit, finished home, long run", "$685–$1,485", "Cross-house run, fishing through walls, multiple access points."],
            ["AFCI/GFCI breaker for an existing circuit", "$165–$285", "Per circuit. Often required when adding outlets to an old circuit."],
            ["240V / 30A circuit for window AC, water heater", "$585–$985", "Includes breaker, run, receptacle."],
            ["240V / 50A circuit for range, EV, large load", "$685–$1,485", "See EV section below for charger-specific pricing."],
            ["Sub-feed for a remote box (garage, ADU)", "$985–$2,485", "Distance and trenching dependent. Underground priced separately."],
        ],
    ),
    "panels.csv": (
        ["Work", "Range", "What's in the number"],
        [
            ["100A panel replacement (same location)", "$1,685–$2,685", "New panel, breakers, grounding, permit, inspection."],
            ["150A panel replacement (same location)", "$2,185–$3,185", "Same scope, larger panel, more breaker space."],
            ["200A panel replacement (same location)", "$2,485–$3,785", "Default modern upgrade. Includes whole-home surge protector option."],
            ["200A full service upgrade (meter, mast, panel)", "$3,285–$5,485", "Pole-to-panel: new service entrance cable, mast, weatherhead, meter base, panel, grounding rods, bonding."],
            ["200A upgrade with overhead-to-underground conversion", "$4,485–$7,985", "Coordinated with Duke Energy. Trench, conduit, riser changes."],
            ["400A residential service (large home, ADU, dual EV)", "$5,485–$9,985", "Rarely needed. We'll tell you honestly if 200A would do."],
            ["Panel relocation (move from old spot to new)", "+$685–$2,485", "Adder on top of replacement cost. Distance and wall access drive the number."],
            ["Federal Pacific / Zinsco replacement", "$2,185–$3,985", "Same as panel replacement, but we never just \"rebalance\" these. They get replaced."],
            ["Single breaker swap (any standard breaker)", "$135–$235", "If we're not already on site, this becomes a service call rate."],
            ["AFCI/GFCI/combination breaker swap (each)", "$185–$285", "Breakers themselves cost more; that's reflected."],
        ],
    ),
    "sub.csv": (
        ["Work", "Range", "Notes"],
        [
            ["60A sub-panel, near main, short feeder", "$885–$1,485", "Garage, basement, small addition."],
            ["100A sub-panel, near main, short feeder", "$1,185–$1,985", "Workshop, large garage, in-law unit."],
            ["100A sub-panel, long feeder run (50–100 ft)", "$1,685–$2,985", "Detached garage, ADU. Underground adds trenching cost."],
            ["Trenching for underground feeder (per ft)", "$15–$35", "Per linear foot, depends on soil, hardscape, depth required."],
            ["Sub-panel for hot tub or pool only", "$685–$1,285", "Smaller scope, dedicated to one load. See outdoor section."],
        ],
    ),
    "ev.csv": (
        ["Work", "Range", "What it covers"],
        [
            ["NEMA 14-50 outlet, <10 ft from panel, exposed", "$485–$785", "Garage with panel on adjacent wall. Conduit, breaker, outlet."],
            ["NEMA 14-50 outlet, 10–25 ft, exposed conduit", "$685–$1,185", "Across the garage, surface-run conduit."],
            ["NEMA 14-50 outlet, finished wall, fishing required", "$885–$1,485", "Drywall stays mostly closed; access holes patched."],
            ["Hardwired L2 charger, 40A circuit (you supply charger)", "$785–$1,385", "Most popular spec. Includes installing your charger, not buying it."],
            ["Hardwired L2 charger, 48–60A circuit", "$985–$1,685", "Future-proof. Pulls 4 gauge wire. Larger breaker."],
            ["Outdoor weatherproof EV charger install", "$985–$1,985", "Driveway-mount or exterior wall. Weather-rated disconnect, conduit."],
            ["Load management device (no panel upgrade needed)", "+$485–$885", "Adder. Lets you add a charger to a near-full panel by pausing it when the dryer or AC kicks on."],
            ["EV install requiring panel upgrade", "$3,485–$5,985", "Combined: panel upgrade + EV circuit. Common in homes built before 2000."],
            ["Tesla wall connector commissioning", "+$135–$235", "Wi-Fi setup, app pairing, power-sharing config if multiple."],
        ],
    ),
    "rewire.csv": (
        ["Scope", "Range", "What changes"],
        [
            ["Vacant home, drywall open, easy access", "$5–$8 / sqft", "Best case. Mid-renovation timing."],
            ["Occupied home, finished walls, careful", "$8–$12 / sqft", "Typical. We work room by room, minimize patches."],
            ["Plaster & lath, decorative ceilings to preserve", "$11–$16 / sqft", "Older Cincinnati homes. Surgical work, higher access cost."],
            ["Whole-home rewire of 1,200 sqft typical home", "$9,800–$14,500", "Worked example, single-story, finished walls."],
            ["Whole-home rewire of 2,000 sqft typical home", "$16,000–$24,000", "Worked example, two-story, finished."],
        ],
    ),
    "kt.csv": (
        ["Tier", "Range", "Scope"],
        [
            ["1. Targeted attic abandonment", "$1,485–$3,985", "Identify K&T circuits in the attic, kill them at the panel, run replacement circuits to the rooms they served. Single-story or attic-only K&T."],
            ["2. Second-floor + attic rewire", "$4,985–$9,985", "Most common Cincinnati scope. Removes K&T from the high-fire-risk zones, leaves first-floor circuits in modern wiring."],
            ["3. Full K&T removal & rewire", "$9,985–$22,000", "Every accessible run. Often combined with full panel upgrade. The durable answer for an insurance-difficult home."],
        ],
    ),
    "generator.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Generator interlock kit (portable generator)", "$485–$885", "Cheapest legal way to back-feed your panel. Mechanical interlock prevents back-feed to grid."],
            ["Manual transfer switch (6–10 circuit)", "$985–$1,685", "Pre-selected critical circuits. Switch them to generator manually."],
            ["Inlet box for portable generator (outdoor)", "$385–$685", "Generator plugs into outdoor inlet, no extension cords through windows."],
            ["Standby whole-home generator install (electrical only)", "$2,485–$4,985", "Generator and gas line separate trades. We do automatic transfer switch, sub-panel, controls."],
            ["Battery backup install (Tesla Powerwall, Enphase, etc.)", "$1,985–$4,985", "Electrical install only. Solar integration priced separately."],
        ],
    ),
    "surge.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Whole-home surge protector (panel-mounted)", "$285–$585", "Single biggest dollar-per-protection upgrade. Add to any panel job for cost+install."],
            ["Driven ground rod (per rod)", "$185–$385", "When existing ground is missing or insufficient. Code requires two."],
            ["Bonding of metallic systems (gas, water)", "$235–$485", "Required by code. Older homes often missing."],
            ["Re-grounding service entrance", "$385–$885", "Full grounding electrode system: rods, bonding, conductor sized to service."],
        ],
    ),
    "smoke.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Hardwired smoke detector replacement (each)", "$135–$215", "Like-for-like swap. Interconnect verified."],
            ["Hardwired combination smoke / CO (each)", "$165–$245", "Modern code default. 10-year sealed battery backup."],
            ["Add hardwired interconnected detector (no existing wire)", "$235–$485", "Per device, when adding to bring older home to code. Wireless-interconnect units lower the cost."],
            ["Full home smoke/CO retrofit (typical 3-bedroom)", "$685–$1,485", "Every required location, interconnected, code-current."],
        ],
    ),
    "remodel.csv": (
        ["Scope", "Range", "Includes"],
        [
            ["Bathroom remodel electrical (basic)", "$985–$1,985", "GFCI outlets, vent fan circuit, vanity light, switch layout, code-current."],
            ["Bathroom remodel electrical (full, with heated floor)", "$1,485–$3,485", "Adds dedicated heated-floor circuit, additional lighting, mirror lighting."],
            ["Kitchen remodel electrical (basic)", "$2,485–$4,985", "Two small-appliance circuits, dishwasher, disposal, microwave, fridge, range, range hood, code outlet spacing, under-cabinet, ceiling lights."],
            ["Kitchen remodel electrical (full reconfigure)", "$4,985–$9,985", "Island circuits, induction range upgrade, recessed lighting package, smart switches, pendant lights, USB outlets."],
            ["Adding a kitchen island with electrical", "$685–$1,685", "Outlet(s) per code, optional pendant feed from above."],
        ],
    ),
    "outdoor.csv": (
        ["Work", "Range", "Notes"],
        [
            ["Exterior weatherproof outlet (each)", "$285–$485", "Through-wall, GFCI, in-use cover."],
            ["Post light at end of driveway / walkway", "$485–$1,185", "Includes trenching, conduit, switch from inside."],
            ["Landscape lighting transformer + 4–6 fixtures", "$685–$1,485", "Low-voltage, photocell or timer."],
            ["Hot tub circuit (240V, GFCI, disconnect)", "$885–$1,685", "Code-compliant disconnect within sight, bonding, GFCI breaker."],
            ["In-ground pool electrical (basic)", "$2,485–$4,985", "Pump, light, equipment bonding, GFCI. Excludes pool-build trades."],
            ["Detached garage feeder + sub-panel + 4 circuits", "$2,485–$4,985", "Trenching priced separately. Common ADU prep."],
            ["Security lighting (motion-activated, hardwired)", "$285–$685", "Per fixture. Photocell optional."],
        ],
    ),
    "trouble.csv": (
        ["Symptom", "Typical fix", "Range"],
        [
            ["Dead outlet, GFCI tripped upstream", "Locate & reset", "$95–$165"],
            ["Dead outlet, bad connection in box", "Re-terminate or replace outlet", "$135–$245"],
            ["Whole half of room dead", "Trace backstabbed connection, replace device", "$185–$385"],
            ["Flickering lights, single fixture", "Bad bulb / fixture / dimmer mismatch", "$95–$285"],
            ["Flickering lights, whole house, dims when fridge starts", "Loose neutral at service. **This is serious.**", "$385–$985"],
            ["Breaker trips immediately on reset", "Hard short. Isolate circuit, repair fault.", "$185–$485"],
            ["Breaker trips after running a while", "Overload or thermal-failing breaker. Diagnose, replace breaker or re-allocate load.", "$185–$485"],
            ["AFCI breaker trips randomly", "Identify offending appliance or wire, swap to combo or address fault", "$185–$485"],
            ["Outdoor outlet stopped working after storm", "Replace GFCI, often the only damage", "$185–$385"],
            ["Burning smell at panel or outlet", "Emergency. We'll make safe first, repair second.", "$285–$985+"],
        ],
    ),
}


def main() -> None:
    for fname, (header, rows) in TABLES.items():
        path = TBL / fname
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        print(f"wrote {path.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
