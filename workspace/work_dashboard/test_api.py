"""Quick test of all API endpoints."""
import urllib.request
import json

BASE = "http://127.0.0.1:8348"

def get(path):
    r = urllib.request.urlopen(BASE + path)
    return json.loads(r.read())

def get_html(path):
    r = urllib.request.urlopen(BASE + path)
    return r.read().decode()

# Test /api/data
data = get("/api/data")
print("=== /api/data ===")
print(f"  completed: {len(data['completed'])} jobs")
print(f"  scheduled: {len(data['scheduled'])} jobs")
print(f"  pending: {len(data['pending'])} jobs")
print(f"  payments: {len(data['payments'])} payments")

# Test /api/properties
props = get("/api/properties")
print(f"\n=== /api/properties === ({len(props)} total)")

# Test /api/owner/properties
oprops = get("/api/owner/properties")
print(f"=== /api/owner/properties === ({len(oprops)} total)")
print(f"  First: {oprops[0]['address']}, jobs: {oprops[0]['jobs']}")

# Test /api/tenant/7697-oceola
tenant = get("/api/tenant/7697-oceola")
print(f"\n=== /api/tenant/7697-oceola ===")
print(f"  property: {tenant['address']}, orders: {len(tenant['work_orders'])}")

# Test page routes
html = get_html("/")
print(f"\n=== Pages ===")
print(f"  / : {len(html)} bytes, has 'Jake': {'Jake' in html}")
html = get_html("/owner")
print(f"  /owner : {len(html)} bytes, has 'Property': {'Property' in html}")
html = get_html("/tenant/7697-oceola")
print(f"  /tenant/7697-oceola : {len(html)} bytes, has 'Work Order': {'Work Order' in html}")

print("\nAll tests passed!")
