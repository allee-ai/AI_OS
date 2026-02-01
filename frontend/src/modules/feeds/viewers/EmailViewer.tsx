import { useState, useEffect } from 'react';
import './FeedViewer.css';

interface Email {
  id: string;
  from: string;
  subject: string;
  snippet: string;
  date: string;
  labels: string[];
  unread: boolean;
}

interface Draft {
  id: string;
  to: string;
  subject: string;
  body: string;
  created: string;
}

type ViewMode = 'inbox' | 'drafts' | 'compose';
type Provider = 'gmail' | 'outlook' | 'proton';

interface ProviderStatus {
  connected: boolean;
  email?: string;
}

const API_BASE = 'http://localhost:8000';

const PROVIDERS: { id: Provider; name: string; icon: string; comingSoon?: boolean }[] = [
  { id: 'gmail', name: 'Gmail', icon: '📧' },
  { id: 'outlook', name: 'Outlook', icon: '📬' },
  { id: 'proton', name: 'Proton', icon: '🔒', comingSoon: true },
];

export default function EmailViewer() {
  const [activeProvider, setActiveProvider] = useState<Provider>('gmail');
  const [viewMode, setViewMode] = useState<ViewMode>('inbox');
  const [emails, setEmails] = useState<Email[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [loading, setLoading] = useState(false);
  const [providerStatus, setProviderStatus] = useState<Record<Provider, ProviderStatus>>({
    gmail: { connected: false },
    outlook: { connected: false },
    proton: { connected: false },
  });

  // Compose state
  const [composeTo, setComposeTo] = useState('');
  const [composeSubject, setComposeSubject] = useState('');
  const [composeBody, setComposeBody] = useState('');

  useEffect(() => {
    checkProviderStatus();
  }, []);

  useEffect(() => {
    if (providerStatus[activeProvider].connected) {
      if (viewMode === 'inbox') {
        fetchInbox();
      } else if (viewMode === 'drafts') {
        fetchDrafts();
      }
    }
  }, [activeProvider, viewMode, providerStatus]);

  const checkProviderStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/providers/status`);
      if (res.ok) {
        const data = await res.json();
        setProviderStatus(data);
      }
    } catch (err) {
      console.error('Failed to check provider status:', err);
    }
  };

  const handleConnect = (provider: Provider) => {
    // Redirect to OAuth flow
    window.location.href = `${API_BASE}/api/feeds/email/oauth/start?provider=${provider}`;
  };

  const fetchInbox = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/messages`);
      if (res.ok) {
        const data = await res.json();
        setEmails(data);
      }
    } catch (err) {
      console.error('Failed to fetch inbox:', err);
      // Show placeholder data for demo
      setEmails([
        {
          id: '1',
          from: 'team@example.com',
          subject: 'Weekly Update',
          snippet: 'Here are the highlights from this week...',
          date: '2026-02-01T10:30:00Z',
          labels: ['INBOX', 'UNREAD'],
          unread: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fetchDrafts = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/drafts`);
      if (res.ok) {
        const data = await res.json();
        setDrafts(data);
      }
    } catch (err) {
      console.error('Failed to fetch drafts:', err);
      setDrafts([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSendDraft = async (draft: Draft) => {
    try {
      await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: draft.to, subject: draft.subject, body: draft.body }),
      });
      fetchDrafts();
    } catch (err) {
      console.error('Failed to send:', err);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const currentStatus = providerStatus[activeProvider];
  const currentProviderConfig = PROVIDERS.find(p => p.id === activeProvider)!;

  return (
    <div className="feed-viewer email-viewer">
      {/* Provider Tabs */}
      <div className="provider-tabs">
        {PROVIDERS.map((provider) => (
          <button
            key={provider.id}
            className={`provider-tab ${activeProvider === provider.id ? 'active' : ''} ${provider.comingSoon ? 'coming-soon' : ''}`}
            onClick={() => !provider.comingSoon && setActiveProvider(provider.id)}
            disabled={provider.comingSoon}
          >
            <span className="provider-icon">{provider.icon}</span>
            <span className="provider-name">{provider.name}</span>
            {providerStatus[provider.id]?.connected && <span className="connected-dot">●</span>}
            {provider.comingSoon && <span className="coming-soon-badge">Soon</span>}
          </button>
        ))}
      </div>

      {/* Not Connected State */}
      {!currentStatus.connected && !currentProviderConfig.comingSoon ? (
        <div className="connect-prompt">
          <div className="connect-icon">{currentProviderConfig.icon}</div>
          <h3>Connect {currentProviderConfig.name}</h3>
          <p>Connect your {currentProviderConfig.name} account to see your inbox, manage drafts, and send emails.</p>
          <button className="connect-btn" onClick={() => handleConnect(activeProvider)}>
            Connect with {currentProviderConfig.name}
          </button>
        </div>
      ) : currentProviderConfig.comingSoon ? (
        <div className="connect-prompt">
          <div className="connect-icon">{currentProviderConfig.icon}</div>
          <h3>{currentProviderConfig.name} Coming Soon</h3>
          <p>We're working on {currentProviderConfig.name} integration. Check back soon!</p>
        </div>
      ) : (
        <>
          {/* View Mode Tabs */}
          <div className="viewer-tabs">
            <button className={`tab ${viewMode === 'inbox' ? 'active' : ''}`} onClick={() => setViewMode('inbox')}>
              📥 Inbox
            </button>
            <button className={`tab ${viewMode === 'drafts' ? 'active' : ''}`} onClick={() => setViewMode('drafts')}>
              📝 Drafts
            </button>
            <button className={`tab ${viewMode === 'compose' ? 'active' : ''}`} onClick={() => setViewMode('compose')}>
              ✏️ Compose
            </button>
          </div>

          <div className="viewer-content">
            {loading ? (
              <div className="viewer-loading">Loading...</div>
            ) : viewMode === 'inbox' ? (
              <div className="email-list">
                {emails.length === 0 ? (
                  <div className="empty-state">No emails yet.</div>
                ) : (
                  emails.map((email) => (
                    <div
                      key={email.id}
                      className={`email-item ${email.unread ? 'unread' : ''} ${selectedEmail?.id === email.id ? 'selected' : ''}`}
                      onClick={() => setSelectedEmail(email)}
                    >
                      <div className="email-from">{email.from}</div>
                      <div className="email-subject">{email.subject}</div>
                      <div className="email-snippet">{email.snippet}</div>
                      <div className="email-date">{formatDate(email.date)}</div>
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
                        <span className="draft-to">To: {draft.to}</span>
                        <span className="draft-date">{formatDate(draft.created)}</span>
                      </div>
                      <div className="draft-subject">{draft.subject}</div>
                      <div className="draft-body">{draft.body}</div>
                      <div className="draft-actions">
                        <button className="btn-send" onClick={() => handleSendDraft(draft)}>📤 Send</button>
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
                  <label>To</label>
                  <input type="email" value={composeTo} onChange={(e) => setComposeTo(e.target.value)} placeholder="recipient@example.com" />
                </div>
                <div className="form-field">
                  <label>Subject</label>
                  <input type="text" value={composeSubject} onChange={(e) => setComposeSubject(e.target.value)} placeholder="Subject line" />
                </div>
                <div className="form-field">
                  <label>Message</label>
                  <textarea value={composeBody} onChange={(e) => setComposeBody(e.target.value)} placeholder="Write your message..." rows={8} />
                </div>
                <div className="compose-actions">
                  <button className="btn-primary">📤 Send</button>
                  <button className="btn-secondary">💾 Save Draft</button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
