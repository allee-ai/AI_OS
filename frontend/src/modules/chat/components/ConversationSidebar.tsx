import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/chatApi';
import { ImportModal } from './ImportModal';
import './ConversationSidebar.css';

interface Conversation {
  session_id: string;
  name: string;
  started: string;
  turn_count: number;
  last_message?: string;
  preview?: string;
  archived?: boolean;
}

interface ConversationSidebarProps {
  currentSessionId?: string;
  onSelectConversation: (sessionId: string) => void;
  onNewConversation: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  currentSessionId,
  onSelectConversation,
  onNewConversation,
  isCollapsed = false,
  onToggleCollapse
}) => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [archivedConversations, setArchivedConversations] = useState<Conversation[]>([]);
  const [showArchive, setShowArchive] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [editName, setEditName] = useState('');

  const loadConversations = useCallback(async () => {
    try {
      const data = await apiService.getConversations();
      setConversations(data);
      
      // Also load archived conversations
      const archived = await apiService.getArchivedConversations();
      setArchivedConversations(archived);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConversations();
    // Refresh every 10 seconds to pick up auto-naming
    const interval = setInterval(loadConversations, 10000);
    return () => clearInterval(interval);
  }, [loadConversations]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    if (window.confirm('Delete this conversation?')) {
      try {
        await apiService.deleteConversation(sessionId);
        setConversations(prev => prev.filter(c => c.session_id !== sessionId));
        setArchivedConversations(prev => prev.filter(c => c.session_id !== sessionId));
      } catch (error) {
        console.error('Failed to delete conversation:', error);
      }
    }
  };

  const handleArchive = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await apiService.archiveConversation(sessionId);
      await loadConversations();
    } catch (error) {
      console.error('Failed to archive conversation:', error);
    }
  };

  const handleUnarchive = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await apiService.unarchiveConversation(sessionId);
      await loadConversations();
    } catch (error) {
      console.error('Failed to unarchive conversation:', error);
    }
  };

  const handleRename = async (sessionId: string) => {
    if (!editName.trim()) {
      setEditingId(null);
      return;
    }
    
    try {
      await apiService.renameConversation(sessionId, editName.trim());
      setConversations(prev => 
        prev.map(c => c.session_id === sessionId ? { ...c, name: editName.trim() } : c)
      );
    } catch (error) {
      console.error('Failed to rename conversation:', error);
    }
    setEditingId(null);
  };

  const startEditing = (e: React.MouseEvent, conversation: Conversation) => {
    e.stopPropagation();
    setEditingId(conversation.session_id);
    setEditName(conversation.name);
  };

  const formatDate = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const diffDays = Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
      
      if (diffDays === 0) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } else if (diffDays === 1) {
        return 'Yesterday';
      } else if (diffDays < 7) {
        return date.toLocaleDateString([], { weekday: 'short' });
      } else {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
      }
    } catch {
      return '';
    }
  };

  if (isCollapsed) {
    return (
      <div className="conversation-sidebar collapsed">
        <button className="collapse-toggle" onClick={onToggleCollapse} title="Expand sidebar">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M9 18L15 12L9 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
        <button className="new-chat-icon" onClick={onNewConversation} title="New conversation">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
            <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
    );
  }

  return (
    <div className="conversation-sidebar">
      <div className="sidebar-header">
        <div className="sidebar-actions">
          <button className="new-chat-button" onClick={onNewConversation}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 5V19M5 12H19" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            New Chat
          </button>
          <button className="import-button" onClick={() => setShowImportModal(true)} title="Import conversations">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            Import
          </button>
          <button className="settings-button" onClick={() => alert('Settings coming soon!')} title="Chat settings">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
              <path d="M12 1V3M12 21V23M4.22 4.22L5.64 5.64M18.36 18.36L19.78 19.78M1 12H3M21 12H23M4.22 19.78L5.64 18.36M18.36 5.64L19.78 4.22" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
            </svg>
            Settings
          </button>
        </div>
        {onToggleCollapse && (
          <button className="collapse-toggle" onClick={onToggleCollapse} title="Collapse sidebar">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M15 18L9 12L15 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
        )}
      </div>

      <div className="conversations-list">
        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : (
          <>
            {conversations.length === 0 ? (
              <div className="empty-state">No conversations yet</div>
            ) : (
              conversations.map(conversation => (
                <div
                  key={conversation.session_id}
                  className={`conversation-item ${conversation.session_id === currentSessionId ? 'active' : ''}`}
                  onClick={() => onSelectConversation(conversation.session_id)}
                >
                  {editingId === conversation.session_id ? (
                    <input
                      type="text"
                      className="rename-input"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onBlur={() => handleRename(conversation.session_id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleRename(conversation.session_id);
                        if (e.key === 'Escape') setEditingId(null);
                      }}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                    />
                  ) : (
                    <>
                      <div className="conversation-info">
                        <span className="conversation-name" title={conversation.name}>
                          {conversation.name}
                        </span>
                        <span className="conversation-meta">
                          {formatDate(conversation.started)} · {conversation.turn_count} turns
                        </span>
                      </div>
                      <div className="conversation-actions">
                        <button 
                          className="action-btn" 
                          onClick={(e) => startEditing(e, conversation)}
                          title="Rename"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path d="M11 4H4C3.46957 4 2.96086 4.21071 2.58579 4.58579C2.21071 4.96086 2 5.46957 2 6V20C2 20.5304 2.21071 21.0391 2.58579 21.4142C2.96086 21.7893 3.46957 22 4 22H18C18.5304 22 19.0391 21.7893 19.4142 21.4142C19.7893 21.0391 20 20.5304 20 20V13" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M18.5 2.5C18.8978 2.10217 19.4374 1.87868 20 1.87868C20.5626 1.87868 21.1022 2.10217 21.5 2.5C21.8978 2.89782 22.1213 3.43739 22.1213 4C22.1213 4.56261 21.8978 5.10217 21.5 5.5L12 15L8 16L9 12L18.5 2.5Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                        <button 
                          className="action-btn" 
                          onClick={(e) => handleArchive(e, conversation.session_id)}
                          title="Archive"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path d="M21 8V21H3V8M1 3H23V8H1V3Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M10 12H14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                        <button 
                          className="action-btn delete" 
                          onClick={(e) => handleDelete(e, conversation.session_id)}
                          title="Delete"
                        >
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                            <path d="M3 6H5H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                          </svg>
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ))
            )}

            {/* Divider before archive */}
            {archivedConversations.length > 0 && (
              <div className="section-divider">
                <span>Archive</span>
              </div>
            )}

            {/* Archive section - always show if there are archived conversations */}
            {archivedConversations.length > 0 && (
            <div className="archive-section">
              <button 
                className="archive-toggle" 
                onClick={() => setShowArchive(!showArchive)}
              >
                <svg 
                  width="14" 
                  height="14" 
                  viewBox="0 0 24 24" 
                  fill="none"
                  style={{ transform: showArchive ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}
                >
                  <path d="M9 18L15 12L9 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                Archived Conversations ({archivedConversations.length})
              </button>
              
              {showArchive && archivedConversations.map(conversation => (
                <div
                  key={conversation.session_id}
                  className={`conversation-item archived ${conversation.session_id === currentSessionId ? 'active' : ''}`}
                  onClick={() => onSelectConversation(conversation.session_id)}
                >
                  <div className="conversation-info">
                    <span className="conversation-name" title={conversation.name}>
                      {conversation.name}
                    </span>
                    <span className="conversation-meta">
                      {formatDate(conversation.started)} · {conversation.turn_count} turns
                    </span>
                  </div>
                  <div className="conversation-actions">
                    <button 
                      className="action-btn" 
                      onClick={(e) => handleUnarchive(e, conversation.session_id)}
                      title="Unarchive"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path d="M21 8V21H3V8M1 3H23V8H1V3Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M10 12H14" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M12 12V16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    <button 
                      className="action-btn delete" 
                      onClick={(e) => handleDelete(e, conversation.session_id)}
                      title="Delete"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                        <path d="M3 6H5H21" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
          </>
        )}

      <ImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onImportComplete={() => loadConversations()}
      />
      </div>
    </div>
  );
};
