import React, { useState, useRef, useEffect } from 'react';
import { CHAT_CONFIG } from '../../utils/constants';
import './MessageInput.css';

interface MessageInputProps {
  onSendMessage: (message: string) => void;
  isLoading: boolean;
  isConnected: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  onSendMessage,
  isLoading,
  isConnected
}) => {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const message = input.trim();
    
    if (message && !isLoading && message.length <= CHAT_CONFIG.MAX_MESSAGE_LENGTH) {
      onSendMessage(message);
      setInput('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
  };

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  }, [input]);

  const isDisabled = isLoading || !isConnected || input.length > CHAT_CONFIG.MAX_MESSAGE_LENGTH;
  const remainingChars = CHAT_CONFIG.MAX_MESSAGE_LENGTH - input.length;

  return (
    <div className="message-input-container">
      <form onSubmit={handleSubmit} className="message-input-form">
        <div className="input-wrapper">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder={
              !isConnected 
                ? 'Connecting...' 
                : 'Type your message... (Press Enter to send, Shift+Enter for new line)'
            }
            disabled={isDisabled}
            className={`message-textarea ${input.length > CHAT_CONFIG.MAX_MESSAGE_LENGTH ? 'error' : ''}`}
            rows={1}
          />
          <button 
            type="submit"
            disabled={isDisabled || !input.trim()}
            className="send-button"
          >
            {isLoading ? (
              <div className="loading-spinner" />
            ) : (
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path 
                  d="M2 21L23 12L2 3V10L17 12L2 14V21Z" 
                  fill="currentColor"
                />
              </svg>
            )}
          </button>
        </div>
        
        <div className="input-footer">
          <div className="connection-status">
            <div className={`status-indicator ${isConnected ? 'connected' : 'disconnected'}`} />
            <span className="status-text">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          
          {input.length > 0 && (
            <div className={`char-counter ${remainingChars < 50 ? 'warning' : ''} ${remainingChars < 0 ? 'error' : ''}`}>
              {remainingChars} chars remaining
            </div>
          )}
        </div>
      </form>
    </div>
  );
};