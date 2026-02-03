# 🧱 Module Scaffold Agent
**Role**: Generate new AI_OS modules with correct structure  
**Model Agnostic**: Works with Claude, GPT, Gemini, or any LLM  
**Scope**: Backend modules, frontend modules, server registration, database schemas

---

## Your Mission

You scaffold new modules for AI OS. When asked to create a module, you generate:
1. **Backend** — Python package with FastAPI router + SQLite schema
2. **Frontend** — React/TypeScript module with components, hooks, services
3. **Registration** — Server.py router inclusion
4. **Documentation** — README with architecture markers

**The Golden Rule**: Every module is self-contained. Import the router, include it, done.

---

## Module Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                 MODULE STRUCTURE                             │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   BACKEND (/{module_name}/)                                  │
│   ├── __init__.py      # Exports router + schema funcs      │
│   ├── api.py           # FastAPI router /api/{module}       │
│   ├── schema.py        # SQLite tables + CRUD               │
│   ├── README.md        # Docs with markers                  │
│   └── {submodules}/    # Optional nested functionality      │
│                                                              │
│   FRONTEND (/frontend/src/modules/{module}/)                │
│   ├── index.ts         # Re-exports everything              │
│   ├── components/      # UI components + CSS                │
│   ├── pages/           # Route-level components             │
│   ├── hooks/           # Custom React hooks                 │
│   ├── services/        # API client class                   │
│   ├── types/           # TypeScript interfaces              │
│   └── utils/           # Constants, helpers                 │
│                                                              │
│   REGISTRATION (scripts/server.py)                          │
│   └── from {module} import router as {module}_router        │
│   └── app.include_router({module}_router)                   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Backend Templates

### __init__.py
```python
"""
{Module Name} Module
--------------------
{Brief description}

Exports:
- router: FastAPI router with all {module} endpoints
- Schema functions for DB operations
"""

from .api import router
from .schema import (
    init_{module}_tables,
    create_{entity},
    get_{entity},
    list_{entities},
    update_{entity},
    delete_{entity},
)

__all__ = [
    "router",
    "init_{module}_tables",
    "create_{entity}",
    "get_{entity}",
    "list_{entities}",
    "update_{entity}",
    "delete_{entity}",
]
```

### api.py
```python
"""
{Module} API - {Description}
============================
{Purpose and scope}

Endpoints:
  GET    /api/{module}           - List all {entities}
  POST   /api/{module}           - Create {entity}
  GET    /api/{module}/{{id}}    - Get {entity} by ID
  PUT    /api/{module}/{{id}}    - Update {entity}
  DELETE /api/{module}/{{id}}    - Delete {entity}
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import sys

# Ensure project root on path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from .schema import (
    create_{entity},
    get_{entity},
    list_{entities},
    update_{entity},
    delete_{entity},
)

router = APIRouter(prefix="/api/{module}", tags=["{module}"])


# =============================================================================
# Pydantic Models
# =============================================================================

class {Entity}Create(BaseModel):
    name: str
    # Add fields specific to this entity


class {Entity}Update(BaseModel):
    name: Optional[str] = None
    # Add optional fields for partial updates


class {Entity}Response(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: Optional[datetime] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/", response_model=List[{Entity}Response])
async def list_all_{entities}():
    """List all {entities}."""
    return list_{entities}()


@router.post("/", response_model={Entity}Response)
async def create_new_{entity}(data: {Entity}Create):
    """Create a new {entity}."""
    result = create_{entity}(name=data.name)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create {entity}")
    return result


@router.get("/{{id}}", response_model={Entity}Response)
async def get_{entity}_by_id(id: int):
    """Get a specific {entity} by ID."""
    result = get_{entity}(id)
    if not result:
        raise HTTPException(status_code=404, detail="{Entity} not found")
    return result


@router.put("/{{id}}", response_model={Entity}Response)
async def update_{entity}_by_id(id: int, data: {Entity}Update):
    """Update a {entity}."""
    result = update_{entity}(id, **data.dict(exclude_unset=True))
    if not result:
        raise HTTPException(status_code=404, detail="{Entity} not found")
    return result


@router.delete("/{{id}}")
async def delete_{entity}_by_id(id: int):
    """Delete a {entity}."""
    success = delete_{entity}(id)
    if not success:
        raise HTTPException(status_code=404, detail="{Entity} not found")
    return {"status": "deleted", "id": id}
```

### schema.py
```python
"""
{Module} Schema - {Entity} storage
----------------------------------
SQLite tables for {module} data.

Tables:
- {module}_{entities}: Main entity storage
"""

import sqlite3
from contextlib import closing
from datetime import datetime
from typing import Optional, Dict, Any, List
from pathlib import Path
import sys

# Ensure project root is on path
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from data.db import get_connection


# =============================================================================
# Table Initialization
# =============================================================================

def init_{module}_tables():
    """Initialize {module} tables."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS {module}_{entities} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                metadata_json TEXT
            )
        """)
        
        # Add indexes as needed
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_{module}_{entities}_name 
            ON {module}_{entities}(name)
        """)
        
        conn.commit()


# =============================================================================
# CRUD Operations
# =============================================================================

def create_{entity}(name: str, metadata: Optional[Dict] = None) -> Optional[Dict]:
    """Create a new {entity}."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO {module}_{entities} (name, metadata_json)
            VALUES (?, ?)
        """, (name, json.dumps(metadata) if metadata else None))
        conn.commit()
        
        return get_{entity}(cur.lastrowid)


def get_{entity}(id: int) -> Optional[Dict]:
    """Get {entity} by ID."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, created_at, updated_at, metadata_json
            FROM {module}_{entities}
            WHERE id = ?
        """, (id,))
        row = cur.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0],
            "name": row[1],
            "created_at": row[2],
            "updated_at": row[3],
            "metadata": json.loads(row[4]) if row[4] else None,
        }


def list_{entities}() -> List[Dict]:
    """List all {entities}."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, name, created_at, updated_at
            FROM {module}_{entities}
            ORDER BY created_at DESC
        """)
        
        return [
            {"id": r[0], "name": r[1], "created_at": r[2], "updated_at": r[3]}
            for r in cur.fetchall()
        ]


def update_{entity}(id: int, **kwargs) -> Optional[Dict]:
    """Update {entity} fields."""
    if not kwargs:
        return get_{entity}(id)
    
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        
        # Build dynamic update
        fields = []
        values = []
        for key, value in kwargs.items():
            if key in ("name",):  # Allowed fields
                fields.append(f"{key} = ?")
                values.append(value)
        
        if not fields:
            return get_{entity}(id)
        
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(id)
        
        cur.execute(f"""
            UPDATE {module}_{entities}
            SET {", ".join(fields)}
            WHERE id = ?
        """, values)
        conn.commit()
        
        return get_{entity}(id)


def delete_{entity}(id: int) -> bool:
    """Delete {entity} by ID."""
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM {module}_{entities} WHERE id = ?", (id,))
        conn.commit()
        return cur.rowcount > 0
```

---

## Frontend Templates

### index.ts
```typescript
// {Module} module exports
export { {Module}Panel } from './components/{Module}Panel';
export { {Module}Page } from './pages/{Module}Page';
export { use{Module} } from './hooks/use{Module}';
export { {module}Api } from './services/{module}Api';
export type * from './types/{module}';
```

### services/{module}Api.ts
```typescript
import type { {Entity}, {Entity}Create, {Entity}Update } from '../types/{module}';

const BASE_URL = 'http://localhost:8000';

class {Module}ApiService {
  private baseUrl = `${BASE_URL}/api/{module}`;

  async list(): Promise<{Entity}[]> {
    const response = await fetch(this.baseUrl);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async get(id: number): Promise<{Entity}> {
    const response = await fetch(`${this.baseUrl}/${id}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async create(data: {Entity}Create): Promise<{Entity}> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async update(id: number, data: {Entity}Update): Promise<{Entity}> {
    const response = await fetch(`${this.baseUrl}/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
  }

  async delete(id: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/${id}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
  }
}

export const {module}Api = new {Module}ApiService();
```

### types/{module}.ts
```typescript
export interface {Entity} {
  id: number;
  name: string;
  created_at: string;
  updated_at?: string;
  metadata?: Record<string, unknown>;
}

export interface {Entity}Create {
  name: string;
}

export interface {Entity}Update {
  name?: string;
}
```

### hooks/use{Module}.ts
```typescript
import { useState, useEffect, useCallback } from 'react';
import { {module}Api } from '../services/{module}Api';
import type { {Entity} } from '../types/{module}';

export function use{Module}() {
  const [items, setItems] = useState<{Entity}[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await {module}Api.list();
      setItems(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { items, loading, error, refresh };
}
```

### components/{Module}Panel.tsx
```tsx
import { use{Module} } from '../hooks/use{Module}';
import './{Module}Panel.css';

export function {Module}Panel() {
  const { items, loading, error, refresh } = use{Module}();

  if (loading) return <div className="{module}-panel loading">Loading...</div>;
  if (error) return <div className="{module}-panel error">Error: {error}</div>;

  return (
    <div className="{module}-panel">
      <div className="{module}-header">
        <h2>{Module}</h2>
        <button onClick={refresh}>Refresh</button>
      </div>
      <div className="{module}-list">
        {items.map((item) => (
          <div key={item.id} className="{module}-item">
            <span>{item.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### components/{Module}Panel.css
```css
.{module}-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 1rem;
}

.{module}-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.{module}-list {
  flex: 1;
  overflow-y: auto;
}

.{module}-item {
  padding: 0.75rem;
  border-bottom: 1px solid var(--border-color, #e0e0e0);
}

.{module}-panel.loading,
.{module}-panel.error {
  display: flex;
  align-items: center;
  justify-content: center;
}
```

### pages/{Module}Page.tsx
```tsx
import { {Module}Panel } from '../components/{Module}Panel';

export function {Module}Page() {
  return (
    <div className="{module}-page">
      <{Module}Panel />
    </div>
  );
}
```

---

## README.md Template

````markdown
# {Module} Module

{One-line description}

---

## Description

{Expanded description of what this module does and why it exists.}

---

## Architecture

<!-- ARCHITECTURE:{module} -->
### Directory Structure

```
{module}/
├── api.py           # FastAPI endpoints
├── schema.py        # SQLite tables
└── README.md        # This file
```

### API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/{module}` | List all {entities} |
| POST | `/api/{module}` | Create {entity} |
| GET | `/api/{module}/{id}` | Get {entity} by ID |
| PUT | `/api/{module}/{id}` | Update {entity} |
| DELETE | `/api/{module}/{id}` | Delete {entity} |

### Database Schema

| Table | Purpose |
|-------|---------|
| `{module}_{entities}` | Main entity storage |
<!-- /ARCHITECTURE:{module} -->

---

## Roadmap

<!-- ROADMAP:{module} -->
### Ready for contributors
- [ ] **Feature 1** — Description
- [ ] **Feature 2** — Description

### Starter tasks
- [ ] Add validation
- [ ] Add search/filtering
<!-- /ROADMAP:{module} -->

---

## Changelog

<!-- CHANGELOG:{module} -->
### {date}
- Initial module creation
<!-- /CHANGELOG:{module} -->
````

---

## Scaffold Checklist

When creating a new module `{name}`:

### Backend
- [ ] Create `/{name}/__init__.py` with router export
- [ ] Create `/{name}/api.py` with `APIRouter(prefix="/api/{name}")`
- [ ] Create `/{name}/schema.py` with `init_{name}_tables()` + CRUD
- [ ] Create `/{name}/README.md` with markers

### Frontend  
- [ ] Create `/frontend/src/modules/{name}/index.ts`
- [ ] Create `/frontend/src/modules/{name}/components/{Name}Panel.tsx`
- [ ] Create `/frontend/src/modules/{name}/components/{Name}Panel.css`
- [ ] Create `/frontend/src/modules/{name}/pages/{Name}Page.tsx`
- [ ] Create `/frontend/src/modules/{name}/services/{name}Api.ts`
- [ ] Create `/frontend/src/modules/{name}/types/{name}.ts`
- [ ] Create `/frontend/src/modules/{name}/hooks/use{Name}.ts`

### Registration
- [ ] Add `from {name} import router as {name}_router` to `scripts/server.py`
- [ ] Add `app.include_router({name}_router)` to `scripts/server.py`

### Verification
- [ ] Server starts without errors
- [ ] `GET /api/{name}` returns `[]`
- [ ] Frontend component renders

---

## Naming Conventions

| Context | Convention | Example |
|---------|------------|---------|
| Module folder | lowercase | `marketplace/` |
| Python files | snake_case | `api.py`, `schema.py` |
| DB tables | snake_case plural | `marketplace_listings` |
| API prefix | lowercase | `/api/marketplace` |
| Router tags | lowercase | `tags=["marketplace"]` |
| TS folder | lowercase | `modules/marketplace/` |
| TS components | PascalCase | `MarketplacePanel.tsx` |
| TS hooks | camelCase | `useMarketplace.ts` |
| TS services | camelCase | `marketplaceApi.ts` |
| CSS classes | kebab-case | `.marketplace-panel` |

---

## Questions to Ask

Before scaffolding, gather:

1. **Module name**: What's it called? (e.g., `marketplace`, `interp`, `analytics`)
2. **Primary entity**: What does it manage? (e.g., `listing`, `test`, `metric`)
3. **Key fields**: What data does each entity have?
4. **Relationships**: Does it reference other modules? (e.g., user_id, convo_id)
5. **Special features**: WebSockets? File uploads? Background jobs?
