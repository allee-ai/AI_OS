# Core Novel Contributions

This document outlines the 12 key innovations that define the Cognitive Operating System. These concepts distinguish this project from standard LLM wrappers or chatbots.

## 1. Learned Focus ("Focus is all you need")
Moving beyond "Attention is all you need," we use a persistent database as a control plane that learns key sequences ("after A comes B") to pre-select context before the LLM sees it. This architectural shift separates retrieval from generation.

## 2. Values vs. Weights Sovereignty
We enforce a split between content and importance:
*   **User Controls VALUES:** You decide *what* memory exists (transparency/editability).
*   **System Controls WEIGHTS:** The AI learns *how often* to recall it (importance).
The user can edit the memory content at any time; the system only adjusts the retrieval probability.

## 3. Hierarchical Experiential Attention (HEA)
A structural, deterministic attention weighting system based on cognitive load theory, rather than purely learned vector attention.
*   **L1 (Reflex):** ~10 tokens. Immediate action.
*   **L2 (Working):** ~50 tokens. Immediate context.
*   **L3 (Deep):** ~200 tokens. Reflective synthesis.

## 4. The "Living Body" Architecture
We couple a small 7B LLM with a sterile, persistent Unikernel browser instance ("The Body"). This body maintains its own cookies, session state, and "physical" presence, granting the small model long-horizon web agency that ephemeral agents lack.

## 5. Behavioral Entropy
We deliberately inject "human imperfections" (mouse jerks, typing typos, variable delays) into automation. This is not a bug but a feature: "imperfection" acts as a security pass key to bypass bot detection systems.

## 6. Deterministic Control / Probabilistic Data
A rigorous separation of concerns:
*   **Database (Control Plane):** Acts as the **Brain**, deterministically selecting stimuli and sequences.
*   **LLM (Data Plane):** Acts as the **Voice/Articulator**, probabilistically generating output based on the brain's selection.

## 7. Metadata Contract Protocol
Modules communicate via metadata signals (`needs_sync`, `stale_threshold`) rather than direct function calls. This allows for lazy, thread-safe state updates and decoupled architecture.

## 8. Spread Activation in SQL
Implementing Hebbian learning ("neurons that wire together fire together") using standard SQL tables (`key_sequences`, `concept_links`) to mimic associative memory retrieval without the opacity of vector databases.

## 9. Reflex Learning System
A mechanism where repeated high-weight patterns automatically degrade from "LLM Decisions" (Computationally expensive) to "Scripted Reflexes" (Rule-based execution), mimicking the biological transition from conscious learning to subconscious competence.

## 10. Identity Anchoring
Using structured JSON files as "Identity Anchors" that survive adversarial attacks better than prompt-only personas. These anchors are structurally enforced by the system prompt builder, making the identity immutable relative to the conversation context.

## 11. Cognitive Cost Equation
*Learned Focus + 7B = Perception of 120B at cost of 7B.*
Small models can perform tasks traditionally reserved for large models by narrowing the search space via focus rather than widening the context window.

## 12. Mutual Accountability Alignment
An alignment theory where:
*   The AI is grounded in user-editable documents (it cannot hallucinate its core identity).
*   The User is forced to reflect on their own patterns (as mirror by the AI).
This creates a co-evolutionary loop of improvement for both human and machine.
