# Identity Thread

**Cognitive Question**: WHO am I? WHO are you?  
**Resolution Order**: 1st (all thought patterns resolve identity first)  
**Brain Mapping**: Prefrontal Cortex (self-model, theory of mind)

---

## Necessity

All psychological documentation confirms: cognition begins with identity resolution. Before "what should I do?" comes "who am I?" and "who is this?". Without identity anchoring, agents drift into incoherent personas.

---

## Backend

### Database Tables

| Table | Location | Purpose |
|-------|----------|---------|
| `identity_flat` | `schema.py:1469` | Main identity storage with L1/L2/L3 columns |
| `profiles` | `schema.py:1881` | Profile entities (user, nola, contacts) |
| `profile_facts` | `schema.py:1941` | Facts linked to profiles |

### Key Functions

| Function | Location | Purpose |
|----------|----------|---------|
| `init_identity_flat()` | `schema.py:1462` | Create identity table |
| `push_identity_row()` | `schema.py:1492` | Insert/update identity fact |
| `pull_identity_flat()` | `schema.py:1525` | Get facts at specified level |
| `get_identity_context()` | `schema.py:1549` | Format facts for system prompt |
| `get_identity_table_data()` | `schema.py:1572` | Get all facts for UI table |

### Adapter

| Method | Location | Purpose |
|--------|----------|---------|
| `get_data()` | `adapter.py:51` | Get identity data at HEA level |
| `get_table_data()` | `adapter.py:62` | Get all rows for table display |
| `get_context_string()` | `adapter.py:70` | Get formatted context for prompt |
| `set_fact()` | `adapter.py:80` | Set fact with L1/L2/L3 |
| `introspect()` | `adapter.py:97` | Return structured introspection |
| `health()` | `adapter.py:113` | Health check |

---

## Context Levels

| Level | Token Budget | Content |
|-------|--------------|---------|
| **L1** | ~10 tokens | `machineID`, `userID`, metadata only |
| **L2** | ~50 tokens | L1 + top-k PROFILES with profile metadata |
| **L3** | ~200 tokens | L2 + top-k FACTS per profile |

### Example L1/L2/L3

```
key: "user_name"
L1: "Jordan"                                    (~5 tokens)
L2: "Jordan, software developer"                (~15 tokens)
L3: "Jordan, software developer building AI_OS, prefers morning sessions" (~30 tokens)
```

---

## Frontend

| Component | Location | Status |
|-----------|----------|--------|
| `ProfilesPage.tsx` | `react-chat-app/frontend/src/pages/ProfilesPage.tsx` | ✅ Done |
| Identity table | `ThreadsPage.tsx:217-231` | ✅ Done |

**Features**:
- ✅ View all identity facts
- ✅ Edit L1/L2/L3 values inline
- ✅ Adjust weights
- ✅ Add new facts
- ✅ Filter by metadata_type (user/nola/machine/relationship)

---

## Integration Points

| Thread | Integration |
|--------|-------------|
| **Log** | Records when identity facts accessed/modified |
| **Linking Core** | Scores which identity facts are relevant NOW |
| **Philosophy** | Identity informs value application |
| **Form** | User preferences affect tool behavior |
| **Subconscious** | `get_context()` pulls identity at specified level |

---

## Weight Semantics

- **0.9+**: Core identity (name, role)
- **0.6-0.8**: Important preferences (communication style)
- **0.3-0.5**: Contextual facts (current project)
- **<0.3**: Peripheral (mentioned once)

Higher weight = retrieved more often = stays in working memory.

# Database Integration Plan

**Status:** ✅ IMPLEMENTED (see `Nola/idv2/idv2.py`)  
**Last Updated:** 2025-12-23

> **Note:** This plan has been implemented as the `idv2` module. The SQLite backend is operational with push/pull/sync operations, context-level filtering (L1/L2/L3), and Docker volume persistence. See `Nola/idv2/idreadme.md` for implementation details.

## Overview

This document outlines the migration from flat JSON file storage to a persistent SQLite database system for Nola's state management. The goal is to maintain local-first architecture while enabling persistent, editable state across sessions.

## Current Architecture

- **State Storage**: JSON files in various locations
- **Persistence**: File-based, session-dependent
- **Editing**: Manual file modification
- **Scaling**: Limited by file I/O performance

## Target Architecture

- **State Storage**: SQLite database with JSON columns
- **Persistence**: Docker volume-mounted database file
- **Editing**: Web UI with real-time state modification
- **Scaling**: Efficient nested key queries and updates

## Implementation Strategy

### Phase 1: Database Schema Design

**Primary Table Structure:**
```sql
CREATE TABLE IF NOT EXISTS state_storage (
    key_name TEXT PRIMARY KEY,       -- 'Identity', 'Persona', 'Context'
    value_json TEXT,                 -- Nested JSON structure
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    message TEXT,
    speaker TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Phase 2: Migration Strategy

1. **JSON Preservation**: Existing JSON files become database seed data
2. **Checkpoint System**: JSONs serve as state restoration points for catastrophic failure
3. **Migration Script**: Automated conversion from file-based to database storage

### Phase 3: Docker Volume Integration

**docker-compose.yml Configuration:**
```yaml
services:
  nola_backend:
    volumes:
      - nola_memory:/app/data/db/
      
volumes:
  nola_memory:
```

**Database Initialization:**
- First run: Creates empty database from JSON checkpoints
- Subsequent runs: Loads existing state from persistent volume

### Phase 4: Frontend Integration

**Editable State UI:**
- Real-time key/value editing interface
- Nested key creation and modification
- State synchronization with backend
- Visual state tree representation

## Technical Benefits

1. **Persistence**: State survives container restarts
2. **Performance**: Efficient querying of nested JSON structures
3. **Concurrency**: Safe multi-user access (when scaled)
4. **Flexibility**: Dynamic schema via JSON columns
5. **Portability**: Single SQLite file for entire state

## API Endpoints

```
GET    /api/state                    # Retrieve full state
GET    /api/state/{key}             # Retrieve specific key
PUT    /api/state/{key}             # Update/create key
DELETE /api/state/{key}             # Remove key
POST   /api/state/restore           # Restore from JSON checkpoint
```

## Risk Mitigation

- **Data Loss**: JSON checkpoint system provides rollback capability
- **Corruption**: Database integrity checks and backup procedures
- **Migration Issues**: Gradual rollout with fallback to JSON files

---

## Notes

### Identity Thread v2 Development Plan

**Current Status**: Working with `Nola/identity_thread` containing existing JSON state files

**Migration Plan:**
1. **JSON Preservation**: Convert existing JSONs in `identity_thread` to database creation tools
2. **Checkpoint System**: Treat current JSONs as state checkpoints for catastrophic failure recovery
3. **Database Seeding**: Use preserved JSONs as starting point when users clone the app
4. **State Bootstrap**: On first run, database populates from these JSON "templates"

**Next Phase - Frontend Development:**
- Jump to React app development for user-friendly interface
- Implement editable database interface
- Create intuitive state management UI

## Technical Benefits

1. **Persistence**: State survives container restarts
2. **Performance**: Efficient querying of nested JSON structures
3. **Concurrency**: Safe multi-user access (when scaled)
4. **Flexibility**: Dynamic schema via JSON columns
5. **Portability**: Single SQLite file for entire state

### Frontend Developer Note

**Important**: The React app currently recreates the nested folder structure `Nola/Stimuli/conversations/` that already exists in the project. This redundancy should be addressed during the frontend refactor to prevent conflicts and maintain clean file organization.

**Folder Structure Consideration:**
- Existing: `Nola/Stimuli/conversations/` (note capitalization)
- React Creates: `Nola/stimuli/conversations/` (lowercase)
- Solution needed: Align folder creation with existing structure or consolidate

### Implementation Priority

1. **Backend**: Database integration and migration scripts
2. **State Management**: JSON-to-database conversion tools  
3. **Frontend**: Editable state interface
4. **Testing**: State persistence and UI functionality
5. **Documentation**: User guides and API documentation

