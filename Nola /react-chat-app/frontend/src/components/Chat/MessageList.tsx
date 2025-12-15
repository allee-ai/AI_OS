import React from 'react';
import type { ChatMessage } from '../../types/chat';
import './MessageList.css';

interface MessageListProps {
  messages: ChatMessage[];
  isAgentTyping?: boolean;
}

export const MessageList: React.FC<MessageListProps> = ({ 
  messages, 
  isAgentTyping = false 
}) => {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  React.useEffect(() => {
    scrollToBottom();
  }, [messages, isAgentTyping]);

  const formatTime = (timestamp: Date) => {
    return new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    }).format(timestamp);
  };

  return (
    <div className="message-list">
      <div className="messages-container">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
          >
            <div className="message-content">
              <div className="message-text">{message.content}</div>
              <div className="message-timestamp">
                {formatTime(message.timestamp)}
              </div>
            </div>
          </div>
        ))}
        
        {isAgentTyping && (
          <div className="message assistant-message">
            <div className="message-content">
              <div className="typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};