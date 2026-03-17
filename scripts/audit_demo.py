"""Audit demo-data.json — check sizes and list all keys."""
import json

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

print(f"All {len(data)} keys:")
for k in sorted(data.keys()):
    size = len(json.dumps(data[k]))
    print(f"  {k}  ({size:,} bytes)")

print(f"\nTotal file size: {len(json.dumps(data, indent=2)):,} bytes")

# Flag large entries
print("\nLarge entries (>10KB):")
for k in sorted(data.keys()):
    size = len(json.dumps(data[k]))
    if size > 10000:
        print(f"  {k}  ({size:,} bytes)")
