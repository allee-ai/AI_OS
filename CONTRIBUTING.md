# Contributing to Agent

Thanks for wanting to help build the future of personal AI. This project is open to everyone—coders, researchers, teachers, and people who just care about getting this right.

---

## For Everyone (No Code Required)

### Try It and Tell Us What Breaks
The most valuable contribution is honest feedback. Clone it, run `./start.sh`, and tell us:
- What confused you?
- What didn't work?
- What did you expect that didn't happen?

Open an issue with the label `feedback` or `bug`.

### Create Training Conversations
The agent learns from examples. You can help by having conversations that demonstrate:
- How she should handle personal questions
- How she should respond when she doesn't know something
- Edge cases (rude users, ambiguous requests, emotional situations)

See `finetune/README.md` for the format. Drop your examples in `finetune/auto_generated/`.

### Improve Documentation
Found a typo? Confusing explanation? Missing step? PRs for docs are always welcome. No code review needed—if it makes things clearer, we'll merge it.

---

## For Developers

### Quick Setup

```bash
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
./start.sh  # Installs everything, starts the app
```

The app runs at `http://localhost:5173`. Backend API at `http://localhost:8000`.

### Run Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

All tests should pass before submitting a PR.

### Find Something to Work On

**Good first issues:** [github.com/allee-ai/AI_OS/labels/good first issue](https://github.com/allee-ai/AI_OS/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)

**All open issues:** [github.com/allee-ai/AI_OS/issues](https://github.com/allee-ai/AI_OS/issues)

Or pick a role below and dive into that area.

---

## Contributor Roles

### 🎓 Teachers
Create conversations and scenario prompts to generate high-quality training data.

**What you'll do:**
- Write example conversations in JSONL format
- Annotate intent and expected behavior  
- Design edge cases and adversarial examples

**Start here:** `finetune/README.md`, `finetune/aios_finetune_data.jsonl`

---

### ⚙️ Backend (Python/FastAPI)
Maintain and extend the API layer.

**What you'll do:**
- Add new API endpoints
- Improve database operations
- Work on the Feeds system (integrations)
- Optimize performance

**Start here:** `scripts/server.py`, `agent/threads/`, `chat/`

**Good issues:** [label:backend](https://github.com/allee-ai/AI_OS/issues?q=is%3Aissue+is%3Aopen+label%3Abackend)

---

### 🎨 Frontend (React/TypeScript)
Improve the chat interface and visualization tools.

**What you'll do:**
- Build new UI components
- Improve accessibility and UX
- Add thread visualizations
- Implement the Reflex Builder UI

**Start here:** `frontend/src/`

**Good issues:** [label:frontend](https://github.com/allee-ai/AI_OS/issues?q=is%3Aissue+is%3Aopen+label%3Afrontend)

---

### 🧠 AI / Research Engineers
Work on model integration and cognitive architecture.

**What you'll do:**
- Experiment with different local models
- Improve the HEA (Hierarchical Experiential Attention) system
- Design fine-tuning pipelines
- Work on spread activation and memory consolidation

**Start here:** `agent/subconscious/`, `agent/threads/`, `docs/ARCHITECTURE.md`

**Good issues:** [label:architecture](https://github.com/allee-ai/AI_OS/issues?q=is%3Aissue+is%3Aopen+label%3Aarchitecture)

---

### 🔬 Cognitive / Neuro / Psych Experts
Advise on the theoretical foundations.

**What you'll do:**
- Review the HEA model against cognitive load theory
- Suggest improvements to state representation
- Help define metrics for behavioral consistency
- Validate the "thread as brain region" metaphor

**Start here:** `docs/RESEARCH_PAPER.md`, `docs/ARCHITECTURE.md`

---

## How to Submit

1. **Find an issue** — Labels like `backend`, `frontend`, `docs` indicate the area
2. **Fork the repo**
3. **Create a branch:** `git checkout -b my-feature`
4. **Make your changes**
5. **Run tests:** `.venv/bin/python -m pytest tests/ -v`
6. **Commit with a clear message:** `git commit -m "Add toast notifications for learned facts"`
7. **Push and open a PR to `main`**

Small, focused PRs are easier to review. If you're doing something big, open an issue first to discuss.

---

## Code Style

- **Python:** We use standard Python conventions. Run `ruff` if you have it.
- **TypeScript:** Standard React patterns. Functional components, hooks.
- **Commits:** Clear, descriptive messages. Present tense ("Add feature" not "Added feature").

---

## Questions?

- Open an issue with the `question` label
- Check `docs/ARCHITECTURE.md` for architecture context
- Read `docs/RESEARCH_PAPER.md` for the philosophy

---

*If you're here, you care about the future of AI being human-centered. That's enough qualification for me.*

