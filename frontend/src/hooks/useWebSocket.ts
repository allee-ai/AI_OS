import { useEffect, useRef, useState, useCallback } from 'react';
import type { WebSocketMessage } from '../types/chat';
import { API_CONFIG, CHAT_CONFIG } from '../utils/constants';

export const useWebSocket = () => {
  const ws = useRef<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [connectionAttempts, setConnectionAttempts] = useState(0);

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      return;
    }

    try {
      ws.current = new WebSocket(API_CONFIG.WS_URL);

      ws.current.onopen = () => {
        setIsConnected(true);
        setConnectionAttempts(0);
        console.log('WebSocket connected');
      };

      ws.current.onmessage = (event) => {
        try {
          const data: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(data);
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.current.onclose = (event) => {
        setIsConnected(false);
        console.log('WebSocket disconnected', event.code, event.reason);

        // Auto-reconnect logic
        if (connectionAttempts < CHAT_CONFIG.RECONNECT_ATTEMPTS) {
          setTimeout(() => {
            setConnectionAttempts(prev => prev + 1);
            connect();
          }, CHAT_CONFIG.RECONNECT_DELAY_MS);
        }
      };

      ws.current.onerror = (error) => {
        console.error('WebSocket error:', error);
        setIsConnected(false);
      };
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [connectionAttempts]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
      ws.current = null;
      setIsConnected(false);
    }
  }, []);

  const sendMessage = useCallback((message: Partial<WebSocketMessage>) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
      return true;
    }
    return false;
  }, []);

  useEffect(() => {
    connect();
    return () => {
      disconnect();
    };
  }, []);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    connect,
    disconnect,
    connectionAttempts
  };
};