# Identity Thread

**Cognitive Question**: WHO am I? WHO are you? WHO do we know?  
**Resolution Order**: 1st (all cognition begins with identity resolution)  
**Brain Mapping**: Prefrontal Cortex (self-model, theory of mind)

---

## Description

Identity provides the foundation for all reasoning. Before "what should I do?" comes "who am I?" and "who is asking?". Without identity anchoring, agents drift into incoherent personas.

The identity thread manages:
- **Machine identity** (the agent itself)
- **Primary user** (who is talking to the agent)
- **Contacts** (family, friends, acquaintances)

---

## Architecture

<!-- ARCHITECTURE:identity -->
### Database Schema

| Table | Purpose |
|-------|---------|
| `profile_types` | Categories with trust levels (user, machine, family, friend, etc.) |
| `profiles` | Individual identity profiles |
| `fact_types` | Types of facts (name, email, preference, relationship, etc.) |
| `profile_facts` | The actual facts with L1/L2/L3 values |

```sql
CREATE TABLE profile_facts (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    l1_value TEXT,                   -- Brief (5-10 tokens)
    l2_value TEXT,                   -- Standard (20-50 tokens)
    l3_value TEXT,                   -- Detailed (100+ tokens)
    weight REAL DEFAULT 0.5,
    protected BOOLEAN DEFAULT FALSE,
    access_count INTEGER DEFAULT 0,
    PRIMARY KEY (profile_id, key)
)
```

### Adapter Methods

| Method | Purpose |
|--------|---------|
| `get_data(level, min_weight, limit)` | Get facts across all profiles |
| `set_fact(profile_id, key, l1, l2, l3, fact_type, weight)` | Create/update a fact |
| `introspect(context_level, query, threshold)` | Build STATE block contribution |
| `health()` | Health check with fact counts |

### Context Levels (HEA)

| Level | Content | Token Budget |
|-------|---------|--------------|
| **L1** | Core identifiers only (machine name, user name) | ~10 tokens |
| **L2** | L1 + top profiles with key facts | ~50 tokens |
| **L3** | L2 + detailed facts, relationships | ~200 tokens |

### Output Format

```
identity.machine.name: Nola - a personal AI
identity.primary_user.name: Jamie
identity.dad.relationship: Your father, retired engineer
```

### Preset Contact Facts

New profiles are created with empty preset facts for common contact information:

| Fact Key | Fact Type | Description |
|----------|-----------|-------------|
| `name` | name | Full name |
| `email` | email | Email address |
| `phone` | phone | Phone number |
| `location` | location | City/region/timezone |
| `occupation` | occupation | Job title or role |
| `organization` | organization | Company or affiliation |
| `relationship` | relationship | How they relate to user |
| `notes` | note | Freeform notes |

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/identity` | List all profiles |
| GET | `/api/identity/{id}/facts` | Get profile facts |
| POST | `/api/identity/facts` | Create new fact |
| PUT | `/api/identity/{id}/facts/{key}` | Edit existing fact |
| DELETE | `/api/identity/{id}/facts/{key}` | Delete fact |
| DELETE | `/api/identity/{id}` | Delete profile (if not protected) |
<!-- /ARCHITECTURE:identity -->

---

## Roadmap

<!-- ROADMAP:identity -->
### Ready for contributors
- [ ] **Family/contacts UI** — Add/edit family members from dashboard
- [ ] **Trust level indicators** — Visual badges for trust levels in UI
- [ ] **Relationship graph** — D3 visualization of user's social network
- [ ] **Profile photos** — Avatar upload and display
- [ ] **Import from contacts** — Pull from phone/Google contacts

### Technical debt
- [ ] Batch fact updates (currently one-at-a-time)
- [ ] Fact history/versioning
<!-- /ROADMAP:identity -->

---

## Changelog

<!-- CHANGELOG:identity -->
### 2026-02-01
- Added edit button (✏️) next to facts for inline editing
- Added edit modal with L1/L2/L3 fields, type selector, weight slider
- Added `ThemedSelect` component for consistent dropdown styling
- Added PUT endpoint for editing facts (`api.py`)
- Added `IdentityFactUpdate` model for partial updates (`api.py`)
- New profiles get preset contact facts: name, email, phone, location, occupation, organization, relationship, notes (`schema.py`)
- Added fact types: phone, organization, relationship, birthday (`schema.py`)
- Updated API endpoints documentation (`README.md`)

### 2026-01-27
- Profile-based schema with L1/L2/L3 values
- Protected core profiles (machine, primary_user)
- Relevance filtering via LinkingCore

### 2026-01-23
- Protected profiles created in schema init (no seed files)
- Quick accessors: `get_agent_name()`, `get_user_name()`

### 2026-01-20
- Self-contained API router at `/api/identity/`
- Introspect returns dot-notation facts
<!-- /CHANGELOG:identity -->

