import type { ChatMessage, SendMessageRequest, SendMessageResponse, AgentStatus } from '../types/chat';
import { API_CONFIG } from '../utils/constants';

class APIService {
  private baseUrl: string;

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL;
  }

  async sendMessage(content: string, sessionId?: string): Promise<SendMessageResponse> {
    const request: SendMessageRequest = {
      content,
      session_id: sessionId
    };

    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.SEND_MESSAGE}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      ...data,
      message: {
        ...data.message,
        timestamp: new Date(data.message.timestamp)
      }
    };
  }

  async getChatHistory(limit: number = 50): Promise<ChatMessage[]> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.CHAT_HISTORY}?limit=${limit}`
    );

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data.map((msg: any) => ({
      ...msg,
      timestamp: new Date(msg.timestamp)
    }));
  }

  async getAgentStatus(): Promise<AgentStatus> {
    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.AGENT_STATUS}`);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return {
      ...data,
      last_interaction: data.last_interaction ? new Date(data.last_interaction) : undefined
    };
  }

  async clearChatHistory(): Promise<void> {
    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.CLEAR_HISTORY}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }
}

export const apiService = new APIService();