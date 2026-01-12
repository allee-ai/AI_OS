# React Chat App

The web interface for talking to Nola.

---

## For Users

This is the chat window you see in your browser. Just type and talk — Nola handles the rest.

**Starting the app:**
```bash
# From project root
./start.sh
```

Your browser opens automatically to `http://localhost:5173`.

---

## For Developers

### Structure

```
react-chat-app/
├── backend/              # FastAPI server (Python)
│   ├── main.py           # App entry, WebSocket handler
│   ├── api/
│   │   ├── chat.py       # /api/chat/* endpoints
│   │   ├── database.py   # /api/database/* endpoints
│   │   └── websockets.py # Real-time handler
│   └── models/           # Pydantic schemas
│
└── frontend/             # React + Vite (TypeScript)
    ├── src/
    │   ├── components/   # UI components
    │   ├── hooks/        # React hooks
    │   └── services/     # API client
    └── public/           # Static assets
```

### Running Separately

```bash
# Backend (terminal 1)
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat/message` | POST | Send message, get response |
| `/api/chat/history` | GET | Retrieve conversation history |
| `/api/database/identity` | GET | Get identity by level |
| `/ws` | WebSocket | Real-time chat |

### Docker

```bash
cd react-chat-app
docker-compose up --build
```
