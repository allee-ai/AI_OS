# Linking Core Thread Agent

**Read `stack.md` first for universal patterns.**

## Purpose

Linking Core contains **algorithms**, not data. It defines how threads connect to each other through spread activation and concept linking.

## Contract: metadata vs data

Your adapter MUST implement:

```python
def get_metadata(self) -> dict:
    """Thread structure - thinking about thinking."""
    return {
        "files": ["adapter.py", "README.md"],
        "tables": ["concept_links", "activation_cache"],  # future
        "modules": ["spread_activation", "relevance_scoring"],
        "algorithms": ["spread", "hebbian_update", "route_query"],
        "params": {"decay": 0.5, "threshold": 0.1, "max_depth": 3},
        "db_path": "/data/db/state.db"
    }

def get_data(self, level: int = 2) -> list:
    """Thread content - concept links (currently in README)."""
    # Doc-only thread - returns README content or empty
    return []  # Future: actual link weights from DB
```

**Key question:** "How does information flow between threads?"

## Unique Nature: Documentation-Only

Unlike other threads:
- **No runtime data** - algorithms stored in README
- **Health check** - passes if README.md exists
- **Frontend display** - shows README content, not data table

## Core Algorithm: Spread Activation

When a concept activates, energy flows to linked concepts:

```
A_new(c) = A_base(c) + Σ [A(neighbor) × weight(edge)]
```

**Where:**
- `A_new(c)` = updated activation of concept c
- `A_base(c)` = base activation (from direct mention)
- `Σ` = sum over all linked concepts
- `A(neighbor)` = activation of linked concept
- `weight(edge)` = strength of link (0.0-1.0)

### Example Flow

When user says "music" (weight 1.0):
```
music [1.0] → creativity [0.8] → identity
music [1.0] → relaxation [0.6] → philosophy
music [1.0] → evening [0.4] → temporal patterns
```

## Database

### Tables (Future Implementation)

**`concept_links`** - Weighted connections
```sql
source TEXT,                    -- "music"
target TEXT,                    -- "creativity"
weight REAL,                    -- 0.8
thread TEXT,                    -- "identity" (where this link lives)
PRIMARY KEY (source, target)
```

**`activation_cache`** - Current activation levels
```sql
concept TEXT PRIMARY KEY,       -- "music"
activation REAL,                -- 1.0
last_updated TEXT               -- timestamp
```

## Adapter

**Location:** `Nola/threads/linking_core/adapter.py`

### Key Functions

```python
from Nola.threads.linking_core.adapter import LinkingCoreAdapter

adapter = LinkingCoreAdapter()

# Check health (README exists?)
health = adapter.health()  # {"status": "ok", "message": "Algorithms documented..."}

# Future: Spread activation
def spread(concept, initial_activation=1.0, decay=0.5, max_depth=3):
    """Propagate activation through concept network."""
    activations = {concept: initial_activation}
    frontier = [concept]
    
    for depth in range(max_depth):
        next_frontier = []
        for node in frontier:
            for neighbor, weight in get_neighbors(node):
                spread_value = activations[node] * weight * decay
                if spread_value > 0.1:  # threshold
                    activations[neighbor] = activations.get(neighbor, 0) + spread_value
                    next_frontier.append(neighbor)
        frontier = next_frontier
    
    return activations
```

## Code Map

### Backend (Python/FastAPI)

| File | Purpose |
|------|---------|
| `Nola/threads/linking_core/adapter.py` | Core adapter - `health()` (README-based) |
| `Nola/threads/linking_core/__init__.py` | Public API |
| `Nola/threads/linking_core/README.md` | **THE DATA** - algorithms documented here |
| `Nola/react-chat-app/backend/api/introspection.py` | REST endpoints (lines 647-710) |
| `Nola/threads/schema.py` | DB schema (future: concept_links table) |

### Backend Endpoints

| Endpoint | Method | Line | Purpose |
|----------|--------|------|---------|
| `/api/introspection/threads/linking_core` | GET | 668 | Returns README status |
| `/api/introspection/threads/linking_core/readme` | GET | 647 | README content |

### Frontend (React/TypeScript)

| File | Purpose |
|------|---------|
| `Nola/react-chat-app/frontend/src/pages/ThreadsPage.tsx` | Thread viewer |
| `Nola/react-chat-app/frontend/src/pages/ThreadsPage.css` | Styles |
| `Nola/react-chat-app/frontend/src/services/introspectionService.ts` | API client |

### Frontend Functions (ThreadsPage.tsx)

| Function | Line | Purpose |
|----------|------|---------|
| `fetchReadme()` | ~200 | Load README for doc threads |
| `renderReadmeView()` | ~420 | Render markdown content |

### Special Frontend Handling

```typescript
// ThreadsPage.tsx - linking_core shows README, not data table
const DOC_THREADS = new Set(['linking_core']);

if (DOC_THREADS.has(selectedThread)) {
  renderReadmeView();   // Show README.md content
} else {
  renderModuleView();   // Show data table
}
```

### Future Database Tables

```
concept_links      - Weighted connections (source, target, weight)
activation_cache   - Current activation levels (concept, activation)
```

## Applications

### 1. Fact Relevance Scoring

Score any content against identity/philosophy facts:

```python
def score_relevance(content, facts):
    """How relevant is content to weighted facts?"""
    scores = {}
    
    for fact in facts:
        # Embed both (or use keyword overlap)
        similarity = embed_similarity(content, fact.data)
        weighted_score = similarity * fact.weight
        scores[fact.key] = weighted_score
    
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)
```

### 2. Thread Retrieval Routing

Decide which thread to query:

```python
def route_query(user_input):
    """Which threads should respond to this query?"""
    activations = spread_from_input(user_input)
    
    # Map concepts to threads
    thread_scores = {
        "identity": sum(a for c, a in activations if c in IDENTITY_CONCEPTS),
        "philosophy": sum(a for c, a in activations if c in PHILOSOPHY_CONCEPTS),
        "reflex": sum(a for c, a in activations if c in REFLEX_CONCEPTS),
        "form": sum(a for c, a in activations if c in FORM_CONCEPTS),
    }
    
    # Return threads above threshold
    return [t for t, s in thread_scores.items() if s > 0.3]
```

### 3. Memory Consolidation

During idle time, strengthen frequently co-activated concepts:

```python
def hebbian_update(activations, learning_rate=0.01):
    """Neurons that fire together wire together."""
    for c1, a1 in activations.items():
        for c2, a2 in activations.items():
            if c1 != c2:
                # Strengthen link proportional to co-activation
                delta = learning_rate * a1 * a2
                update_link_weight(c1, c2, delta)
```

## Architecture Diagram

```
          User Input
               ↓
        ┌──────────────┐
        │ Linking Core │
        │  (Routing)   │
        └──────────────┘
               ↓
    ┌──────────┼──────────┐
    ↓          ↓          ↓
┌────────┐┌────────┐┌──────────┐
│Identity││Philosophy││  Form   │
│(who)   ││ (why)   ││ (what)  │
└────────┘└────────┘└──────────┘
    ↓          ↓          ↓
    └──────────┼──────────┘
               ↓
        ┌──────────────┐
        │     Log      │
        │  (temporal)  │
        └──────────────┘
```

## Conflicts to Watch

| If you're changing... | Check with... |
|----------------------|---------------|
| Concept categories | Identity (what concepts matter) |
| Link weights | Philosophy (value-based priorities) |
| Activation thresholds | Reflex (speed requirements) |
| Retrieval logic | All threads (they depend on routing) |

## README

Full documentation: `Nola/threads/linking_core/README.md`
