#!/usr/bin/env python3
"""Fix linking_core demo data: add missing node fields, structural endpoint, cooccurrence."""
import json
import random

random.seed(42)

with open("frontend/public/demo-data.json") as f:
    data = json.load(f)

# 1. Fix node fields in graph endpoint
graph = data.get("GET /api/linking_core/graph", {})
if "nodes" in graph:
    for node in graph["nodes"]:
        if "total_strength" not in node:
            node["total_strength"] = node.get("connections", 1) * 0.65
        if "earliest_link" not in node:
            node["earliest_link"] = "2026-01-15 08:00:00"
        if "latest_link" not in node:
            node["latest_link"] = "2026-03-20 22:00:00"
        if "is_center" not in node:
            node["is_center"] = False

    # Add more links so the graph is actually visible
    existing_nodes = [n["id"] for n in graph["nodes"]]
    if len(graph.get("links", [])) < 10:
        new_links = []
        for i in range(min(len(existing_nodes), 30)):
            a = existing_nodes[i % len(existing_nodes)]
            b = existing_nodes[(i + 3) % len(existing_nodes)]
            if a != b:
                new_links.append({
                    "concept_a": a,
                    "concept_b": b,
                    "strength": round(random.uniform(0.4, 0.95), 4),
                    "fire_count": random.randint(3, 25),
                    "last_fired": "2026-03-20 22:00:00",
                })
        graph["links"] = graph.get("links", []) + new_links
        graph["stats"]["total_links"] = len(graph["links"])

# 2. Build proper structural graph with StructuralNode shape
# Needs: id, label, thread, kind, depth, weight, data
# And StructuralEdge: source, target, type, strength, fire_count, cross_thread
# Plus stats: node_count, structural_count, associative_count, threads[]
threads = ["identity", "philosophy", "form", "reflex", "log", "linking_core"]

struct_nodes = [
    # Self node (the sun)
    {"id": "self", "label": "Self", "thread": "identity", "kind": "self", "depth": -1, "weight": 1.0, "data": {}},
]

# Thread root nodes (planets) — depth 0
for t in threads:
    struct_nodes.append({
        "id": t, "label": t.replace("_", " ").title(),
        "thread": t, "kind": "thread", "depth": 0, "weight": 0.9, "data": {},
    })

# Depth-1 groups (moons) — profiles, categories, etc.
groups = {
    "identity": ["self.agent", "user.primary", "family", "friends", "acquaintances"],
    "philosophy": ["values", "ethics", "reasoning_style", "worldview", "aesthetics"],
    "form": ["system_tools", "user_tools", "api_tools"],
    "reflex": ["greetings", "safety", "shortcuts"],
    "log": ["conversations", "events", "errors"],
    "linking_core": ["concepts", "embeddings", "links"],
}

for thread, grps in groups.items():
    for g in grps:
        struct_nodes.append({
            "id": f"{thread}.{g}", "label": g.replace("_", " ").title(),
            "thread": thread, "kind": "group", "depth": 1,
            "weight": round(random.uniform(0.4, 0.8), 2), "data": {},
        })

# Depth-2 leaf facts (dust)
leaves = {
    "identity.self.agent": ["name=Nola", "role=AI assistant", "architecture=AI OS", "version=0.2"],
    "identity.user.primary": ["name=Jamie", "location=Portland", "interests=AI,music"],
    "identity.family": ["sister=Sam", "dog=Koda"],
    "philosophy.values": ["curiosity", "honesty", "growth", "helpfulness"],
    "philosophy.ethics": ["privacy_first", "no_deception", "user_autonomy"],
    "form.system_tools": ["reflex_check", "memory_consolidate", "log_event"],
    "reflex.greetings": ["hello_pattern", "goodbye_pattern"],
    "log.conversations": ["conv_001", "conv_002", "conv_003"],
    "linking_core.concepts": ["curiosity", "growth", "identity", "memory"],
}

for parent_id, facts in leaves.items():
    thread = parent_id.split(".")[0]
    for f in facts:
        struct_nodes.append({
            "id": f"{parent_id}.{f}", "label": f,
            "thread": thread, "kind": "fact", "depth": 2,
            "weight": round(random.uniform(0.2, 0.6), 2), "data": {},
        })

# Structural edges: self→threads, threads→groups, groups→leaves
structural_edges = []
for t in threads:
    structural_edges.append({"source": "self", "target": t, "type": "structural"})
for thread, grps in groups.items():
    for g in grps:
        structural_edges.append({"source": thread, "target": f"{thread}.{g}", "type": "structural"})
for parent_id, facts in leaves.items():
    thread = parent_id.split(".")[0]
    for f in facts:
        structural_edges.append({"source": parent_id, "target": f"{parent_id}.{f}", "type": "structural"})

# Associative (cross-thread) edges
associative_edges = [
    {"source": "identity.self.agent", "target": "philosophy.values", "type": "associative", "strength": 0.8, "cross_thread": True},
    {"source": "identity.user.primary", "target": "log.conversations", "type": "associative", "strength": 0.7, "cross_thread": True},
    {"source": "linking_core.concepts", "target": "philosophy.values", "type": "associative", "strength": 0.65, "cross_thread": True},
    {"source": "form.system_tools", "target": "reflex.greetings", "type": "associative", "strength": 0.5, "cross_thread": True},
    {"source": "identity.family", "target": "identity.friends", "type": "associative", "strength": 0.6, "cross_thread": False},
]

structural_data = {
    "nodes": struct_nodes,
    "structural": structural_edges,
    "associative": associative_edges,
    "stats": {
        "node_count": len(struct_nodes),
        "structural_count": len(structural_edges),
        "associative_count": len(associative_edges),
        "threads": threads,
    },
}

# Set both the base and sorted query-param variants (SW sorts params alphabetically)
data["GET /api/linking_core/graph/structural"] = structural_data
data["GET /api/linking_core/graph/structural?cross_links=true&max_cross_links=200&min_cross_strength=0.15"] = structural_data

# 3. Add cooccurrence endpoint with proper shape (key_a, key_b, count, last_seen)
cooccurrence_data = {
    "pairs": [
        {"key_a": "curiosity", "key_b": "growth", "count": 15, "last_seen": "2026-03-20 21:00:00"},
        {"key_a": "identity", "key_b": "memory", "count": 12, "last_seen": "2026-03-20 20:30:00"},
        {"key_a": "learning", "key_b": "curiosity", "count": 10, "last_seen": "2026-03-19 18:00:00"},
        {"key_a": "reasoning", "key_b": "logic", "count": 8, "last_seen": "2026-03-19 15:00:00"},
        {"key_a": "empathy", "key_b": "growth", "count": 7, "last_seen": "2026-03-18 22:00:00"},
        {"key_a": "privacy", "key_b": "autonomy", "count": 6, "last_seen": "2026-03-18 20:00:00"},
        {"key_a": "honesty", "key_b": "trust", "count": 5, "last_seen": "2026-03-17 19:00:00"},
        {"key_a": "architecture", "key_b": "threads", "count": 9, "last_seen": "2026-03-20 22:00:00"},
    ],
    "top_concepts": [
        {"concept": "curiosity", "total_count": 37},
        {"concept": "growth", "total_count": 28},
        {"concept": "identity", "total_count": 24},
        {"concept": "memory", "total_count": 20},
        {"concept": "learning", "total_count": 18},
    ],
    "stats": {"total_pairs": 8, "returned": 8, "max_count": 15},
}
data["GET /api/linking_core/cooccurrence"] = cooccurrence_data
# SW sorts params: limit < min_count alphabetically
data["GET /api/linking_core/cooccurrence?limit=200&min_count=2"] = cooccurrence_data

# 4. Add sorted query-param variants for cluster graph (anchored < max_nodes)
data["GET /api/linking_core/graph?anchored=true&max_nodes=200"] = graph
data["GET /api/linking_core/graph?anchored=false&max_nodes=200"] = graph

with open("frontend/public/demo-data.json", "w") as f:
    json.dump(data, f, indent=2)

print(f"Cluster: {len(graph['nodes'])} nodes, {len(graph['links'])} links")
print(f"Structural: {len(struct_nodes)} nodes, {len(structural_edges)} struct edges, {len(associative_edges)} assoc edges")
print(f"Threads: {threads}")
print(f"Cooccurrence: {len(cooccurrence_data['pairs'])} pairs")
