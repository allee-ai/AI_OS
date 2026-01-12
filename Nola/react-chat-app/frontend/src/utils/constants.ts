export const API_CONFIG = {
  BASE_URL: 'http://localhost:8000',
  WS_URL: 'ws://localhost:8000/ws',
  ENDPOINTS: {
    CHAT_HISTORY: '/api/chat/history',
    SEND_MESSAGE: '/api/chat/message',
    AGENT_STATUS: '/api/chat/agent/status',
    CLEAR_HISTORY: '/api/chat/clear',
    GET_MODELS: '/api/models',
    SET_MODEL: '/api/models/current',
    // Introspection endpoints (trailing slashes required by FastAPI)
    INTROSPECTION: '/api/introspection/',
    INTROSPECTION_IDENTITY: '/api/introspection/identity',
    INTROSPECTION_THREADS: '/api/introspection/threads',
    INTROSPECTION_CONTEXT: '/api/introspection/context',
    INTROSPECTION_EVENTS: '/api/introspection/events',
    // Database endpoints (new thread system)
    DATABASE_TABLES: '/api/database/tables',
    DATABASE_THREADS_SUMMARY: '/api/database/threads-summary',
    DATABASE_THREAD: '/api/database/thread',  // + /{thread_name}
    DATABASE_IDENTITY_HEA: '/api/database/identity-hea',
    DATABASE_IDENTITY_MODULE: '/api/database/identity',  // + /{module_key}
    DATABASE_IDENTITY_CHANGES: '/api/database/identity-changes'
  }
} as const;

export const CHAT_CONFIG = {
  MAX_MESSAGE_LENGTH: 1000,
  TYPING_DELAY_MS: 50,
  RECONNECT_ATTEMPTS: 3,
  RECONNECT_DELAY_MS: 2000
} as const;