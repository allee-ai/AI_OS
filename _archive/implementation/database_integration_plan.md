# Database Integration Plan

**Status:** ✅ IMPLEMENTED (see `Nola/idv2/idv2.py`)  
**Last Updated:** 2025-12-23

> **Note:** This plan has been implemented as the `idv2` module. The SQLite backend is operational with push/pull/sync operations, context-level filtering (L1/L2/L3), and Docker volume persistence. See [idv2/idreadme.md](../Nola/idv2/idreadme.md) for implementation details.

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

### Frontend Developer Note

**Important**: The React app currently recreates the nested folder structure `Nola/stimuli/conversations/` that already exists in the project. This redundancy should be addressed during the frontend refactor to prevent conflicts and maintain clean file organization.

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