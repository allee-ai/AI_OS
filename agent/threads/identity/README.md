# Identity Thread

**Cognitive Question**: WHO am I? WHO are you? WHO do we know?  
**Resolution Order**: 1st (all cognition begins with identity resolution)  
**Brain Mapping**: Prefrontal Cortex (self-model, theory of mind)

---

## Purpose

Identity provides the foundation for all reasoning. Before "what should I do?" comes "who am I?" and "who is asking?". Without identity anchoring, agents drift into incoherent personas.

The identity thread manages:
- **Machine identity** (the agent itself)
- **Primary user** (who is talking to the agent)
- **Contacts** (family, friends, acquaintances)

---

## Database Schema

### Tables

| Table | Purpose |
|-------|---------|
| `profile_types` | Categories with trust levels (user, machine, family, friend, etc.) |
| `profiles` | Individual identity profiles |
| `fact_types` | Types of facts (name, email, preference, relationship, etc.) |
| `profile_facts` | The actual facts with L1/L2/L3 values |

### profile_facts

```sql
CREATE TABLE profile_facts (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,               -- 'name', 'likes', 'relationship'
    fact_type TEXT NOT NULL,         -- FK to fact_types
    l1_value TEXT,                   -- Brief (5-10 tokens)
    l2_value TEXT,                   -- Standard (20-50 tokens)
    l3_value TEXT,                   -- Detailed (100+ tokens)
    weight REAL DEFAULT 0.5,         -- 0.0-1.0 importance
    protected BOOLEAN DEFAULT FALSE,
    access_count INTEGER DEFAULT 0,
    PRIMARY KEY (profile_id, key)
)
```

---

## Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get facts across all profiles |
| `get_context_string(level, token_budget)` | Formatted string for prompts |
| `set_fact(profile_id, key, l1, l2, l3, fact_type, weight)` | Create/update a fact |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with fact counts |
| `score_relevance(fact, context)` | Score fact importance |
| `get_module_data(module, level)` | Get facts for a specific profile |

### introspect()

The main interface for subconscious integration. Returns `IntrospectionResult` with:
- `facts`: List of dot-notation facts like `identity.dad.name: Robert`
- `relevant_concepts`: Concepts extracted from query
- `context_level`: HEA level used
- `health`: Thread health status

Facts are filtered by `_filter_by_relevance()` using LinkingCore spread activation.

---

## Context Levels (HEA)

| Level | Content | Token Budget |
|-------|---------|--------------|
| **L1** | Core identifiers only (machine name, user name) | ~10 tokens |
| **L2** | L1 + top profiles with key facts | ~50 tokens |
| **L3** | L2 + detailed facts, relationships | ~200 tokens |

### L1/L2/L3 Value Example

```
profile: family.dad
key: name

l1_value: "Robert"
l2_value: "Robert, your father"  
l3_value: "Robert, your father, retired engineer who lives in Ohio"
```

---

## Output Format

Facts are formatted with dot notation for the STATE block:

```
identity.machine.name: Nola - a personal AI
identity.primary_user.name: Jamie
identity.dad.relationship: Your father, retired engineer
identity.dad.likes: fishing, woodworking
```

---

## Relevance Filtering

When a query is provided, `_filter_by_relevance()` uses LinkingCore to filter:

1. Extract concepts from query ("dad" -> `["dad", "father", "family"]`)
2. Run spread activation to get related concepts
3. Filter facts where profile_id, key, or value match any activated concept

Example: Query "dad" activates `family.dad.*` facts.

---

## Core Profiles

Two protected profiles are created by default:

| Profile ID | Type | Purpose |
|------------|------|---------|
| `machine` | machine | The agent itself (name, OS, capabilities) |
| `primary_user` | user | The main user (name, email, preferences) |

Additional profiles use compound IDs: `family.dad`, `friend.alex`, `acquaintance.coworker`

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/identity/profiles` | List all profiles |
| GET | `/api/identity/profiles/{id}` | Get profile with facts |
| POST | `/api/identity/profiles` | Create profile |
| DELETE | `/api/identity/profiles/{id}` | Delete profile (if not protected) |
| GET | `/api/identity/facts` | List all facts |
| POST | `/api/identity/facts` | Create/update fact |

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Subconscious** | Calls `introspect()` to build STATE block |
| **Linking Core** | Scores relevance, spread activation for filtering |
| **Log** | Records when identity facts are accessed |
| **Philosophy** | Identity informs value application |
| **Form** | User preferences affect tool behavior |

---

## Weight Semantics

| Weight | Meaning | Examples |
|--------|---------|----------|
| 0.9+ | Core identity | name, role |
| 0.6-0.8 | Important facts | occupation, email |
| 0.3-0.5 | Contextual | current project, preferences |
| <0.3 | Peripheral | mentioned once |

Higher weight = retrieved more often at lower HEA levels.

