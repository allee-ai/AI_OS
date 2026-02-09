# AI_OS vs SOAR: Architectural Comparison

**February 2026**

---

## Summary

**SOAR** is a symbolic cognitive architecture from the 1980s built on production rules. **AI_OS** is a local OS extension for LLMs. Both aim for persistent, autonomous agents but differ fundamentally in one key aspect:

**SOAR**: The model controls its own perception (can modify working memory)  
**AI_OS**: The model cannot control its perception (reads supplied state)

This document explores what that difference means in practice.

---

## 1. The Core Difference: Perception Control

### Traditional Architectures

SOAR, ACT-R, and classical cognitive architectures share a pattern:

```
Working Memory (WM) ←─┐
        ↓              │
    Rule Engine        │
        ↓              │
    Modify WM ─────────┘
```

The model can add, remove, or modify its own state representation. In principle, a rule could rewrite "I am Agent" to "I am User."

### AI_OS

```
External Reality (Feeds)
        ↓
   Subconscious (Trusted Layer)
        ↓
   Assembled Context (Read-Only)
        ↓
   LLM Generation
        ↓
   Output (No feedback to Context)
```

The model cannot:
- Modify its identity (supplied by Identity thread)
- Choose what it remembers (supplied by scoring)
- Override who the user is (supplied by profiles)

### Why This Matters

This isn't just a security feature. Humans work within supplied reality too—you can't decide you're the other person in a conversation. Your nervous system supplies your proprioception, memories, and position in space. AI_OS implements this constraint architecturally.

---

## 2. Computational Approach

| Dimension | SOAR | AI_OS |
|-----------|------|-------|
| **Base System** | Production rule engine | Transformer language model |
| **Knowledge** | Symbolic rules + working memory | Profile facts (L1/L2/L3) + embeddings |
| **Cognitive Model** | Unified reasoner | 7 specialized threads |
| **Reasoning** | Forward/backward chaining | Next-token prediction + structured context |
| **Learning** | Chunking (rule compilation) | Hebbian graph + consolidation |
| **Decisions** | Conflict resolution | LLM generation over supplied state |

### SOAR's Cycle
```
Perception → Working Memory → Rule Matching → Operator Selection → Action
```

### AI_OS's Cycle
```
Feeds → Subconscious (score threads) → Context Assembly → LLM → Action/State Update
```

---

## 3. State Representation

### SOAR: Working Memory + Long-Term Memory

- **Working Memory**: Symbolic graph (e.g., `(block B1 ^color red ^on B2)`)
- **Long-Term Memory**: Production rules
- **Episodic Memory**: Temporal sequences
- **Semantic Memory**: Factual knowledge

### AI_OS: Thread-Based State

Seven threads answer fundamental questions:

| Thread | Answers | Storage |
|--------|---------|---------|
| **Identity** | WHO? | Profile facts: self, users, relationships |
| **Philosophy** | WHY? | Profile facts: values, beliefs, ethics |
| **Log** | WHEN? | Timestamped events |
| **Form** | WHAT can happen? | Tool definitions, capabilities |
| **Reflex** | HOW fast? | Pattern → response mappings |
| **Linking Core** | WHERE in attention? | Concept graph, spread activation |
| **Subconscious** | Orchestrator | Assembles context |

Each thread uses a common pattern:
- `profiles` table: Entities
- `profile_facts` table: Key-value with L1/L2/L3 hierarchical detail
- Ground truth: Model reads but cannot modify

**Key difference**: SOAR's working memory is mutable by rules. AI_OS's state is read-only to the model.

---

## 4. Memory & Learning

| Type | SOAR | AI_OS |
|------|------|-------|
| **Short-Term** | Working Memory (~7 chunks) | Temp Memory (pending consolidation) |
| **Procedural** | Production rules | Reflex patterns |
| **Declarative** | Semantic/Episodic Memory | Identity/Philosophy facts |
| **Event** | Episodic snapshots | Log thread |
| **Attention** | Implicit (rule salience) | Explicit (Linking Core) |

### Learning Mechanisms

**SOAR: Chunking**
- Impasse occurs → subgoal created → solution compiled into new rule
- Purely symbolic

**AI_OS: Consolidation Loop**
- Facts extracted to temp_memory
- Scored by embedding similarity + spread activation
- Routed to Identity or Philosophy thread
- Hebbian links strengthened
- Model weights unchanged

---

## 5. Attention

**SOAR**: Implicit through rule salience. Working memory limited to ~7 elements. No explicit relevance scoring.

**AI_OS**: Explicit Linking Core thread.
- Spread activation through concept graph
- Embedding similarity via nomic-embed-text
- Co-occurrence scoring
- Weighted fusion: 50% embedding + 30% co-occurrence + 20% spread + 10% keywords

Token budget enforced:
- L1: ~10 tokens per fact
- L2: ~50 tokens per fact
- L3: ~200 tokens per fact

---

## 6. Modularity

### SOAR: Monolithic
- Core: Working memory + rule engine
- Modules share working memory
- Tightly coupled

### AI_OS: Loose Threads
Each thread is independent:
```
agent/threads/my_domain/
├── schema.py      # Database tables
├── adapter.py     # ThreadInterface
├── api.py         # FastAPI router
└── README.md

frontend/src/modules/threads/my_domain/
├── Viewer.tsx
└── index.ts
```

Fault-isolated: one thread failing doesn't crash others.

**Adding capabilities**: SOAR adds decision rules. AI_OS adds perceptual domains (what the model can see).

---

## 7. Transparency

**SOAR**: Full rule trace. Every decision cycle logged. Deterministic and inspectable.

**AI_OS**: 
- Context assembly is transparent (SQL queries, scoring formulas)
- LLM generation is opaque (transformer activations)
- Mitigation: Structured state constrains behavior. Identity isn't in the conversation, so prompt injection can't override it.

---

## 8. Use Cases

### SOAR Strengths
- Formal domains (chess, logistics, diagnosis)
- Cognitive modeling research
- Safety-critical systems requiring provable correctness

### AI_OS Strengths
- Natural language tasks (chat, email, writing)
- Personal autonomy (assistant with persistent memory)
- Rapid prototyping (no rule engineering)

### Hybrid Potential
Use SOAR for critical decision logic, AI_OS for language understanding and generation.

---

## 9. Philosophical Differences

**SOAR**: Unified theory of cognition. One architecture for all cognitive functions. The system can inspect and modify its own rules.

**AI_OS**: Specialized threads for different cognitive functions. The model cannot modify its perception—only reason within it. Uses cognitive science as design patterns, not as claims about replicating human cognition.

---

## 10. What AI_OS Contributes

1. **Perception-cognition separation** — Model cannot override supplied reality
2. **Thread architecture** — 7 threads answering WHO/WHAT/WHERE/WHEN/WHY/HOW
3. **Profile facts pattern** — Extensible ground truth domains
4. **Hierarchical Experiential Attention** — L1/L2/L3 fact compression
5. **Hebbian concept graph** — Online learning without weight updates
6. **Fault-isolated threads** — One failure doesn't cascade

---

## 11. Conclusion

SOAR and AI_OS solve different problems:

- **SOAR**: Symbolic AI with deterministic, explainable decisions
- **AI_OS**: Neural AI with persistent identity and constrained perception

They're complementary. SOAR offers provable correctness. AI_OS offers linguistic fluency and the constraint that the model cannot override its own grounding.

The key insight: traditional architectures let intelligence control its perception. AI_OS enforces the human constraint—you work within supplied reality, you don't choose it.

---

## Further Reading

### SOAR
- Laird, J.E. (2012). *The Soar Cognitive Architecture*. MIT Press.
- Newell, A. (1990). *Unified Theories of Cognition*. Harvard University Press.
- [soar.eecs.umich.edu](https://soar.eecs.umich.edu/)

### AI_OS
- [RESEARCH_PAPER.md](RESEARCH_PAPER.md)
- [research2.md](research2.md)
- [ARCHITECTURE.md](ARCHITECTURE.md)

---

**Last Updated:** February 7, 2026
