import { useState, useEffect } from 'react';
import './FeedViewer.css';

interface Message {
  id: string;
  author: string;
  authorAvatar?: string;
  content: string;
  channel: string;
  timestamp: string;
  isBot: boolean;
}

interface Draft {
  id: string;
  channel: string;
  content: string;
  replyTo?: string;
  created: string;
}

type ViewMode = 'messages' | 'drafts' | 'compose';

export default function DiscordViewer() {
  const [viewMode, setViewMode] = useState<ViewMode>('messages');
  const [messages, setMessages] = useState<Message[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [loading, setLoading] = useState(false);

  // Compose state
  const [composeChannel, setComposeChannel] = useState('');
  const [composeContent, setComposeContent] = useState('');

  useEffect(() => {
    if (viewMode === 'messages') {
      fetchMessages();
    } else if (viewMode === 'drafts') {
      fetchDrafts();
    }
  }, [viewMode]);

  const fetchMessages = async () => {
    setLoading(true);
    try {
      // TODO: Connect to actual Discord API
      setMessages([
        {
          id: '1',
          author: 'DevBot',
          content: 'Build completed successfully ✅',
          channel: '#ci-cd',
          timestamp: '2026-02-01T10:45:00Z',
          isBot: true,
        },
        {
          id: '2',
          author: 'TeamMember',
          content: 'Hey @Nola, can you review the latest PR?',
          channel: '#general',
          timestamp: '2026-02-01T10:30:00Z',
          isBot: false,
        },
      ]);
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDrafts = async () => {
    setLoading(true);
    try {
      setDrafts([
        {
          id: 'd1',
          channel: '#general',
          content: 'Sure, I\'ll take a look at the PR now!',
          replyTo: 'TeamMember',
          created: '2026-02-01T10:35:00Z',
        },
      ]);
    } catch (err) {
      console.error('Failed to fetch drafts:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSendDraft = async (draft: Draft) => {
    alert(`Would send to ${draft.channel}: ${draft.content}`);
  };

  const formatTime = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="feed-viewer discord-viewer">
      <div className="viewer-tabs">
        <button 
          className={`tab ${viewMode === 'messages' ? 'active' : ''}`}
          onClick={() => setViewMode('messages')}
        >
          💬 Messages
        </button>
        <button 
          className={`tab ${viewMode === 'drafts' ? 'active' : ''}`}
          onClick={() => setViewMode('drafts')}
        >
          📝 Drafts
        </button>
        <button 
          className={`tab ${viewMode === 'compose' ? 'active' : ''}`}
          onClick={() => setViewMode('compose')}
        >
          ✏️ Compose
        </button>
      </div>

      <div className="viewer-content">
        {loading ? (
          <div className="viewer-loading">Loading...</div>
        ) : viewMode === 'messages' ? (
          <div className="message-list">
            {messages.length === 0 ? (
              <div className="empty-state">No messages yet. Connect Discord to see your DMs and mentions.</div>
            ) : (
              messages.map((msg) => (
                <div key={msg.id} className={`message-item ${msg.isBot ? 'bot' : ''}`}>
                  <div className="message-header">
                    <span className="message-author">{msg.author}</span>
                    <span className="message-channel">{msg.channel}</span>
                    <span className="message-time">{formatTime(msg.timestamp)}</span>
                  </div>
                  <div className="message-content">{msg.content}</div>
                </div>
              ))
            )}
          </div>
        ) : viewMode === 'drafts' ? (
          <div className="drafts-list">
            {drafts.length === 0 ? (
              <div className="empty-state">No drafts. AI-generated replies will appear here.</div>
            ) : (
              drafts.map((draft) => (
                <div key={draft.id} className="draft-item">
                  <div className="draft-header">
                    <span className="draft-channel">{draft.channel}</span>
                    {draft.replyTo && <span className="draft-reply">↩️ {draft.replyTo}</span>}
                  </div>
                  <div className="draft-body">{draft.content}</div>
                  <div className="draft-actions">
                    <button className="btn-send" onClick={() => handleSendDraft(draft)}>
                      📤 Send
                    </button>
                    <button className="btn-edit">✏️ Edit</button>
                    <button className="btn-delete">🗑️ Delete</button>
                  </div>
                </div>
              ))
            )}
          </div>
        ) : (
          <div className="compose-form">
            <div className="form-field">
              <label>Channel</label>
              <input 
                type="text" 
                value={composeChannel} 
                onChange={(e) => setComposeChannel(e.target.value)}
                placeholder="#channel or @user"
              />
            </div>
            <div className="form-field">
              <label>Message</label>
              <textarea 
                value={composeContent} 
                onChange={(e) => setComposeContent(e.target.value)}
                placeholder="Type your message..."
                rows={6}
              />
            </div>
            <div className="compose-actions">
              <button className="btn-primary">📤 Send</button>
              <button className="btn-secondary">💾 Save Draft</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
