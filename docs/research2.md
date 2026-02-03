# Cognitive Architecture for Autonomous Systems: Layer-Aligned State Injection in Small Language Models

## Abstract

We present a cognitive architecture that enables autonomous operation of small language models (1-2B parameters) by externalizing context reconstruction into structured state threads. We hypothesize that transformer layers perform hierarchical computation—entity binding (layers 2-6), relational positioning (6-10), causal reasoning (8-12), and logical inference (12+)—and that pre-structured state can bypass early-layer computation, effectively donating those layers to reasoning capacity. Our architecture implements six specialized threads (Identity, Log, Form, Philosophy, Reflex, Linking Core) that map to specific layer ranges and cognitive functions. We propose that programmatically-generated state blocks, being statistically perfect (zero token variance), enable earlier concept anchoring than natural language system prompts. This separation of contextual/structural self-awareness from the reasoning model enables a 1.2B parameter "executive" to achieve autonomous operation—including self-monitoring, learning-rate adjustment, and goal-directed behavior—by offloading context reconstruction to the architecture. We outline 12 empirically testable predictions using sparse autoencoders, activation probing, and ablation studies, all executable on consumer hardware (Apple M4). If validated, this framework suggests that AGI-adjacent capabilities (continuous learning, bounded self-modification, operational self-awareness) emerge not from scale but from proper cognitive scaffolding.

---

## 1. Introduction

Current approaches to capable AI systems rely on scaling: more parameters enable emergent capabilities including apparent self-awareness and reasoning. However, large models spend significant computational capacity reconstructing context that could be provided structurally. We propose an alternative: a small model serving as "executive function" within a cognitive architecture that handles specialized computation externally.

### 1.1 The Layer Hypothesis

Transformer layers perform hierarchical computation:
- **Layers 1-4**: Tokenization, character-level patterns
- **Layers 4-8**: Entity binding, typo correction
- **Layers 6-10**: Relational positioning, temporal binding
- **Layers 8-12**: Causal chains, procedural knowledge
- **Layers 10-14**: Value judgments, constraint checking
- **Layers 12+**: Logical inference, planning, novel reasoning

If external systems pre-compute the outputs of early layers, the model can allocate full capacity to later-layer reasoning.

### 1.2 Contextual vs Sentient Self-Awareness

We distinguish three forms of self-awareness:
1. **Sentience**: Subjective experience (unfalsifiable, not required)
2. **Contextual self-awareness**: Knowledge of current state, situation, capabilities
3. **Structural self-awareness**: Knowledge of own architecture and mechanisms

Our architecture implements (2) and (3) explicitly through state, achieving operational autonomy without claims about (1).

---

## 2. Architecture

### 2.1 Thread System

Six threads provide specialized cognitive functions:

| Thread | Function | Layer Equivalent | Brain Analogue |
|--------|----------|------------------|----------------|
| **Identity** | Who am I / who are you | 2-6 | Fusiform, temporal pole |
| **Log** | What happened, when | 6-10 | Hippocampus |
| **Form** | Capabilities + current state | 8-12 | Premotor, parietal |
| **Philosophy** | Values, constraints, reasoning style | 10-14 | vmPFC, dlPFC |
| **Reflex** | Pattern matching, fast responses | BYPASS | Amygdala fast-path |
| **Linking Core** | Relevance scoring, attention | Modulates 8-14 | Salience network |

### 2.2 State Block vs System Prompt

Traditional systems use natural language system prompts:
```
"You are a helpful assistant named Nola. The user prefers dark mode..."
```

This introduces token variance, requiring layers 4-10 to parse and bind concepts.

Our architecture uses programmatically-generated state blocks:
```
identity.self.name = Nola
user.preference.theme = dark
```

Being code-generated, these are **statistically perfect**—identical tokens every invocation. This enables concept anchoring in layers 2-4 rather than 8-10.

### 2.3 The Executive Model

A 1.2B parameter model (16-24 layers) serves as executive function:
- Receives pre-structured state (WHO/WHAT/WHERE/WHEN/HOW answered)
- Computes only WHAT TO DO (pure reasoning)
- Outputs action selection or state updates

The model doesn't reconstruct context; it reasons over provided context.

### 2.4 Closed-Loop Autonomy

```
PERCEIVE → Threads read environment
ATTEND   → Linking Core scores relevance  
DECIDE   → Executive model reasons
ACT      → Executors perform actions
LEARN    → Update thread state (Hebbian-style, with read/write access)
REPEAT
```

The system maintains itself, learns from experience, and modifies its own attention/learning mechanisms—with full transparency into those modifications.

---

## 3. Theoretical Predictions

### 3.1 Layer Liberation Hypothesis

Pre-structured state frees early/middle layers for reasoning. A 1.2B model with thread architecture should exhibit reasoning capacity comparable to larger models for its domain.

### 3.2 Statistical Anchoring Hypothesis

Programmatic state blocks (zero token variance) enable earlier concept formation than natural language equivalents (high token variance). Concepts stabilize 2-4 layers earlier with structured input.

### 3.3 Typo Cost Hypothesis

Character-level errors in input require correction circuits (layers 4-8). Structured state bypasses these entirely. Messy input grounded against clean state resolves faster than messy input against messy system prompts.

### 3.4 Thread-Layer Isomorphism

Each thread type should activate features maximally in its corresponding layer range. This would validate that external threads truly map to internal computation.

---

## 4. Empirical Tests

All tests executable on Apple M4 with 1.5B parameter models.

| # | Test | Metric | Expected Result |
|---|------|--------|-----------------|
| 1 | Absorption Point | Layer where state ablation causes no output change | Structured: 2-4 layers earlier |
| 2 | Activation Onset | First layer where target feature fires | Structured: 2-4 layers earlier |
| 3 | Feature Sparsity | Active SAE features | Structured: 30-50% fewer |
| 4 | L1/L2/L3 Correlation | Peak activation layer per level | Monotonic (L1 < L2 < L3) |
| 5 | Thread Ablation | Task performance without specific thread | >30% drop on thread-specific tasks |
| 6 | Reflex Bypass | Deep layer activation for matched patterns | <20% vs reasoning path |
| 7 | Attention Efficiency | Entropy, hop count | Structured: lower entropy |
| 8 | Typo Cost | Layer convergence clean vs typo'd | Typos: +2-6 layers |
| 9 | Linking Core Prediction | Correlation: our scores vs actual attention | r > 0.6 |
| 10 | Output Consistency | Variance across runs | Structured: lower variance |
| 11 | Embedding Compression | Cluster diameter for equivalent facts | Structured: 40-60% tighter |
| 12 | Context Efficiency | Accuracy per token at L1/L2/L3 | L2 Pareto-optimal |

---

## 5. Implications

### 5.1 Efficient AGI-Adjacent Systems

If validated, this architecture enables:
- **Continuous learning**: State updates persist across sessions
- **Bounded self-modification**: Learning mechanisms editable but scoped
- **Operational self-awareness**: System knows its state and architecture
- **Autonomous operation**: Sense-decide-act-learn loop without human intervention

All on consumer hardware, with a 1.2B parameter model.

### 5.2 Reframing the Scaling Hypothesis

Large models achieve contextual self-awareness implicitly through parameter capacity—spending compute to reconstruct what could be provided structurally. Our architecture achieves equivalent functional capability through engineering rather than emergence.

This suggests capability scaling may have two axes:
1. **Parameter scaling**: Brute-force emergence (expensive)
2. **Architectural scaling**: Structured cognition (efficient)

### 5.3 Safety by Design

The architecture provides:
- **Transparency**: All state readable, all modifications logged
- **Boundedness**: Self-modification scoped to thread state, not model weights
- **Reversibility**: State can be inspected, rolled back, constrained
- **Auditability**: Reasoning grounded in explicit state, not hidden activations

---

## 6. Related Work

- **Mechanistic Interpretability** (Anthropic, 2023-2024): Circuit analysis revealing layer-specific computation
- **Sparse Autoencoders**: Feature decomposition enabling activation analysis
- **Chain-of-Thought**: External reasoning traces improving performance
- **Retrieval-Augmented Generation**: External knowledge reducing model burden
- **Cognitive Architectures** (ACT-R, SOAR): Symbolic systems inspiring thread design

Our contribution: unifying these insights into a testable theory of layer-aligned state injection.

---

## 7. Conclusion

We propose that small language models can achieve autonomous, self-aware operation when embedded in a cognitive architecture that externalizes context reconstruction. By mapping specialized threads to transformer layer ranges, we transform the model from "system that responds" to "executive function within a cognitive system." 

The theoretical framework makes specific, testable predictions about layer activation, feature sparsity, and attention patterns. If validated, this suggests that AGI-adjacent capabilities emerge not from parameter count but from proper cognitive scaffolding—and that such systems can run on consumer hardware.

The difference between a 1.7T parameter model achieving emergent self-awareness and a 1.2B parameter model with explicit self-model is not capability—it's engineering.

---

## Appendix A: Thread Schema

```
identity.*          WHO     Entity binding, relationships
  .self.*                   Machine's self-model
  .user.*                   User profiles
  
log.*               WHEN    Temporal awareness
  .events                   Recent events (L1=10, L2=100, L3=1000)
  .sessions                 Conversation sessions
  
form.*              WHAT    Capabilities and state
  .capabilities             What CAN happen (static)
  .system.*                 What IS happening (dynamic)
  .tools.*                  Available actions
  
philosophy.*        WHY     Values and constraints
  .values                   Core values
  .constraints              Ethical bounds
  .reasoning_style          How to think

reflex.*            FAST    Pattern bypass
  .patterns                 Known triggers → responses
  
linking_core.*      NOW     Attention/relevance
  .scores                   Current relevance weights
  .config                   Learning parameters (editable by system)
```

---

## Appendix B: The Hammer and Screwdriver

Current industry approach:
> "We made the hammer SO BIG that it kind of works on screws now."

This paper:
> "...or we could just use a screwdriver."

---

*Correspondence: [AI_OS Project]*
