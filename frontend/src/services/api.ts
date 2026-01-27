import type { ChatMessage, SendMessageRequest, SendMessageResponse, AgentStatus, ModelsResponse } from '../types/chat';
import { API_CONFIG } from '../utils/constants';

class APIService {
  private baseUrl: string;
  private currentModel: string = 'qwen2.5:7b';

  constructor() {
    this.baseUrl = API_CONFIG.BASE_URL;
  }

  async sendMessage(content: string, sessionId?: string): Promise<SendMessageResponse> {
    const request: SendMessageRequest = {
      content,
      session_id: sessionId,
      model_id: this.currentModel
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

  async getModels(): Promise<ModelsResponse> {
    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.GET_MODELS}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async setModel(modelId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.SET_MODEL}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model_id: modelId }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    this.currentModel = modelId;
  }

  getCurrentModel(): string {
    return this.currentModel;
  }

  setCurrentModelLocal(modelId: string): void {
    this.currentModel = modelId;
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

  async startSession(): Promise<{ session_id: string }> {
    const response = await fetch(`${this.baseUrl}${API_CONFIG.ENDPOINTS.START_SESSION}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async setSession(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/chat/set-session/${sessionId}`, {
      method: 'POST'
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  // Database API methods
  async getDatabaseTables(): Promise<{ tables: string[] }> {
    const response = await fetch(`${this.baseUrl}/api/database/tables`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getIdentityHEA(contextLevel: number = 2): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.DATABASE_IDENTITY_HEA}?context_level=${contextLevel}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getIdentityChanges(contextLevel: number = 2): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.DATABASE_IDENTITY_CHANGES}?context_level=${contextLevel}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getIdentityModule(moduleKey: string, contextLevel: number = 2): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.DATABASE_IDENTITY_MODULE}/${moduleKey}?context_level=${contextLevel}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getThreadsSummary(): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.DATABASE_THREADS_SUMMARY}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getThreadData(threadName: string, contextLevel: number = 2): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}${API_CONFIG.ENDPOINTS.DATABASE_THREAD}/${threadName}?context_level=${contextLevel}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getTableRecords(tableName: string, limit: number = 100, contextLevel: number = 2): Promise<any> {
    const response = await fetch(
      `${this.baseUrl}/api/database/records/${tableName}?limit=${limit}&context_level=${contextLevel}`
    );
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  // Conversations API methods
  async getConversations(limit: number = 50): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/api/conversations?limit=${limit}&archived=false`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getArchivedConversations(limit: number = 50): Promise<any[]> {
    const response = await fetch(`${this.baseUrl}/api/conversations?limit=${limit}&archived=true`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async getConversation(sessionId: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return response.json();
  }

  async renameConversation(sessionId: string, name: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}/rename`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ name }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  async archiveConversation(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}/archive`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  async unarchiveConversation(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}/unarchive`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  async deleteConversation(sessionId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/conversations/${sessionId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
  }

  async createNewConversation(): Promise<{ session_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/conversations/new`, {
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }
}

export const apiService = new APIService();