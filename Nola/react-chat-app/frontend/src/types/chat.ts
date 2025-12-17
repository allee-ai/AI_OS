export interface ChatMessage {
  id: string;
  content: string;
  role: 'user' | 'assistant';
  timestamp: Date;
}

export interface SendMessageRequest {
  content: string;
  session_id?: string;
}

export interface SendMessageResponse {
  message: ChatMessage;
  agent_status: string;
}

export interface AgentStatus {
  status: 'ready' | 'thinking' | 'offline';
  name: string;
  last_interaction?: Date;
}

export interface WebSocketMessage {
  type: 'chat_message' | 'typing_start' | 'typing_stop' | 'agent_response_chunk' | 'agent_typing_start' | 'agent_typing_stop' | 'error';
  content?: string;
  message_id?: string;
  is_final?: boolean;
}