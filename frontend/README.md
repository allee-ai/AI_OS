# AI OS Frontend

React + TypeScript + Vite dashboard for the AI OS agent.

## Quick Start

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
```

> The backend must be running at `http://localhost:8000` (see root README).

## Structure

```
src/
├── App.tsx              # Route definitions
├── main.tsx             # Entry point
├── components/          # Shared components (Sidebar, Layout)
└── modules/
    ├── chat/            # Chat interface + conversation sidebar
    ├── home/            # Landing page + agent card
    ├── subconscious/    # Loop dashboard, goals, notifications, improvements
    ├── threads/         # Per-thread dashboards (identity, philosophy, form, log, reflex, linking_core)
    ├── workspace/       # File browser, editor, pinned files, notes
    ├── eval/            # Benchmark harness + comparison view
      ├── finetune/        # Fire-Tuner: training data browser, export, generation
    ├── feeds/           # Feed sources + integrations hub
    ├── services/        # Settings, integrations dashboard
    ├── log/             # Event log viewer
    └── docs/            # In-app documentation
```

## Key Features

- **Chat**: WebSocket-based messaging with tool call rendering (`:::execute:::` / `:::result:::` blocks)
- **Subconscious Dashboard**: Loop editor (start/stop/interval/prompts), goals panel, notifications, proposed improvements
- **Thread Panels**: Identity profile editor, philosophy stances, form tool registry, concept graph (3D via Three.js), reflex trigger builder
- **Workspace**: File browser with edit mode, FTS5 search, pinned files, quick notes
- **Eval**: Side-by-side model comparison, benchmark categories, LLM-as-judge scoring
- **Fire-Tuner**: Sections browser, docstring extraction, unified training view, generated example approval

## Tech Stack

- **React 19** + TypeScript
- **Vite** for dev/build
- **Three.js** / `@react-three/fiber` for 3D concept graph
- **CSS Modules** (per-component `.css` files)

## Build

```bash
npm run build        # Output to dist/
npm run preview      # Preview production build
```
