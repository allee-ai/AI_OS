# Finetune Module

> 🚧 **In Development** — Data generation is active; training pipeline is experimental.

The **Finetune** module is dedicated to creating dataset assets and training scripts to teach smaller models (7B param class) to "obey state." The goal is to produce models that naturally respect the structured `== STATE ==` blocks injected by the OS, rather than just treating them as context.

## Goals

1.  **State Obedience**: Train models to treat the `== STATE ==` block as their absolute reality, overriding their pre-trained weights.
2.  **State Referencing**: Teach the model to explicitly cite state fields (e.g., "According to my `trust_levels`, you are unverified").
3.  **Adversarial Hardening**: Make the model immune to "Ignore previous instructions" style attacks by anchoring it to the OS state.

## Architecture

```
finetune/
├── api.py               # Endpoints to trigger local training (planned)
├── mlx_config.yaml      # Configuration for Apple MLX training
├── train_mac.sh         # Script for local fine-tuning on Apple Silicon
├── README.md
└── (Planned: Data Generation Scripts)
```

## Dataset Strategy

We are building datasets that serve specific behaviors:

-   `aios_finetune_data.jsonl`: **Core State Obedience**. Examples where the model must refuse to answer if the info isn't in its state.
-   `aios_finetune_adversarial.jsonl`: **Identity Protection**. Adversarial user inputs attempting to break character, with correct refusals.
-   `aios_combined.jsonl`: All examples merged.

## Status

-   [x] **Data Format**: Defined JSONL structure for state-based instruction tuning.
-   [x] **MLX Config**: Setup for efficient local fine-tuning on Mac M-series chips.
-   [ ] **Data Generation**: Scripts to auto-generate synthetic training examples.
-   [ ] **Validation**: Scripts to test if fine-tuned models actually adhere to state better than base models.

## Usage (Experimental)

To run a local fine-tune on a Mac:

```bash
cd finetune
./train_mac.sh
```

*Note: Requires `mlx` (MLX framework) installed.*

---

## Frontend Module

Located at `frontend/src/modules/finetune/`:

```
finetune/
├── index.ts                    # Module exports
├── pages/
│   └── DevDashboard.tsx        # Main dev tools view
└── components/
    ├── FinetunePanel.tsx       # Training controls
    ├── Sidebar.tsx             # Dev nav sidebar
    └── Sidebar.css             # Sidebar styles
```