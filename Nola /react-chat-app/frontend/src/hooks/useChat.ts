import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage, AgentStatus } from '../types/chat';
import { useWebSocket } from './useWebSocket';
import { apiService } from '../services/api';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [isAgentTyping, setIsAgentTyping] = useState(false);
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
        // Finalize streaming message if exists
        if (streamingMessageRef.current && streamingMessageIdRef.current) {
          const finalMessage: ChatMessage = {
            id: streamingMessageIdRef.current,
            content: streamingMessageRef.current,
            role: 'assistant',
            timestamp: new Date()
          };
          
          setMessages(prev => {
            // Replace streaming message or add new one
            const existing = prev.find(m => m.id === streamingMessageIdRef.current);
            if (existing) {
              return prev.map(m => 
                m.id === streamingMessageIdRef.current ? finalMessage : m
              );
            } else {
              return [...prev, finalMessage];
            }
          });
          
          streamingMessageRef.current = '';
          streamingMessageIdRef.current = '';
        }
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
    } catch (error) {
      console.error('Failed to clear history:', error);
    }
  }, []);

  return {
    messages,
    sendMessage,
    clearHistory,
    isLoading,
    isConnected,
    agentStatus,
    isAgentTyping
  };
};