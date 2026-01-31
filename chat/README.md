# Chat Module

The **Chat Module** handles all conversation logic in AI OS. It includes the real-time API for the frontend, the database schema for persistent history, and the import system for migrating data from other AI models.

## Components

### 1. API (`api.py`)
Exposes FastAPI endpoints for two main functions:

- **Real-time Chat** (`/api/chat`):
    - Handling user messages
    - interfacing with the `agent` service to generate responses
    - Websocket management
- **Conversation Management** (`/api/conversations`):
    - CRUD operations (List, Get, Rename, Archive, Delete)
    - Session management

### 2. Database Schema (`schema.py`)
Stores conversation history in SQLite.

| Table | Description |
|-------|-------------|
| `convos` | Metadata (Session ID, Name, Last Updated, Turn Count) |
| `convo_turns` | Content (User Message, Assistant Message, Token Counts) |
| `message_ratings` | User feedback (Thumbs up/down) for future fine-tuning |

### 3. Import System (`import_convos.py`)
A powerful utility to port your history from other providers into AI OS.

**Supported Formats:**
- **ChatGPT** (`conversations.json`)
- **Claude** (`conversations.json`)
- **Gemini** (JSON export)
- **VS Code Copilot** (JSON export)

**How it works:**
1. Upload an export file via the UI.
2. `ImportConvos` auto-detects the format using parsers in `parsers/`.
3. Conversations are parsed into a standard format.
4. Data is saved to the SQLite `convos` table (for UI access).
5. Data is optionally written to plain text files in `Feeds/` (for the OS to "read" and learn from later).

## Key Functions

### `save_conversation(session_id, messages)`
Persists a full conversation state. Can update an existing session or create a new one.

### `add_turn(session_id, user_msg, agent_msg)`
Appends a single interaction to the history. This is efficient for real-time chatting as it doesn't rewrite the whole history.

### `ImportConvos.import_conversations()`
The main entry point for the import tool. It handles the extraction, parsing, and storage pipeline asynchronously.

---

## Frontend Module

Located at `frontend/src/modules/chat/`:

```
chat/
├── index.ts                    # Module exports
├── pages/
│   └── ChatPage.tsx            # Main chat view
├── components/
│   ├── ChatContainer.tsx       # Layout wrapper
│   ├── ConversationSidebar.tsx # Session list
│   ├── MessageList.tsx         # Message display
│   ├── MessageInput.tsx        # User input field
│   ├── ModelSelector.tsx       # LLM picker dropdown
│   ├── SystemPromptSidebar.tsx # System prompt editor
│   ├── DatabaseToggle.tsx      # Demo/personal mode switch
│   └── ImportModal.tsx         # Conversation import UI
├── hooks/
│   ├── useChat.ts              # Chat state management
│   └── useWebSocket.ts         # Real-time connection
├── services/
│   └── chatApi.ts              # API client
├── types/
│   └── chat.ts                 # TypeScript interfaces
└── utils/
    └── constants.ts            # API config
```