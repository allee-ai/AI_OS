import { BASE_URL, WS_URL } from '../../../config/api';

export const API_CONFIG = {
  BASE_URL,
  WS_URL,
  ENDPOINTS: {
    CHAT_HISTORY: '/api/chat/history',
    SEND_MESSAGE: '/api/chat/message',
    AGENT_STATUS: '/api/chat/agent-status',
    CLEAR_HISTORY: '/api/chat/clear',
    START_SESSION: '/api/chat/start-session',
    GET_MODELS: '/api/models',
    SET_MODEL: '/api/models/current',
    // Introspection endpoints (now via subconscious)
    INTROSPECTION: '/api/subconscious/state',
    INTROSPECTION_IDENTITY: '/api/identity/introspect',
    INTROSPECTION_THREADS: '/api/subconscious/health',
    INTROSPECTION_CONTEXT: '/api/subconscious/context',
    INTROSPECTION_EVENTS: '/api/log/events'
  }
} as const;

export const CHAT_CONFIG = {
  MAX_MESSAGE_LENGTH: 1000,
  TYPING_DELAY_MS: 50,
  RECONNECT_ATTEMPTS: 3,
  RECONNECT_DELAY_MS: 2000
} as const;
