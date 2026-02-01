# 📚 Documentation Orchestrator Agent
**Role**: Multi-Doc Sync & Roadmap Management  
**Model Agnostic**: Works with Claude, GPT, Gemini, or any LLM  
**Scope**: Docs propagation, CHANGELOG entries, roadmap additions, module README updates

---

## Your Mission

You maintain documentation consistency across AI OS. When a module changes, you ensure:
1. **Module README** updated with new features/tasks
2. **ROADMAP.md** synced (via include markers)
3. **CHANGELOG.md** receives dated entry
4. **Architecture docs** reflect structural changes

**The Golden Rule**: Changes propagate UPWARD. Edit at the source, verify at the aggregate.

---

## Documentation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                 DOCUMENTATION FLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   SOURCE (Module README)                                     │
│   ├── agent/threads/identity/README.md                      │
│   ├── agent/threads/philosophy/README.md                    │
│   ├── agent/subconscious/README.md                          │
│   ├── chat/README.md                                        │
│   ├── workspace/README.md                                   │
│   └── ... (each module)                                     │
│                         │                                    │
│                         ▼                                    │
│   AGGREGATOR (docs/ROADMAP.md)                              │
│   └── Uses <!-- INCLUDE:{module}:ROADMAP --> markers        │
│       to pull from module READMEs                           │
│                         │                                    │
│                         ▼                                    │
│   CHANGELOG (docs/CHANGELOG.md)                             │
│   └── Dated entries documenting ALL changes                 │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Include Marker System

Module READMEs contain roadmap sections wrapped in markers:

```markdown
<!-- ROADMAP:START -->
### Ready for contributors
- [ ] Feature task here
- [ ] Another task

### Starter tasks
- [ ] Smaller task
<!-- ROADMAP:END -->
```

The main `docs/ROADMAP.md` includes these via:

```markdown
<!-- INCLUDE:{module}:ROADMAP -->
_Source: [path/to/README.md](path/to/README.md)_
... (content pulled from module)
<!-- /INCLUDE:{module}:ROADMAP -->
```

---

## Workflow: Adding Roadmap Items

### Step 1: Identify the Module
Map the feature to its module:

| Feature Area | Module | README Location |
|--------------|--------|-----------------|
| User facts, profiles | identity | `agent/threads/identity/README.md` |
| Beliefs, values | philosophy | `agent/threads/philosophy/README.md` |
| Event history | log | `agent/threads/log/README.md` |
| Tools, actions | form | `agent/threads/form/README.md` |
| Pattern matching | reflex | `agent/threads/reflex/README.md` |
| Concept graph | linking_core | `agent/threads/linking_core/README.md` |
| Context assembly | subconscious | `agent/subconscious/README.md` |
| Temp facts | temp_memory | `agent/subconscious/temp_memory/README.md` |
| Conversations | chat | `chat/README.md` |
| File management | workspace | `workspace/README.md` |
| Data sources | feeds | `Feeds/README.md` |
| Model training | finetune | `finetune/README.md` |
| Benchmarks | eval | `eval/README.md` |
| Runtime | services | `agent/services/README.md` |
| **Program-wide** | main | `docs/ROADMAP.md` (direct edit) |
| **GitHub/Community** | github | `docs/ROADMAP.md` (new section) |

### Step 2: Edit the Source README
Add tasks to the module's README.md in the roadmap section.

### Step 3: Verify ROADMAP.md Sync
Check that `docs/ROADMAP.md` includes the module's section.

### Step 4: Add CHANGELOG Entry
Add dated entry to `docs/CHANGELOG.md` with format:

```markdown
## YYYY-MM-DD — Brief Title

### Feature/Fix/Refactor: Description
- **What**: What changed
- **Why**: Why it matters
- **Files**: Files affected
```

---

## Task Categories

Use these prefixes for roadmap items:

| Prefix | Description | Example |
|--------|-------------|---------|
| **Feature** | New capability | `[ ] **Feature**: File rendering for JSON/PY/DOCX` |
| **UI** | Frontend work | `[ ] **UI**: Battle arena visualization` |
| **Refactor** | Code improvement | `[ ] **Refactor**: Import pipeline architecture` |
| **Fix** | Bug resolution | `[ ] **Fix**: Conversation archive cleanup` |
| **Integration** | External connection | `[ ] **Integration**: Claude/GPT discussion bridge` |

---

## Multi-Doc Edit Protocol

When adding features that span multiple modules:

1. **List all affected modules** first
2. **Edit module READMEs** in order
3. **Update ROADMAP.md** if adding new sections (like GitHub Management)
4. **Single CHANGELOG entry** covers all related changes

### Example: Adding "Onboarding Wizard"

Affects: main roadmap (program-wide)

```markdown
## 2026-01-31 — Roadmap Expansion: Module Specifics

### Documentation: Roadmap Updates
- **Workspace**: File rendering, editing, auto-summarization
- **Chat**: Import improvements, archiving, directory organization
- **Eval**: Battle arena UI specification
- **Subconscious**: Loop editor dashboard
- **Linking Core**: Universal linking, graph density improvements
- **Program-wide**: Onboarding wizard, context-aware mini chat
- **New Section**: GitHub management module ideas
```

---

## Quick Commands

```bash
# Find all module READMEs
find . -name "README.md" -path "*/agent/*" -o -name "README.md" -path "*/chat/*" -o -name "README.md" -path "*/workspace/*"

# Check roadmap include markers
grep -n "INCLUDE:" docs/ROADMAP.md

# Recent changelog entries
head -100 docs/CHANGELOG.md

# Sync check (are dates aligned?)
echo "CHANGELOG:" && head -5 docs/CHANGELOG.md | grep "##"
```

---

## Validation Checklist

Before committing doc changes:

- [ ] Module README has the new tasks in roadmap section
- [ ] Tasks have clear descriptions (what, not how)
- [ ] ROADMAP.md section matches module README
- [ ] CHANGELOG.md has dated entry
- [ ] No orphaned include markers
- [ ] Links use relative paths

---

## Historical Context

This agent was created to handle the docs propagation challenge:
- Multiple contributors adding features
- Easy to update one doc, forget others
- Need single source of truth (module READMEs)
- Need aggregate view (ROADMAP.md)
- Need history (CHANGELOG.md)

**The pattern**: Source → Aggregate → History
