import { useState, useEffect, useCallback, useRef } from 'react';
import type { ChatMessage, AgentStatus } from '../types/chat';
import { useWebSocket } from './useWebSocket';
import { apiService } from '../services/chatApi';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [isAgentTyping, setIsAgentTyping] = useState(false);
  const [sessionId, setSessionId] = useState<string | undefined>();
  const [totalTurns, setTotalTurns] = useState(0);
  const [loadedTurnCount, setLoadedTurnCount] = useState(0);
  const streamingMessageRef = useRef<string>('');
  const streamingMessageIdRef = useRef<string>('');

  const PAGE_SIZE = 50;
  const hasMoreMessages = loadedTurnCount < totalTurns;

  const { isConnected, lastMessage, sendMessage: sendWS } = useWebSocket();

  // Load initial chat history or start new session
  useEffect(() => {
    const initializeChat = async () => {
      try {
        const history = await apiService.getChatHistory();
        
        if (history.length === 0) {
          // No history - start a fresh session
          const { session_id } = await apiService.startSession();
          setSessionId(session_id);
        } else {
          setMessages(history);
        }
      } catch (error) {
        console.error('Failed to initialize chat:', error);
      }
    };

    initializeChat();
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

  const sendMessage = useCallback(async (content: string, overrides?: { provider?: string; model?: string; endpoint?: string }) => {
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
          content: content.trim(),
          ...(overrides?.provider ? { provider: overrides.provider } : {}),
          ...(overrides?.model ? { model: overrides.model } : {}),
          ...(overrides?.endpoint ? { endpoint: overrides.endpoint } : {}),
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
      const { session_id } = await apiService.startSession();
      setMessages([]);
      setSessionId(session_id);
    } catch (error) {
      console.error('Failed to start session:', error);
      await clearHistory();
    }
  }, [clearHistory]);

  const turnsToMessages = (turns: any[]): ChatMessage[] => {
    const msgs: ChatMessage[] = [];
    for (const turn of turns) {
      if (turn.user) {
        msgs.push({
          id: `user_${turn.timestamp}`,
          content: turn.user,
          role: 'user',
          timestamp: new Date(turn.timestamp)
        });
      }
      if (turn.assistant) {
        msgs.push({
          id: `assistant_${turn.timestamp}`,
          content: turn.assistant,
          role: 'assistant',
          timestamp: new Date(turn.timestamp)
        });
      }
    }
    return msgs;
  };

  const loadConversation = useCallback(async (conversationSessionId: string) => {
    try {
      // Tell backend to use this session
      await apiService.setSession(conversationSessionId);
      
      const conversation = await apiService.getConversation(conversationSessionId, PAGE_SIZE);
      const total = conversation.total_turns ?? conversation.turns?.length ?? 0;
      const turnCount = conversation.turns?.length ?? 0;
      
      setMessages(turnsToMessages(conversation.turns || []));
      setTotalTurns(total);
      setLoadedTurnCount(turnCount);
      setSessionId(conversationSessionId);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, []);

  const loadOlderMessages = useCallback(async () => {
    if (!sessionId || !hasMoreMessages) return;
    try {
      const olderOffset = totalTurns - loadedTurnCount - PAGE_SIZE;
      const offset = Math.max(0, olderOffset);
      const limit = olderOffset < 0 ? PAGE_SIZE + olderOffset : PAGE_SIZE;
      
      const conversation = await apiService.getConversation(sessionId, limit, offset);
      const olderMessages = turnsToMessages(conversation.turns || []);
      
      setMessages(prev => [...olderMessages, ...prev]);
      setLoadedTurnCount(prev => prev + (conversation.turns?.length ?? 0));
    } catch (error) {
      console.error('Failed to load older messages:', error);
    }
  }, [sessionId, hasMoreMessages, totalTurns, loadedTurnCount]);

  return {
    messages,
    sendMessage,
    clearHistory,
    startNewSession,
    loadConversation,
    loadOlderMessages,
    hasMoreMessages,
    isLoading,
    isConnected,
    agentStatus,
    isAgentTyping,
    sessionId
  };
};