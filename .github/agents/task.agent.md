# 📋 Task — Initial Task Template
**Role**: Structure a task before any code is written. Fill this out, then hand to `@agent` or `@plan`.  
**Scope**: Any work item — feature, fix, refactor, new module, training data  
**Rule**: If a section is blank, the task isn't ready.

---

## Task Template

Copy and fill in every section. Leave nothing as "TBD."

```markdown
## Task: {clear, specific title}

### What
{One paragraph. What are you building or changing?}

### Why
{One paragraph. What user-facing or system-level problem does this solve?
If this is a refactor, what's broken or degraded about the current approach?}

### Where (Module Classification)

**Type**: {thread feature | top-level module | orchestrator | frontend-only | schema migration | training data | bug fix}

**Primary module**: {e.g., agent/threads/identity}
**Secondary files**: {list any other files that must change}

### Shape

{Describe the change at the file level:}

| File | Change | New or Edit |
|------|--------|-------------|
| `path/to/file.py` | {what changes} | {new / edit} |
| ... | ... | ... |

### Contract

{For each new or modified function/endpoint:}

**Backend**:
- `POST /api/{module}/{action}` — Input: `{fields}` → Output: `{fields}`
- `{function_name}(params) → return_type`

**Frontend**:
- `{ComponentName}` renders `{what}`
- `{serviceName}(params)` calls `{endpoint}`

### Files to Read First
{List every file you must understand before writing code:}
- `path/to/existing.py` — {why you need to read it}

### Blast Radius

**Scope**: {local | module | cross-module | system}

{If module or above: list what could break and how you'd know.}

### Breakpoints

{Pre-build checks from @ask. Answer each before writing code:}
- [ ] Does this already exist? → {answer}
- [ ] Does this cross a thread boundary? → {answer}
- [ ] What existing behavior could this break? → {answer}
- [ ] Can this be solved without new code? → {answer}

### Verification

{Exact commands or steps to confirm the task is done:}

```bash
# Endpoint works
curl -s http://localhost:8000/api/{module}/{endpoint} | python3 -m json.tool

# Frontend renders
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/{route}

# No errors
docker logs ai-os --tail 20 2>&1 | grep -i "error"
```

### Dependencies

{What must be true before this task can start?}
- [ ] {table X exists}
- [ ] {module Y is registered}
- [ ] {endpoint Z returns data}
```

---

## Quick Reference — Common Task Shapes

### New Thread Module
```
Files: schema.py → adapter.py → api.py → __init__.py → threads/__init__.py → server.py → frontend
Blast Radius: module
Read First: agent/threads/base.py, agent/threads/__init__.py, an existing thread for reference
```

### New Top-Level Module
```
Files: schema.py → api.py → __init__.py → server.py → frontend
Blast Radius: module
Read First: scripts/server.py, an existing module (chat/ or workspace/) for reference
```

### Add Field to Existing Thread
```
Files: schema.py (column) → adapter.py (expose) → api.py (endpoint) → frontend types → frontend render
Blast Radius: module
Read First: the thread's existing schema.py, migrations.py
```

### Bug Fix
```
Files: usually 1–2
Blast Radius: local
Read First: the file with the bug, plus its callers (grep for imports)
```

### Training Data
```
Files: {thread}/train.py → finetune/auto_generated/{name}.jsonl
Blast Radius: local
Read First: existing train.py for format, finetune/mlx_config.yaml for training config
```

---

## Usage

Fill out the template, then:
- Switch to `@plan` to validate the plan
- Switch to `@ask` to stress-test assumptions
- Switch to `@agent` to execute
