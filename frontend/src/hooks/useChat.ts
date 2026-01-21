import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage, AgentStatus } from '../types/chat';
import { useWebSocket } from './useWebSocket';
import { apiService } from '../services/api';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [isAgentTyping, setIsAgentTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const streamingMessageRef = useRef<string>('');
  const streamingMessageIdRef = useRef<string>('');

  const { isConnected, lastMessage, sendMessage: sendWS } = useWebSocket();

  // Load initial chat history
  useEffect(() => {
    const loadHistory = async () => {
      try {
        const history = await apiService.getChatHistory();
        setMessages(history);
      } catch (error) {
        console.error('Failed to load chat history:', error);
      }
    };

    loadHistory();
  }, []);

  // Load agent status
  useEffect(() => {
    const loadAgentStatus = async () => {
      try {
        const status = await apiService.getAgentStatus();
        setAgentStatus(status);
      } catch (error) {
        console.error('Failed to load agent status:', error);
      }
    };

    loadAgentStatus();
  }, []);

  // Handle WebSocket messages
  useEffect(() => {
    if (!lastMessage) return;

    switch (lastMessage.type) {
      case 'agent_typing_start':
        setIsAgentTyping(true);
        break;

      case 'agent_typing_stop':
        setIsAgentTyping(false);
        // Clear streaming refs (message already finalized by last chunk)
        streamingMessageRef.current = '';
        streamingMessageIdRef.current = '';
        break;

      case 'agent_response_chunk':
        if (lastMessage.content && lastMessage.message_id) {
          streamingMessageRef.current = lastMessage.content;
          streamingMessageIdRef.current = lastMessage.message_id;

          // Update or create streaming message
          setMessages(prev => {
            const streamingMessage: ChatMessage = {
              id: lastMessage.message_id!,
              content: lastMessage.content!,
              role: 'assistant',
              timestamp: new Date()
            };

            const existing = prev.find(m => m.id === lastMessage.message_id);
            if (existing) {
              return prev.map(m => 
                m.id === lastMessage.message_id ? streamingMessage : m
              );
            } else {
              return [...prev, streamingMessage];
            }
          });
        }
        break;

      case 'error':
        console.error('WebSocket error:', lastMessage.content);
        setIsLoading(false);
        setIsAgentTyping(false);
        break;
    }
  }, [lastMessage]);

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim()) return;

    setIsLoading(true);

    // Add user message immediately
    const userMessage: ChatMessage = {
      id: `user_${Date.now()}`,
      content: content.trim(),
      role: 'user',
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);

    try {
      if (isConnected) {
        // Use WebSocket for real-time streaming
        const success = sendWS({
          type: 'chat_message',
          content: content.trim()
        });

        if (!success) {
          throw new Error('Failed to send WebSocket message');
        }
      } else {
        // Fallback to HTTP API
        const response = await apiService.sendMessage(content.trim());
        const assistantMessage: ChatMessage = {
          ...response.message,
          timestamp: new Date(response.message.timestamp)
        };
        setMessages(prev => [...prev, assistantMessage]);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      
      // Add error message
      const errorMessage: ChatMessage = {
        id: `error_${Date.now()}`,
        content: 'Sorry, I encountered an error processing your message. Please try again.',
        role: 'assistant',
        timestamp: new Date()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [isConnected, sendWS]);

  const clearHistory = useCallback(async () => {
    try {
      await apiService.clearChatHistory();
      setMessages([]);
      setSessionId(undefined);
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  }, []);

  const startNewSession = useCallback(async () => {
    try {
      // Start new session and get Nola's proactive intro
      const { message: introMessage } = await apiService.startSession();
      setMessages([introMessage]);
      setSessionId(undefined);
    } catch (error) {
      console.error('Failed to start session:', error);
      // Fallback to just clearing
      await clearHistory();
    }
  }, [clearHistory]);

  const loadConversation = useCallback(async (conversationSessionId: string) => {
    try {
      const conversation = await apiService.getConversation(conversationSessionId);
      
      // Convert turns to messages
      const loadedMessages: ChatMessage[] = [];
      for (const turn of conversation.turns || []) {
        if (turn.user) {
          loadedMessages.push({
            id: `user_${turn.timestamp}`,
            content: turn.user,
            role: 'user',
            timestamp: new Date(turn.timestamp)
          });
        }
        if (turn.assistant) {
          loadedMessages.push({
            id: `assistant_${turn.timestamp}`,
            content: turn.assistant,
            role: 'assistant',
            timestamp: new Date(turn.timestamp)
          });
        }
      }
      
      setMessages(loadedMessages);
      setSessionId(conversationSessionId);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, []);

  return {
    messages,
    sendMessage,
    clearHistory,
    startNewSession,
    loadConversation,
    isLoading,
    isConnected,
    agentStatus,
    isAgentTyping,
    sessionId
  };
};