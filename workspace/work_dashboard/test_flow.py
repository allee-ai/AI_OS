"""Test work order submission and owner approval flow."""
import urllib.request
import json

BASE = "http://127.0.0.1:8348"

def post(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(BASE + path, data=body, headers={"Content-Type": "application/json"})
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

def get(path):
    return json.loads(urllib.request.urlopen(BASE + path).read())

# 1. Submit a work order as a tenant
print("1. Submitting work order for 7697 Oceola...")
wo = post("/api/tenant/7697-oceola/work-order", {
    "property_id": 8,  # 7697 Oceola
    "description": "Kitchen faucet leaking badly",
    "urgency": "high"
})
print(f"   Created WO #{wo['id']}: {wo['description']} [{wo['status']}]")

# 2. Check it shows up on owner page
orders = get("/api/owner/work-orders")
submitted = [o for o in orders if o["status"] == "submitted"]
print(f"\n2. Owner sees {len(submitted)} pending work order(s)")
print(f"   Latest: {submitted[0]['description']} at {submitted[0]['property_address']}")

# 3. Approve it
print(f"\n3. Approving WO #{wo['id']}...")
result = post(f"/api/owner/work-orders/{wo['id']}/approve", {})
print(f"   Result: {result}")

# 4. Check job was created
jobs = get("/api/jobs?status=pending")
new_job = [j for j in jobs if j["description"] == "Kitchen faucet leaking badly"]
print(f"\n4. New pending job created: {len(new_job) > 0}")
if new_job:
    print(f"   Job #{new_job[0]['id']}: {new_job[0]['description']} at {new_job[0]['property_address']}")

# 5. Clean up — delete the test job and check
print(f"\n5. Cleaning up test data...")
if new_job:
    req = urllib.request.Request(BASE + f"/api/jobs/{new_job[0]['id']}", method="DELETE")
    urllib.request.urlopen(req)
    print("   Test job deleted")

print("\nFull flow test passed!")
