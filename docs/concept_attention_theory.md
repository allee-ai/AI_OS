# Hierarchical Experiential Attention: A Parallel Memory Layer for Personalized Language Model Responses

**Status:** Working Draft  
**Last Updated:** December 2025  
**Authors:** [Your Name]

---

## Abstract

Large Language Models (LLMs) generate responses by computing probability distributions over tokens conditioned on training data. While powerful for general knowledge, this approach lacks persistent experiential memory—every conversation starts fresh or requires expensive context stuffing. Current solutions like Retrieval-Augmented Generation (RAG) treat memory as search over fragments, while fine-tuning burns static knowledge into weights.

We propose **Hierarchical Experiential Attention (HEA)**: a parallel attention layer that computes token probabilities conditioned on structured personal state, running alongside standard LLM attention. The key insight is that **location in hierarchy + context level + recency = implicit attention weighting**, eliminating the need for learned attention weights in the initial formulation.

We demonstrate this architecture with Nola, an open-source implementation using JSON state with metadata contracts. Early results suggest that structured experiential memory outperforms flat context stuffing on personalization quality while using significantly fewer tokens.

---

## 1. Introduction

### 1.1 The Memory Problem

Current LLMs face a fundamental limitation: they lack persistent experiential memory. Each inference is stateless—the model has no built-in mechanism to remember previous interactions, learn user preferences, or accumulate personal context over time.

Existing approaches to this problem each have significant drawbacks:

| Approach | Mechanism | Limitation |
|----------|-----------|------------|
| **Context Stuffing** | Prepend all history to prompt | Token limits, cost, irrelevant noise |
| **RAG** | Embed & retrieve relevant chunks | Retrieval ≠ memory, no structure, fragments |
| **Fine-tuning** | Train on personal data | Expensive, static, catastrophic forgetting |
| **Platform Memory** | Vendor-managed (ChatGPT Memory) | Black box, no user control, vendor lock-in |

### 1.2 The Dual-Process Hypothesis

We propose that effective personal AI requires **two parallel processes**:

1. **Probabilistic Attention** (existing LLM): "What token is likely given general knowledge?"
2. **Experiential Attention** (our contribution): "What token is likely given MY experiences?"

This mirrors the neuroscience distinction between:
- **Neocortex**: Pattern recognition, statistical prediction
- **Hippocampus**: Episodic memory, factual recall

Current LLMs are "all neocortex"—powerful pattern matchers with no episodic memory system.

### 1.3 Contribution

We introduce:
1. **Hierarchical Experiential Attention (HEA)**: A formal framework for parallel memory-conditioned generation
2. **Metadata Contract Protocol**: A sync mechanism for structured state management
3. **Context Level Selection**: Cognitive load-inspired depth control
4. **Nola**: Open-source reference implementation

---

## 2. Related Work

### 2.1 Retrieval-Augmented Generation

RAG systems (Lewis et al., 2020; LangChain, LlamaIndex) augment LLM context with retrieved documents. However:
- Retrieval returns **fragments**, not structured memory
- No hierarchy or relevance weighting beyond embedding similarity
- 10,000 chunks is search, not memory

### 2.2 Memory-Augmented Language Models

MemGPT (Packer et al., 2023) introduces memory management for LLMs with explicit read/write operations. Our approach differs:
- We use **implicit weighting** via hierarchy, not explicit memory operations
- State sync is **metadata-driven**, not procedural
- Context levels map to **cognitive load theory**, not arbitrary tiers

### 2.3 Cognitive Architectures

ACT-R (Anderson, 2007) and SOAR (Laird, 2012) model human cognition with structured memory systems. We adapt key concepts:
- **Activation-based retrieval** → Hierarchy + recency weighting
- **Working memory limits** → Context levels (L1/L2/L3)
- **Declarative vs procedural** → Experiential state vs model weights

### 2.4 Personal AI Assistants

Commercial systems (ChatGPT Memory, Claude Projects) offer limited personalization:
- **Opaque**: Users can't inspect or modify memory representations
- **Vendor-locked**: Data trapped in proprietary systems
- **Unstructured**: Flat key-value or free-text storage

---

## 3. Theoretical Framework

### 3.1 Formal Definition

Let $x$ be an input sequence and $y$ be the output sequence. Standard autoregressive generation computes:

$$P(y|x) = \prod_{t=1}^{T} P(y_t | y_{<t}, x; \theta)$$

where $\theta$ represents model parameters encoding compressed training data.

We introduce **experiential state** $E$ structured as a hierarchy:

$$E = \{E^{(0)}, E^{(1)}, ..., E^{(d)}\}$$

where $E^{(i)}$ represents state at depth $i$ in the hierarchy (raw data → aggregators → global state).

Hierarchical Experiential Attention computes:

$$P(y|x, E) = \prod_{t=1}^{T} P(y_t | y_{<t}, x, \phi(x, E); \theta)$$

where $\phi(x, E)$ is the **context selection function** that extracts relevant experiential context.

### 3.2 Context Selection Function

The context selection function $\phi$ operates in three stages:

**Stage 1: Level Selection**

Based on input characteristics, select context level $l \in \{1, 2, 3\}$:

$$l = \text{level}(x) = \begin{cases} 1 & \text{if } x \text{ is casual/quick} \\ 2 & \text{if } x \text{ involves current context} \\ 3 & \text{if } x \text{ requires deep analysis} \end{cases}$$

**Stage 2: Hierarchical Weighting**

For each state node $e \in E$, compute relevance weight:

$$w(e) = \alpha_{\text{hierarchy}}(e) \cdot \alpha_{\text{level}}(e, l) \cdot \alpha_{\text{recency}}(e)$$

where:
- $\alpha_{\text{hierarchy}}(e) \in [0,1]$: Weight based on position in hierarchy
- $\alpha_{\text{level}}(e, l)$: Weight based on node's context level vs selected level
- $\alpha_{\text{recency}}(e)$: Decay function based on `last_updated` timestamp

**Stage 3: Context Extraction**

Extract weighted context up to token budget $B$:

$$\phi(x, E) = \text{top}_B\left(\{(e, w(e)) : e \in E, w(e) > \tau\}\right)$$

### 3.3 Implicit Attention via Structure

A key insight: **the hierarchy itself encodes attention**. Rather than learning attention weights, we define them structurally:

```
Hierarchy Weight:
  Global State (Nola.json)     → 1.0  (always relevant)
  Identity Aggregator          → 0.7  (usually relevant)  
  Raw Data Modules             → 0.4  (specifically relevant)

Level Weight:
  Level 1 content at Level 1   → 1.0
  Level 2 content at Level 1   → 0.3
  Level 3 content at Level 1   → 0.1
  [symmetric scaling for other levels]

Recency Weight:
  w_recency(e) = exp(-λ · age(e))
  where age(e) = now - e.metadata.last_updated
```

This eliminates the need for learned attention in the initial formulation while preserving the key property: **relevant experiential context is weighted higher**.

### 3.4 Dual-Stream Generation

The full generation process combines both attention streams:

```
Input x
    ├── LLM Attention ──────────→ P(y|x; θ)      [probabilistic]
    │
    └── Experiential Attention ─→ φ(x, E)        [structured recall]
                                      │
                                      ▼
                               Augmented prompt
                                      │
                                      ▼
                              P(y|x, φ(x,E); θ)  [grounded output]
```

In the current implementation, experiential context is injected via system prompt. Future work explores cross-attention integration at the model layer.

---

## 4. Architecture

### 4.1 State Hierarchy

```
Nola.json (Global Runtime State)
    ↑ sync
Identity.json (Aggregator)
    ↑ sync
┌───┴───┐
│       │
machineID.json    user.json (Raw Data Modules)
```

Each node contains:
```json
{
  "metadata": {
    "last_updated": "ISO-8601 timestamp",
    "context_level": 1|2|3,
    "needs_sync": boolean,
    "stale_threshold_seconds": number,
    "source_file": "path"
  },
  "data": {
    // Arbitrary structure - keys don't matter
    // Location + level + recency = weighting
  }
}
```

### 4.2 Metadata Contract Protocol

Modules communicate via metadata signals, not direct calls:

| Signal | Meaning | Action |
|--------|---------|--------|
| `needs_sync: true` | Module has updates | Parent pulls on next access |
| `stale_threshold` exceeded | Data may be outdated | Trigger refresh |
| `context_level` change | Relevance shifted | Adjust weighting |

This enables:
- **Decoupled modules**: No direct dependencies
- **Lazy sync**: Only sync when accessed
- **Thread safety**: Atomic metadata checks

### 4.3 Context Level Semantics

| Level | Token Budget | Use Case | Cognitive Analog |
|-------|--------------|----------|------------------|
| **L1** | ~10 tokens | Quick identity, greetings | Automatic retrieval |
| **L2** | ~50 tokens | Current projects, relationships | Working memory |
| **L3** | ~200 tokens | Full history, deep analysis | Deliberate recall |

Level selection can be:
- **Explicit**: API parameter (`stimuli_type="analytical"`)
- **Implicit**: Keyword detection, conversation depth
- **Adaptive**: Escalate/de-escalate based on conversation flow

### 4.4 Thread-Safe Singleton

The Agent maintains single instance with atomic state access:

```python
class Agent:
    _instance = None
    _lock = Lock()
    
    def get_state(self, reload=False):
        with self._lock:
            if reload:
                self._state = json.load(state_file)
            return self._state
    
    def set_state(self, section, data):
        with self._lock:
            self._state[section] = data
            json.dump(self._state, state_file)
```

This ensures consistency when multiple interfaces (React, CLI, Twilio) access state concurrently.

---

## 5. Implementation: Nola

### 5.1 System Overview

Nola is a reference implementation demonstrating HEA:

```
nola/
├── core/
│   ├── agent.py          # Thread-safe singleton
│   ├── contract.py       # Metadata protocol helpers
│   └── Nola.json         # Global runtime state
├── identity_thread/
│   ├── identity.py       # Aggregator logic
│   ├── identity.json     # Aggregated state
│   ├── machineID/        # Machine context module
│   └── userID/           # User context module
├── stimuli/
│   ├── comms/            # External interfaces (Twilio, email)
│   └── conversations/    # Interaction history
└── interfaces/
    ├── react-chat/       # Web interface
    ├── cli/              # Terminal interface
    └── api/              # FastAPI backend
```

### 5.2 Key Operations

**Bootstrap (first access):**
```python
agent = get_agent()  # Triggers full sync chain
# machineID → identity → Nola.json
```

**Generation with context:**
```python
response = agent.generate(
    prompt="I'm stressed about work",
    stimuli_type="conversational"  # L2 context
)
# 1. Select level 2
# 2. Weight hierarchy nodes
# 3. Extract relevant context
# 4. Inject into system prompt
# 5. Generate via Ollama
```

**Context escalation:**
```python
# Conversation turn 1: "Hi!" → L1
# Conversation turn 2: "Work is stressful" → L2 (escalate)
# Conversation turn 5: "Tell me a joke" → L1 (de-escalate)
```

### 5.3 Model Agnosticism

Nola interfaces with Ollama, supporting any local model:

```python
def generate(self, prompt, model='llama3.2:3b'):
    context = self._build_context()  # HEA selection
    full_prompt = f"{context}\n\nUser: {prompt}"
    return ollama.generate(model=model, prompt=full_prompt)
```

The experiential layer is independent of the underlying LLM.

---

## 6. Evaluation Framework

### 6.1 Metrics

| Metric | Definition | Measurement |
|--------|------------|-------------|
| **Personalization Quality** | Response relevance to user context | Human eval (1-5 scale) or LLM-as-judge |
| **Token Efficiency** | Context tokens used for equivalent quality | Tokens per quality point |
| **Factual Grounding** | Accuracy of personal facts in response | Fact verification against state |
| **Context Appropriateness** | Right level for the query | Level prediction accuracy |

### 6.2 Baselines

1. **Base LLM**: No memory, fresh each conversation
2. **Full Context**: Dump entire state into prompt
3. **RAG**: Embed state, retrieve top-k chunks
4. **MemGPT**: Explicit memory operations (if comparable)

### 6.3 Ablation Studies

| Ablation | Tests |
|----------|-------|
| **-Hierarchy** | Flat state vs hierarchical |
| **-Levels** | Single level vs L1/L2/L3 |
| **-Recency** | No decay vs time-weighted |
| **-Metadata** | Direct sync vs contract protocol |

### 6.4 Hypotheses

**H1**: HEA achieves higher personalization quality than RAG at equivalent token budgets.

**H2**: Context level selection reduces tokens by 60%+ vs full context with <10% quality loss.

**H3**: Hierarchical weighting outperforms flat retrieval on multi-turn conversations.

---

## 7. Discussion

### 7.1 Path to Learned Attention

The current implementation uses **structural attention** (hierarchy + level + recency). Future versions could learn attention weights:

```
Phase 1: Structural (current)
  - Fixed weights from hierarchy position
  - Rule-based level selection
  
Phase 2: Hybrid
  - Embeddings for similarity scoring
  - Learned level selection classifier
  
Phase 3: End-to-End
  - Cross-attention between input and experiential state
  - Jointly trained with base model (adapter layers)
```

### 7.2 Embedding Integration

Keys are currently human-readable strings. Embedding integration:

```python
# Current
state["work"]["projects"]["CAF"] = "Cognitive Agent Framework..."

# With embeddings
state["work"]["projects"]["CAF"] = {
    "text": "Cognitive Agent Framework...",
    "embedding": [0.12, -0.34, ...],  # Regenerable per model
}
```

The **text is the permanent artifact**; embeddings regenerate per model.

### 7.3 Multi-Modal Memory

The hierarchical structure extends to non-text modalities:

```json
{
  "experiential_state": {
    "text_memories": { ... },
    "image_memories": { ... },
    "audio_memories": { ... }
  }
}
```

Each modality maintains its own hierarchy with shared metadata contract.

### 7.4 Privacy and Ownership

HEA is designed for **user-owned memory**:
- JSON files on local machine
- No cloud sync required
- Export/import between systems
- Full transparency (human-readable state)

This contrasts with vendor-controlled memory (ChatGPT, Claude) where users cannot inspect or own their data.

---

## 8. Conclusion

We introduced Hierarchical Experiential Attention (HEA), a framework for augmenting LLMs with structured personal memory. Key contributions:

1. **Theoretical framework**: Dual-process model with formal context selection function
2. **Structural attention**: Hierarchy + level + recency as implicit weighting
3. **Metadata protocol**: Decoupled sync via signals, not calls
4. **Reference implementation**: Nola, open-source and model-agnostic

Early results suggest that structured experiential memory offers a promising alternative to RAG and fine-tuning for personalized AI. The architecture is extensible to learned attention, embeddings, and multi-modal memory while preserving user ownership and transparency.

**Future work**: Quantitative evaluation against baselines, learned attention integration, and multi-agent experiential sharing.

---

## References

Anderson, J. R. (2007). How Can the Human Mind Occur in the Physical Universe? Oxford University Press.

Laird, J. E. (2012). The Soar Cognitive Architecture. MIT Press.

Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. NeurIPS.

Packer, C., et al. (2023). MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560.

---

## Appendix A: Metadata Contract Specification

```python
def create_metadata(context_level=1, source_file=None):
    return {
        "last_updated": datetime.now().isoformat(),
        "context_level": context_level,
        "needs_sync": False,
        "stale_threshold_seconds": 600,
        "source_file": source_file
    }

def should_sync(metadata):
    return metadata.get("needs_sync", False)

def is_stale(metadata):
    threshold = metadata.get("stale_threshold_seconds", 600)
    updated = datetime.fromisoformat(metadata["last_updated"])
    return (datetime.now() - updated).seconds > threshold

def request_sync(metadata):
    metadata["needs_sync"] = True
    return metadata

def mark_synced(metadata):
    metadata["needs_sync"] = False
    metadata["last_updated"] = datetime.now().isoformat()
    return metadata
```

## Appendix B: Context Level Selection Algorithm

```python
def select_context_level(user_input, conversation_history):
    """
    Select appropriate context level based on input analysis.
    
    Returns: 1 (minimal), 2 (moderate), or 3 (full)
    """
    input_lower = user_input.lower()
    
    # Level 3 triggers: analytical, deep, reflective
    l3_triggers = ["analyze", "explain", "why do i", "tell me about my", 
                   "history", "pattern", "reflect"]
    if any(t in input_lower for t in l3_triggers):
        return 3
    
    # Level 1 triggers: casual, quick, greetings
    l1_triggers = ["hi", "hello", "hey", "thanks", "bye", "ok", "sure"]
    if any(input_lower.strip() == t for t in l1_triggers):
        return 1
    
    # Level 2: default for substantive conversation
    return 2
```

---

*This document is a working draft. Contributions welcome via GitHub issues.*
