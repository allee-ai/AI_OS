# React Chat App → Nola Stimuli Channel

A local-first AI chat application that serves as a **communication stimuli channel** for [Nola](Nola/README.md) - a personal AI with hierarchical state management. Built with React + TypeScript frontend and FastAPI backend, connected to Nola's Hierarchical Experiential Attention (HEA) system.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

## 🧠 What is This?

This chat interface is one of several **stimuli channels** that feed into Nola's cognitive system:

```
┌─────────────────────────────────────────────────────────┐
│                    STIMULI CHANNELS                      │
├──────────────┬──────────────┬──────────────┬────────────┤
│  React Chat  │    Twilio    │    Email     │    CLI     │
│  (this app)  │   (future)   │   (future)   │  (exists)  │
└──────┬───────┴──────────────┴──────────────┴────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│              NOLA - Hierarchical State                   │
├─────────────────────────────────────────────────────────┤
│  Context Manager (HEA)                                   │
│  ├── L1: Realtime (~10 tokens) - Quick responses        │
│  ├── L2: Conversational (~50 tokens) - Default          │
│  └── L3: Analytical (~200 tokens) - Deep context        │
├─────────────────────────────────────────────────────────┤
│  Identity Thread                                         │
│  ├── machineID.json → identity.json → Nola.json         │
│  └── userID.json ──┘                                    │
├─────────────────────────────────────────────────────────┤
│  Ollama (Local LLM)                                      │
└─────────────────────────────────────────────────────────┘
```

## ✨ Features

- **Hierarchical Context** - Automatic L1/L2/L3 context escalation based on message analysis
- **Real-time Chat** - WebSocket-based streaming responses
- **Local AI** - Powered by Ollama (runs entirely on your machine)
- **Conversation Persistence** - Stored in `Nola/Stimuli/conversations/`
- **Modern Stack** - React 18 + TypeScript + Vite + FastAPI
- **User-Owned Data** - Your conversations, your machine, no cloud

## 🚀 Quick Start

### Option 1: One-Command Start (Recommended)

**macOS/Linux:**
```bash
git clone https://github.com/YOUR_USERNAME/react-chat-app.git
cd react-chat-app
chmod +x start.sh
./start.sh
```

**Windows:**
```cmd
git clone https://github.com/YOUR_USERNAME/react-chat-app.git
cd react-chat-app
start.bat
```

The script will:
1. Check/install prerequisites
2. Start Ollama if needed
3. Install dependencies
4. Start backend & frontend
5. Open browser automatically

### Option 2: Docker

```bash
# Ensure Ollama is running on host
ollama serve

# Start with Docker Compose
chmod +x start-docker.sh
./start-docker.sh
```

### Option 3: Manual Setup

#### Prerequisites

1. **Ollama** - https://ollama.ai
   ```bash
   # Install Ollama, then:
   ollama serve
   ollama pull llama3.2:3b  # or your preferred model
   ```

2. **Python 3.11+**
   ```bash
   python3 --version
   ```

3. **Node.js 18+**
   ```bash
   node --version
   ```

#### Setup

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/react-chat-app.git
cd react-chat-app

# Backend setup
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# Frontend setup
cd frontend
npm install
cd ..

# Start backend (Terminal 1)
cd backend
uvicorn main:app --reload --port 8000

# Start frontend (Terminal 2)
cd frontend
npm run dev
```

Open http://localhost:5173 in your browser.

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

## 🔧 Configuration

### Environment Variables

Create `.env` in `react-chat-app/backend/`:
```env
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
HOST=0.0.0.0
PORT=8000
DEBUG=true
```

### Ollama Models

Nola uses these models (configure in `Nola/agent.py`):
- `gpt-oss:20b-cloud` (primary)
- `llama3.2:3b` (fallback)
- `mistral:7b` (fallback)

### Context Levels

The chat automatically selects context depth based on your message:

| Message Type | Context Level | Tokens | Example |
|--------------|---------------|--------|---------|
| Casual | L1 (realtime) | ~10 | "Hi!", "Thanks" |
| Substantive | L2 (conversational) | ~50 | "I'm stressed about work" |
| Analytical | L3 (analytical) | ~200 | "Analyze my productivity patterns" |

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/chat/message` | POST | Send message |
| `/api/chat/history` | GET | Get chat history |
| `/api/chat/agent/status` | GET | Agent status |
| `/api/chat/clear` | POST | Clear history |
| `/ws` | WebSocket | Real-time chat |

## 🐛 Troubleshooting

### "Ollama not found"
```bash
# Install Ollama from https://ollama.ai
# Then run:
ollama serve
```

### "Connection refused" / Network error
```bash
# Check if backend is running
curl http://localhost:8000/health

# Check if frontend is running
curl http://localhost:5173
```

### "Model not found"
```bash
# Pull required models
ollama pull llama3.2:3b
ollama pull mistral:7b
```

### Port already in use
```bash
# macOS/Linux
lsof -ti:8000 | xargs kill -9
lsof -ti:5173 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

## 🛠️ Development

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

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file.

## 🙏 Acknowledgments

- [Ollama](https://ollama.ai) - Local LLM runtime
- [FastAPI](https://fastapi.tiangolo.com) - Modern Python web framework
- [Vite](https://vitejs.dev) - Next-gen frontend tooling
- [React](https://react.dev) - UI library
