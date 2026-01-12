import React, { useState, useCallback } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { ModelSelector } from './ModelSelector';
import { ConversationSidebar } from './ConversationSidebar';
import { SystemPromptSidebar } from './SystemPromptSidebar';
import { useChat } from '../../hooks/useChat';
import { useIntrospection } from '../../hooks/useIntrospection';
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
    isAgentTyping,
    loadConversation,
    sessionId
  } = useChat();

  const { data: introspection } = useIntrospection({ level: 2, pollInterval: 4000, autoStart: true });
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [rightSidebarCollapsed, setRightSidebarCollapsed] = useState(true);

  const handleClearHistory = async () => {
    if (window.confirm('Are you sure you want to clear all chat history?')) {
      await clearHistory();
      onClearHistory?.();
    }
  };

  const handleSelectConversation = useCallback(async (selectedSessionId: string) => {
    if (loadConversation) {
      await loadConversation(selectedSessionId);
    }
  }, [loadConversation]);

  const handleNewConversation = useCallback(async () => {
    await clearHistory();
  }, [clearHistory]);

  return (
    <div className="chat-layout">
      <ConversationSidebar
        currentSessionId={sessionId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        isCollapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
      />
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
          <ModelSelector />
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

      <div className="live-context-bar">
        <div className="context-pill">
          <span className="pill-label">Context</span>
          <span className="pill-value">{introspection?.context?.fact_count ?? 0} facts</span>
        </div>
        <div className="context-pill">
          <span className="pill-label">Threads</span>
          <span className="pill-value">{introspection?.context?.thread_count ?? 0}</span>
        </div>
        <div className="context-pill">
          <span className="pill-label">Level</span>
          <span className="pill-value">L{introspection?.context_level ?? 2}</span>
        </div>
        {introspection?.recent_events?.[0]?.message && (
          <div className="context-note" title={introspection.recent_events[0].message}>
            Last event: {introspection.recent_events[0].message}
          </div>
        )}
      </div>

      <MessageList 
        messages={messages} 
        isAgentTyping={isAgentTyping}
        conversationId={sessionId}
      />
      
      <MessageInput 
        onSendMessage={sendMessage}
        isLoading={isLoading}
        isConnected={isConnected}
      />
      </div>
      <SystemPromptSidebar
        isCollapsed={rightSidebarCollapsed}
        onToggleCollapse={() => setRightSidebarCollapsed(!rightSidebarCollapsed)}
      />
    </div>
  );
};