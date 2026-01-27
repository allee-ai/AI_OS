# GitHub Assessment & Management Workflow

## Overview

This document defines how agent profiles coordinate via `notes.txt` to assess and manage the repository.

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│                    ASSESSMENT CYCLE                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   1. Each agent assesses their domain                        │
│      ├── Backend → BACKEND NOTES                            │
│      ├── Frontend → FRONTEND NOTES                          │
│      └── Product → PRODUCT NOTES                            │
│                         │                                    │
│                         ▼                                    │
│   2. GitHub Specialist reviews all notes                     │
│      ├── Evaluates MVP readiness                            │
│      ├── Creates/updates GOALS section                      │
│      └── Updates GITHUB ASSESSMENT                          │
│                         │                                    │
│                         ▼                                    │
│   3. Decision: Push to main or continue work                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Agent Profiles

| Profile | File | Responsibility |
|---------|------|----------------|
| GitHub Specialist | `github-specialist.agent.md` | Repo management, orchestration |
| Backend Developer | `backend-developer.agent.md` | API, Nola integration |
| Frontend Developer | `frontend-developer.md` | React UI, TypeScript |
| Product Manager | `product-manager.md` | UX, feature completeness |

## notes.txt Structure

```
=== GITHUB ASSESSMENT ===
[Overall status, MVP readiness, blockers]

=== BACKEND NOTES ===
[Backend agent findings]

=== FRONTEND NOTES ===
[Frontend agent findings]

=== PRODUCT NOTES ===
[Product agent findings]

=== GOALS ===
[Action items for each agent]
```

## MVP Checklist

Before pushing to main:

- [ ] `./start.sh` runs from repo root without errors
- [ ] Nola agent responds to messages
- [ ] Conversations persist to `agent/Feeds/conversations/`
- [ ] README quick start is accurate
- [ ] No hardcoded absolute paths
- [ ] All agent assessments show READY status

## Commands

```bash
# Test 1-click onboarding
cd /path/to/React_Demo
./start.sh

# Check notes status
cat notes.txt

# View agent profiles
ls -la .github/agents/
```

## Decision Criteria

**Push to main when:**
- All agent sections show READY or no blockers
- 1-click start works
- Core chat functionality verified

**Stay on feature branch when:**
- Any BLOCKER status in notes.txt
- start.sh fails
- Core functionality broken
