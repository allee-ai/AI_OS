# 🎯 Agent Model Recommendations

Quick reference for which model to use with each agent profile.

---

## Cost vs Capability Matrix

| Model | Cost (per 1M tokens) | Best For | Avoid For |
|-------|---------------------|----------|-----------|
| **GPT-4o-mini** | ~$0.15 | Templated tasks, scaffolding, sync checks | Complex debugging, architecture |
| **GPT-4o** | ~$2.50 | Most coding tasks, refactoring, tests | Deep architecture, novel problems |
| **Claude Sonnet** | ~$3.00 | Code review, debugging, type inference | Overkill for simple tasks |
| **Claude Opus** | ~$15.00 | Architecture, research, complex reasoning | Routine tasks (burning money) |
| **Gemini 1.5 Pro** | ~$1.25 | Long context, codebase analysis | Real-time iteration |
| **Gemini 1.5 Flash** | ~$0.075 | Bulk processing, simple transforms | Anything requiring reasoning |

---

## Agent → Model Mapping

### 🧱 Module Agent (`module.agent.md`)
| Task | Model | Why |
|------|-------|-----|
| Scaffold new module | **GPT-4o-mini** | Pure template filling |
| Decide module boundaries | **Claude Opus** | Architectural judgment |
| Generate CRUD operations | **GPT-4o-mini** | Mechanical pattern |

### 🔗 Sync Agent (`sync.agent.md`)
| Task | Model | Why |
|------|-------|-----|
| Sync check (report only) | **GPT-4o-mini** | Pattern matching |
| Generate missing methods | **GPT-4o** | Needs context awareness |
| Complex type conversion | **Claude Sonnet** | Edge cases in types |

### 🔧 Fix Agent (future)
| Task | Model | Why |
|------|-------|-----|
| Trace obvious error | **GPT-4o** | Stack trace analysis |
| Debug cross-module issue | **Claude Sonnet** | Multi-file reasoning |
| Root cause + architecture fix | **Claude Opus** | Deep system understanding |

### 📋 Changelog Agent (future)
| Task | Model | Why |
|------|-------|-----|
| Format git diff to entry | **GPT-4o-mini** | Template + extraction |
| Categorize changes | **GPT-4o-mini** | Simple classification |
| Write summary narrative | **GPT-4o** | Needs coherent prose |

### 🧪 Test Agent (future)
| Task | Model | Why |
|------|-------|-----|
| Generate regression test | **GPT-4o** | Needs to understand the bug |
| Scaffold test file | **GPT-4o-mini** | Template |
| Design test strategy | **Claude Sonnet** | Edge case thinking |

### 🏗️ Refactor Agent (future)
| Task | Model | Why |
|------|-------|-----|
| Rename + update imports | **GPT-4o-mini** | Find/replace with verification |
| Safe multi-file move | **GPT-4o** | Dependency tracking |
| Architecture refactor | **Claude Opus** | System-wide implications |

### 📚 Docs Agent (`docs.agent.md`)
| Task | Model | Why |
|------|-------|-----|
| Sync README markers | **GPT-4o-mini** | Copy between files |
| Write new documentation | **GPT-4o** | Clear technical prose |
| Architecture documentation | **Claude Sonnet** | Accurate mental model |

### 🔮 Vision Agent (`VISION.agent.md`)
| Task | Model | Why |
|------|-------|-----|
| Codebase assessment | **Claude Opus** | Deep reasoning required |
| Prioritization | **Claude Opus** | Strategic thinking |
| Quick status check | **GPT-4o** | Sufficient for summaries |

### 🔬 Research Agent (future)
| Task | Model | Why |
|------|-------|-----|
| Format results for Discord | **GPT-4o-mini** | Template |
| Analyze experiment results | **Claude Opus** | Scientific reasoning |
| Literature comparison | **Gemini 1.5 Pro** | Long context for papers |

---

## Decision Flowchart

```
START
  │
  ├─► Is this a template/scaffold task?
  │     YES → GPT-4o-mini ($0.15/1M)
  │
  ├─► Is this find/replace or sync check?
  │     YES → GPT-4o-mini ($0.15/1M)
  │
  ├─► Is this writing code that needs context?
  │     YES → GPT-4o ($2.50/1M)
  │
  ├─► Is this debugging across multiple files?
  │     YES → Claude Sonnet ($3/1M)
  │
  ├─► Is this architecture or deep reasoning?
  │     YES → Claude Opus ($15/1M)
  │
  ├─► Is this processing a huge codebase/paper?
  │     YES → Gemini 1.5 Pro ($1.25/1M)
  │
  └─► Default → GPT-4o (best cost/capability balance)
```

---

## Cost Optimization Strategy

### Daily Development (80% of work)
- **GPT-4o-mini** for scaffolding, sync checks, changelogs
- **GPT-4o** for actual code changes, debugging
- **Estimated**: ~$1-3/day

### Weekly Architecture (15% of work)
- **Claude Sonnet** for code review, complex debugging
- **Claude Opus** for vision assessments, major decisions
- **Estimated**: ~$5-10/week

### Monthly Research (5% of work)
- **Claude Opus** for paper writing, theory development
- **Gemini 1.5 Pro** for literature review
- **Estimated**: ~$10-20/month

### Total: ~$30-60/month instead of ~$200+/month using Opus for everything

---

## Model-Specific Tips

### GPT-4o-mini
- Give explicit file paths
- Use numbered steps
- Provide examples of expected output format
- Don't ask it to "figure out" structure

### GPT-4o
- Can handle ambiguity better
- Good at following existing patterns in codebase
- Still benefits from explicit context

### Claude Sonnet
- Excellent at code review
- Good at catching edge cases
- Sometimes over-engineers simple solutions

### Claude Opus
- Reserve for genuinely hard problems
- Best for "what should we build" not "how do we build it"
- Worth it for decisions that compound (architecture, strategy)

### Gemini 1.5 Pro
- Unmatched context window (1M+ tokens)
- Use for "analyze entire codebase" tasks
- Slower than others for iteration

---

## When to Escalate

**Mini → 4o**: When the model keeps making the same mistake or missing context

**4o → Sonnet**: When debugging requires understanding subtle interactions

**Sonnet → Opus**: When you need to make a decision that affects architecture

**Any → You (human)**: When the model is confident but wrong twice in a row
