import sqlite3

db = sqlite3.connect('data/app.db')
db.row_factory = sqlite3.Row

print('=== COMPLETED JOBS ===')
rows = db.execute(
    "SELECT p.address, j.description, j.cost, j.paid "
    "FROM jobs j JOIN properties p ON j.property_id=p.id "
    "WHERE j.status='completed' ORDER BY p.address"
).fetchall()
total_cost = 0
total_paid = 0
for r in rows:
    total_cost += r['cost']
    total_paid += r['paid']
    rem = r['cost'] - r['paid']
    print(f"  {r['address']:25s} {r['description']:30s} cost=${r['cost']:,.0f}  paid=${r['paid']:,.0f}  rem=${rem:,.0f}")
print(f"  TOTALS: cost=${total_cost:,.0f}  paid=${total_paid:,.0f}  rem=${total_cost - total_paid:,.0f}")

print()
print('=== PAYMENTS ===')
pays = db.execute('SELECT amount, date, note FROM payments ORDER BY date').fetchall()
pay_total = 0
for p in pays:
    pay_total += p['amount']
    print(f"  ${p['amount']:,.0f}  {p['date']}  {p['note']}")
print(f"  TOTAL PAYMENTS: ${pay_total:,.0f}")

print()
print('=== SUMMARY ===')
print(f"  Total Billed (completed): ${total_cost:,.0f}")
print(f"  Total Paid (per-job):     ${total_paid:,.0f}")
print(f"  Total Payments received:  ${pay_total:,.0f}")
print(f"  Balance Due:              ${total_cost - pay_total:,.0f}")

print()
print('=== BY PROPERTY ===')
props = db.execute(
    "SELECT p.address, SUM(j.cost) as billed, SUM(j.paid) as paid "
    "FROM jobs j JOIN properties p ON j.property_id=p.id "
    "WHERE j.status='completed' GROUP BY p.address ORDER BY SUM(j.cost) DESC"
).fetchall()
for p in props:
    print(f"  {p['address']:25s} billed=${p['billed']:,.0f}  paid=${p['paid']:,.0f}  rem=${p['billed']-p['paid']:,.0f}")

sched = db.execute("SELECT SUM(cost) FROM jobs WHERE status='scheduled'").fetchone()[0] or 0
pend = db.execute("SELECT SUM(cost) FROM jobs WHERE status='pending'").fetchone()[0] or 0
print()
print(f"  Scheduled work: ${sched:,.0f}")
print(f"  Pending work:   ${pend:,.0f}")
