# Nola: Local-First Personal AI with Hierarchical Context

A privacy-first, open-source personal AI system with **Hierarchical Experiential Attention (HEA)**, persistent memory, and multi-channel stimuli support. Nola is not just a chat app—she is a context-aware, extensible cognitive agent that runs entirely on your machine.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

---

## 🧠 Why Nola?

- **Not just a chatbot:** Nola is a local-first, privacy-respecting AI with a persistent, hierarchical memory system.
- **Hierarchical Context:** Every message is classified and routed through a context manager (HEA) that dynamically adjusts how much of your identity and history is used.
- **User-owned data:** All conversations and identity data are stored locally—never in the cloud.
- **Multi-channel:** React chat is just one stimuli channel. CLI, email, and more are supported or planned.
- **Research + Product:** Designed for both everyday use and as a platform for AI/UX research.

---

## 🚀 Quick Start

### 1. One-Command Start (Recommended)

**macOS/Linux:**
```bash
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
chmod +x start.sh
./start.sh
```

**Windows:**
```cmd
git clone https://github.com/allee-ai/AI_OS.git
cd AI_OS
start.bat
```

The script will:
1. Check/install prerequisites (Ollama, Python, Node)
2. Start Ollama if needed
3. Install dependencies
4. Start backend & frontend
5. Open browser automatically

### 2. Docker

```bash
ollama serve  # Ensure Ollama is running on host
chmod +x start-docker.sh
./start-docker.sh
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    STIMULI CHANNELS                    │
├──────────────┬──────────────┬──────────────┬───────────┤
│  React Chat  │    Twilio    │    Email     │   CLI     │
│  (this app)  │   (future)   │   (future)   │ (exists)  │
└──────┬───────┴──────────────┴──────────────┴───────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              NOLA - Hierarchical State                  │
├────────────────────────────────────────────────────────┤
│  Context Manager (HEA)                                 │
│  ├── L1: Realtime (~10 tokens) - Quick responses       │
│  ├── L2: Conversational (~50 tokens) - Default         │
│  └── L3: Analytical (~200 tokens) - Deep context       │
├────────────────────────────────────────────────────────┤
│  Identity Thread                                      │
│  ├── machineID.json → identity.json → Nola.json        │
│  └── userID.json ──┘                                   │
├────────────────────────────────────────────────────────┤
│  Ollama (Local LLM)                                   │
└────────────────────────────────────────────────────────┘
```

---

## ✨ Features

- **Hierarchical Context (HEA):** L1/L2/L3 context levels, automatic escalation based on message type
- **Persistent Memory:** All conversations and identity data are stored in `Nola/Stimuli/conversations/`
- **Local AI:** Powered by Ollama (runs entirely on your machine)
- **Multi-channel:** React, CLI, and more
- **Modern Stack:** React 18 + TypeScript + Vite + FastAPI
- **User-Owned Data:** Your conversations, your machine, no cloud

---

## 📁 Project Structure

```
React_Demo/
├── Nola/                    # 🧠 The brain - hierarchical state system
│   ├── agent.py            # Thread-safe singleton agent
│   ├── contract.py         # Metadata protocol
│   ├── Nola.json           # Global runtime state
│   ├── identity_thread/    # Identity hierarchy
│   │   ├── identity.json   # Aggregated identity
│   │   ├── machineID/      # Machine context module
│   │   └── userID/         # User context module
│   └── Stimuli/
│       ├── conversations/  # 💬 Chat history stored here
│       └── comms/          # Future: Twilio, email modules
│
├── react-chat-app/         # 💻 This stimuli channel
│   ├── backend/            # FastAPI server
│   │   ├── main.py         # App entry point
│   │   ├── services/
│   │   │   └── agent_service.py  # ⭐ Nola integration + HEA
│   │   └── api/
│   │       ├── chat.py     # REST endpoints
│   │       └── websockets.py
│   └── frontend/           # React + Vite app
│       └── src/
│           ├── components/Chat/
│           ├── hooks/
│           └── services/
│
├── docs/                   # 📚 Theory & evaluation
│   ├── concept_attention_theory.md
│   └── tests.md
│
└── .github/               # 👥 Contributor infrastructure
    ├── agents/            # AI agent profiles
    └── ISSUE_TEMPLATE/
```

---

## 🧩 Key Concepts

- **Stimuli Channel:** Any interface (chat, CLI, email, etc.) that sends messages to Nola’s cognitive system.
- **Identity Thread:** Aggregates machine and user identity, filters by context level.
- **Context Manager (HEA):** Classifies each message and selects the right context depth.
- **Persistence:** All chat and identity data is stored locally for privacy and continuity.

---

## 🛠️ Development & API

### Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm run dev      # Development server
npm run build    # Production build
npm run preview  # Preview production build
```

### Type Checking

```bash
cd frontend
npm run build  # Runs TypeScript compiler
```

---

## 📦 Building for Production

### Docker

```bash
docker-compose up --build
```

### Manual Build

```bash
# Backend - runs as-is with uvicorn
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Frontend - build static files
cd frontend
npm run build
# Serve dist/ with any static server
```

---

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

---

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM runtime
- [FastAPI](https://fastapi.tiangolo.com) - Modern Python web framework
- [Vite](https://vitejs.dev) - Next-gen frontend tooling
- [React](https://react.dev) - UI library
