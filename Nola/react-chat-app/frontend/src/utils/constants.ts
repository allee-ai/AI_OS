export const API_CONFIG = {
  BASE_URL: 'http://localhost:8000',
  WS_URL: 'ws://localhost:8000/ws',
  ENDPOINTS: {
    CHAT_HISTORY: '/api/chat/history',
    SEND_MESSAGE: '/api/chat/message',
    AGENT_STATUS: '/api/chat/agent/status',
    CLEAR_HISTORY: '/api/chat/clear'
  }
} as const;

export const CHAT_CONFIG = {
  MAX_MESSAGE_LENGTH: 1000,
  TYPING_DELAY_MS: 50,
  RECONNECT_ATTEMPTS: 3,
  RECONNECT_DELAY_MS: 2000
} as const;