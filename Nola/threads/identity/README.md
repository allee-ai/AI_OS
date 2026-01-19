# Identity Thread

The Identity Thread answers: **"Who am I? Who are you?"**

## Purpose

Identity stores facts about self and user that persist across conversations. This is the most important thread — user identity facts take highest priority in context assembly.

## Architecture: L1/L2/L3 Per Key

Each identity key has three levels of detail:

```
key: "user_name"
L1: "Jordan"                                    (~5 tokens, realtime)
L2: "Jordan, software developer"                (~15 tokens, conversational)
L3: "Jordan, software developer building AI_OS, prefers morning work sessions"  (~30 tokens, analytical)
```

### Why Levels?

- **L1 (Realtime)**: Minimum viable context for quick responses
- **L2 (Conversational)**: Standard context for normal chat
- **L3 (Analytical)**: Full context for complex reasoning

## Modules

### `identity_flat`
The main identity table with hierarchical levels:

| Column | Purpose |
|--------|---------|
| `key` | Unique identifier (e.g., "user_name", "nola_personality") |
| `metadata_type` | Category: "user", "nola", "machine", "relationship" |
| `metadata_desc` | Human-readable description |
| `l1` | Quick fact (~10 tokens) |
| `l2` | Standard fact (~30 tokens) |
| `l3` | Full context (~100 tokens) |
| `weight` | 0.0-1.0, higher = more important |

## Key Principles

### User is Most Important
User identity facts should have the highest weights. Nola exists to serve the user — their name, preferences, and projects matter most.

### Slow to Change
Identity facts are stable. They update through:
1. **Explicit correction**: User says "Actually, my name is..."
2. **Consolidation daemon**: Repeated patterns promote to identity
3. **Manual editing**: Through the Threads UI

### Weight Decay
Facts not accessed decay over time. Frequently referenced facts maintain high weight.

## Example Data

```sql
INSERT INTO identity_flat (key, metadata_type, l1, l2, l3, weight)
VALUES 
  ('user_name', 'user', 'Jordan', 'Jordan, software developer', 
   'Jordan, software developer building AI_OS project, prefers concise responses', 0.95),
  
  ('nola_personality', 'nola', 'Helpful assistant', 
   'Nola: curious, warm, direct communicator',
   'Nola: curious and engaged, warm but professional, prefers direct communication, asks clarifying questions', 0.8);
```

## API Usage

```python
from Nola.threads.identity.adapter import IdentityThreadAdapter

adapter = IdentityThreadAdapter()

# Get facts at L2
facts = adapter.get_data(level=2, limit=10)

# Push new fact
adapter.push_identity(
    key="user_project",
    l1="AI_OS",
    l2="AI_OS, a cognitive architecture project",
    l3="AI_OS, a cognitive architecture with 5 threads...",
    metadata_type="user",
    weight=0.8
)
```

## Integration with Other Threads

- **Log**: Records when identity facts are accessed/modified
- **Linking Core**: Scores which identity facts are relevant right now
- **Philosophy**: Identity informs how Nola approaches values
- **Form**: User preferences affect tool behavior

## Implementation (canonical)

## Implementation (full)

The canonical implementation details and migration plan for the state/database integration are included here (transferred from `docs/implementation/database_integration_plan.md`).

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

