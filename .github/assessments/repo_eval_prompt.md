# AI OS Repository Evaluation Prompt

> **Usage:** Paste this entire prompt into a fresh conversation with Claude, GPT, Gemini, etc.  
> **Purpose:** Simulate what developers will see when they AI-evaluate the repo before investing time.

---

## The Prompt

```
I'm evaluating whether to invest time in this open-source project. Please analyze it critically and honestly — I want real assessment, not cheerleading.

**Repository:** https://github.com/allee-ai/AI_OS

**Evaluation criteria:**

### 1. Legitimacy Check
- Is this real working code or vaporware?
- Are the claims in the README backed by implementation?
- Any red flags (abandoned, over-promised, copy-paste from tutorials)?

### 2. Architecture Assessment
- Is there coherent design or is it spaghetti?
- Do the abstractions make sense?
- Would this be maintainable/extensible?

### 3. Claims vs. Reality
- What does it claim to do?
- What does it actually do (based on code)?
- Any overclaims or honest hedging?

### 4. Maturity & Completeness
- What's working vs. WIP vs. missing?
- Frontend/backend balance?
- Test coverage?
- Documentation quality?

### 5. Developer Experience
- Could I actually run this?
- Is onboarding clear?
- Are there obvious footguns?

### 6. Differentiation
- What's the actual value prop vs. LangChain/LlamaIndex/MemGPT/etc?
- Is there anything novel or is it reinventing wheels?

### 7. Red Flags
- Bus factor?
- Signs of abandonment?
- Questionable dependencies?
- Security concerns?

### 8. Bottom Line
- Would you recommend a developer spend a weekend trying this?
- What type of user would benefit most?
- What's the biggest risk of investing time here?

**Format:** Be direct. Use bullet points. If something is bad, say it's bad. I need honest signal, not politeness.
```

---

## What to Compare Across Models

After running with each model, note:

| Model | Overall Verdict | Key Strengths Identified | Key Weaknesses Identified | Unique Insight |
|-------|-----------------|-------------------------|---------------------------|----------------|
| Claude | | | | |
| GPT-4 | Early-stage but serious OS extension for local LLMs; worth a weekend for folks who care about identity/memory, not ideal as a generic production framework yet. | Real, non-trivial architecture (threads, subconscious, linking core) with concrete implementations of memory loops, identity, and Hebbian-inspired concept graph; good docs and tests for an indie project; honest about hypotheses vs. facts and clearly scoped roadmap. | Bus factor ~1 and bespoke architecture make long-term bet riskier; some advanced features (philosophy, reflex, dream) are still aspirational; patterns are different from mainstream LangChain/LlamaIndex. | Most interesting as a living experiment in structured local LLM tooling, not as "the one framework"; best used by people who want to tinker with identity/memory and are comfortable building on an opinionated, research-y base. |
| Gemini | Essential Study (Beta) | "Subconscious" Pattern correctly implemented; 3D "Neural Nebula" visualization proves underlying graph data; "Hebbian" claim validated by co-occurrence boosting logic. | Frontend complexity (React Three Fiber) raises barrier to entry; Graph rendering could hit performance limits; "Loops" are complex to debug. | Shift from "RAG wrapper" to "Weighted Graph Memory" is significant; Observability ("Glass Box") of *why* facts are retrieved is a major differentiator against black-box frameworks. |

### Questions to ask yourself after:
1. Did any model catch something the others missed?
2. Were there consistent criticisms across all models?
3. Did any model misunderstand the project fundamentally?
4. What would you fix based on consensus feedback?

---

## Follow-up Prompts

After initial assessment, try these:

### Deep Dive: Code Quality
```
Look at agent/subconscious/orchestrator.py and agent/threads/identity/adapter.py. 
Assess: code quality, error handling, edge cases, and whether the "HEA" and "thread" 
abstractions are well-implemented or cargo-culted.
```

### Deep Dive: Claims Verification
```
The README claims "Memory — Persistent across sessions, organized by relevance" 
and uses terms like "Hebbian learning" and "spread activation." 

Find the actual implementation of these. Is it real or just naming things 
after neuroscience concepts without substance?
```

### Deep Dive: Competitive Analysis
```
Compare this to:
- LangChain's memory modules
- MemGPT
- LlamaIndex's chat engines

What does AI OS do that these don't? What do they do better?
```

### Deep Dive: Enterprise Readiness
```
A utility company wants to add AI chat to their data analytics platform.
Requirements: local deployment (India data sovereignty), long conversation 
sessions, operator preference memory.

Would this project be a viable foundation? What's missing?
```

---

## Notes

- Run this **before** your public launch to catch issues
- Run it **periodically** after major updates
- Consider publishing interesting assessments to show transparency
- If all models agree something is broken, fix it before launch
