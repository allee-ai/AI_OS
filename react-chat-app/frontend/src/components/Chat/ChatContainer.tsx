import React from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useChat } from '../../hooks/useChat';
import './ChatContainer.css';

interface ChatContainerProps {
  onClearHistory?: () => void;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({ onClearHistory }) => {
  const { 
    messages, 
    sendMessage, 
    clearHistory,
    isLoading, 
    isConnected, 
    agentStatus,
    isAgentTyping 
  } = useChat();

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to clear all chat history?')) {
      await clearHistory();
      onClearHistory?.();
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <div className="agent-info">
          <div className="agent-avatar">
            <div className={`avatar-indicator ${agentStatus?.status || 'offline'}`}>
              🧠
            </div>
          </div>
          <div className="agent-details">
            <h3 className="agent-name">{agentStatus?.name || 'Nola'}</h3>
            <div className="agent-status">
              <div className={`status-dot ${agentStatus?.status || 'offline'}`} />
              <span className="status-text">
                {isAgentTyping ? 'Thinking...' : agentStatus?.status || 'offline'}
              </span>
            </div>
          </div>
        </div>
        
        <div className="chat-actions">
          {messages.length > 0 && (
            <button 
              onClick={handleClearHistory}
              className="clear-button"
              title="Clear chat history"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path 
                  d="M6 7H5V5A1 1 0 016 4H18A1 1 0 0119 5V7H18M8 5V7H16V5H8M6 7V19A2 2 0 008 21H16A2 2 0 0018 19V7H6Z" 
                  stroke="currentColor" 
                  strokeWidth="2" 
                  fill="none"
                />
              </svg>
            </button>
          )}
        </div>
      </div>

      <MessageList 
        messages={messages} 
        isAgentTyping={isAgentTyping}
      />
      
      <MessageInput 
        onSendMessage={sendMessage}
        isLoading={isLoading}
        isConnected={isConnected}
      />
    </div>
  );
};