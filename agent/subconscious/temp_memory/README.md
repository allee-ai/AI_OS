# Temp Memory

Short-term fact storage before consolidation to long-term memory.

---

## Description

When you chat with the agent, it extracts facts from the conversation:
- "I like coffee" → stored as a temporary fact
- Facts get scored for importance
- High-confidence facts are promoted to permanent Identity/Philosophy threads

This is the "working memory" that processes before committing.

---

## Architecture

<!-- ARCHITECTURE:temp_memory -->
### Database Schema

```sql
CREATE TABLE temp_facts (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    timestamp TEXT,
    source TEXT DEFAULT 'conversation',
    session_id TEXT,
    consolidated INTEGER DEFAULT 0,
    score_json TEXT,
    hier_key TEXT,
    metadata_json TEXT,
    status TEXT DEFAULT 'pending',
    confidence_score REAL
)
```

### Fact Lifecycle

```
PENDING → PENDING_REVIEW → APPROVED → CONSOLIDATED
                ↓
            REJECTED
```

| Status | Meaning |
|--------|---------|
| pending | Awaiting scoring |
| pending_review | Low confidence, needs human approval |
| approved | Ready for consolidation |
| consolidated | Promoted to permanent storage |
| rejected | Discarded |

### Key Functions

| Function | Purpose |
|----------|---------|
| `add_fact()` | Store a new fact |
| `get_facts()` | Retrieve facts |
| `get_pending_review()` | Facts needing approval |
| `approve_fact()` / `reject_fact()` | Human triage |
| `mark_consolidated()` | Mark as promoted |
<!-- /ARCHITECTURE:temp_memory -->

---

## Roadmap

<!-- ROADMAP:temp_memory -->
### Extraction quality
- [ ] **Duplicate detection** — Flag facts that are semantically similar to existing ones before promotion (embedding similarity check)
- [ ] **Auto-categorization** — Suggest `hier_key` from text instead of requiring manual assignment
- [ ] **Extraction accuracy eval** — What % of extracted facts are actually correct? What % of important facts get missed? No ground truth benchmark exists
- [ ] **Batch review UI** — Approve/reject multiple pending facts at once

### Starter tasks
- [ ] Fact count by status in dashboard (pending/approved/promoted)
<!-- /ROADMAP:temp_memory -->

---

## Changelog

<!-- CHANGELOG:temp_memory -->
### 2026-03-05
- Fixed `no such column: status` crash: `_ensure_table()` reordered so `ALTER TABLE ADD COLUMN` migrations run before `CREATE INDEX` statements (index on `status` column was failing on stale DBs)
- `update_fact_status()` now calls `_ensure_table()` before acquiring a connection, guarding any caller against stale schema

### 2026-01-27
- Fixed log_event integration (correct parameter signature)
- Added regression tests in test_consolidation.py

### 2026-01-20
- Multi-status fact lifecycle
- Integration with unified_events timeline
<!-- /CHANGELOG:temp_memory -->
