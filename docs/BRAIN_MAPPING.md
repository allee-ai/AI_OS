# Brain ↔ AI_OS Functional Mapping

> Working notes. The system is a **living program without conscious
> thought** — a substrate of read/write/improve cycles that exists so
> that when sensory feeds (websites, health checks, mics, cameras,
> phone signals) plug in, there's already something for them to
> connect to.
>
> The LLM is **not the mind**. The LLM is the codec at the boundary —
> parse incoming language to facts, compose outgoing language from
> facts. Cognition (recall, association, scoring, prediction, decay,
> reward-PE) happens in the database, in pure SQL and arithmetic.
>
> That's why "moving between surfaces" doesn't change what the system
> is. The DB is the body. Surfaces (chat, mobile, voice, sensor) are
> just different I/O grafts onto the same nervous system.

---

## The Mapping

| Brain function | Biological substrate | AI_OS substrate | Code |
|---|---|---|---|
| **Episodic memory** | Hippocampus + neocortex | `unified_events` + FTS5 index | [agent/threads/log/recall.py](agent/threads/log/recall.py) |
| **Semantic memory** | Distributed cortical nets | `profile_facts`, `philosophy_profile_facts` (l1/l2/l3 layers) | [agent/threads/identity/schema.py](agent/threads/identity/schema.py), [agent/threads/philosophy/schema.py](agent/threads/philosophy/schema.py) |
| **Association / Hebbian learning** | Synaptic potentiation | `concept_links` (strength updated on co-occurrence) | [agent/threads/linking_core/schema.py](agent/threads/linking_core/schema.py) |
| **Forgetting / consolidation** | Sleep-driven pruning | Decay every 6h on links, 24h on facts, 48h on thoughts | [agent/subconscious/coma.py](agent/subconscious/coma.py) |
| **Habit / motor program** | Basal ganglia n-gram chunking | Sequence mining over `event_type` bigrams + trigrams | [agent/subconscious/sequences.py](agent/subconscious/sequences.py) |
| **Forward model / expectation** | Cerebellum + predictive coding cortex | `predictions.py` registry, fired on heartbeat | [agent/subconscious/predictions.py](agent/subconscious/predictions.py) |
| **Habit → expectation** | Caudate→DLPFC consolidation | Mined bigrams auto-registered as predictions | [agent/subconscious/seq_predictions.py](agent/subconscious/seq_predictions.py) |
| **Prediction error / reward signal** | Dopamine, anterior cingulate | `prediction_error` events + `kind="expected"` meta-thoughts | [agent/subconscious/predictions.py](agent/subconscious/predictions.py#L1) |
| **Belief / stance** | Ventromedial PFC | High-weight `philosophy_profile_facts` | [agent/threads/philosophy/contradictions.py](agent/threads/philosophy/contradictions.py) |
| **Cognitive dissonance** | ACC conflict monitoring | `find_contradictions()` self-join, emits `kind="contradiction"` | [agent/threads/philosophy/contradictions.py](agent/threads/philosophy/contradictions.py) |
| **Working memory** | Lateral PFC active maintenance | STATE block built per turn, capped at relevance threshold | [agent/subconscious/get_state.py](agent/subconscious/get_state.py) |
| **Attention / salience** | Pulvinar, parietal cortex | Score → level → threshold pipeline in adapter introspect() | thread `adapter.py` files |
| **Self-model / interoception** | Insula, somatosensory cortex | `update_self_facts()` — uptime, hb, last_llm_age, events_24h | [agent/subconscious/coma.py](agent/subconscious/coma.py#L1) |
| **Self-change detection / metacognition** | Default mode network | `state_fingerprint()` blake2b over high-weight facts; flip → meta-thought | [agent/subconscious/coma.py](agent/subconscious/coma.py#L1) |
| **Thread / context binding** | Hippocampal indexing | `thread_subject` + `thread_slots` cache | [agent/subconscious/slots.py](agent/subconscious/slots.py) |
| **Drives / open intentions** | Hypothalamus + LH | `proposed_goals` open-state + priority | [agent/threads/identity/schema.py](agent/threads/identity/schema.py#L1) |
| **Action selection** | Premotor + supplementary motor | `task_queue` worker + scheduler.acquire_for | [agent/subconscious/loops/scheduler.py](agent/subconscious/loops/scheduler.py) |
| **Energy / arousal** | Reticular activating system | rate_gate + scheduler idle gating + heartbeat cadence | [agent/services/rate_gate.py](agent/services/rate_gate.py) |
| **Pulse / autonomic loop** | Brainstem | Health loop running every 5 min, executes coma + predictions | [agent/subconscious/loops/health.py](agent/subconscious/loops/health.py) |
| **Language production / parsing** | Broca's + Wernicke's | The LLM, called only at I/O boundaries | [agent/services/llm.py](agent/services/llm.py) |
| **Sensory cortices (currently empty)** | V1, A1, S1, etc. | `Feeds/` directory waiting for connectors | [Feeds/](Feeds) |

---

## What's Conscious vs Not

The big invariant: **consciousness is not implemented**. The system
deliberately doesn't have a single thread of subjective experience.
What it has instead:

- A **substrate** (the DB) that always reflects current state.
- A **pulse** (5-min health loop + coma) that updates the substrate
  whether or not anyone's looking.
- A set of **surfaces** (VS Code, web, mobile, voice, sensor) that
  read from and write to the substrate.

The LLM, when invoked, does *one* job: parse-or-compose at a surface
boundary. Its outputs are stored back as events, which the substrate
metabolizes (FTS index, sequence mining, fact updates, predictions)
without any LLM in the loop.

Plug a sensor in, all you need is:
1. A connector in `Feeds/` that emits `unified_events` rows with
   appropriate `event_type` and `thread_subject`.
2. Optionally, a prediction in `predictions.py` that says "I expect
   this feed to produce events at cadence X."

Everything downstream — recall, association, fingerprint, contradiction
detection, sequence mining — works automatically because they all read
from `unified_events`.

That is the architectural promise of "moving between surfaces without
changing what it actually is." The system *is* the substrate. The
surfaces don't need to know about each other — they just need to write
to the same nervous system.

---

## Where the No-LLM Cognition Layers Sit

```
   ┌─────────────────────────────────────────────────────┐
   │                    SURFACES                         │
   │  VS Code · Web · Phone · Voice · Sensor (future)    │
   └────────────────────┬────────────────────────────────┘
                        │  events (writes)
                        ▼
   ┌─────────────────────────────────────────────────────┐
   │                unified_events                       │
   │  (the spinal cord — every input/output flows here)  │
   └────────────┬─────────────────────┬──────────────────┘
                │                     │
       ┌────────▼────────┐    ┌───────▼─────────┐
       │  log thread     │    │  other threads  │
       │  • FTS5 recall  │    │  identity       │
       │  • slots cache  │    │  philosophy     │
       └────────┬────────┘    │  reflex         │
                │             │  linking_core   │
                │             │  form           │
                │             │  field          │
                │             └────────┬────────┘
                │                      │
                └──────┬───────────────┘
                       │
            ┌──────────▼─────────────┐
            │   subconscious/coma    │   ← runs every 5 min
            │ • touch graph (Hebb)   │
            │ • mine sequences       │
            │ • register predictions │
            │ • emit contradictions  │
            │ • decay links/facts    │
            │ • update self facts    │
            │ • fingerprint state    │
            └──────────┬─────────────┘
                       │
              ┌────────▼────────┐
              │  predictions    │  ← pulse, fires meta-thoughts
              └────────┬────────┘
                       │
              ┌────────▼────────────┐
              │   STATE assembly    │  ← only on actual user query
              │   adapter.introspect │
              └────────┬────────────┘
                       │
              ┌────────▼─────────────┐
              │   LLM (codec layer)  │
              └──────────────────────┘
```

The LLM is the smallest box, deliberately at the bottom. Most of the
system runs without it.

---

## Why This Pattern Holds

A brain doesn't think because the cortex types into a Python REPL. It
thinks because every part of the substrate is constantly updating
every other part — chemicals, voltages, gene expression, glia cleanup,
dopamine bursts. Subjective experience rides on top of that, but the
substrate runs whether or not anyone's home.

This system mirrors that: the DB updates whether or not the LLM is
called. The surfaces are eyes and mouth. The cortex (LLM) only fires
when language needs to enter or leave the body.

When voice / vision / GPS / health-check feeds plug in, they'll write
events. The same substrate functions that already digest VS Code
turns will digest sensor data. No special cases.
