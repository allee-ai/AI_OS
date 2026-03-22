import { useState, useEffect } from 'react';
import { BASE_URL } from '../../../config/api';
import './FeedViewer.css';

const API_BASE = BASE_URL;

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

interface TriageResult {
  id: string;
  from: string;
  subject: string;
  priority: 'urgent' | 'high' | 'normal' | 'low';
  category: string;
  reason: string;
}

type ViewMode = 'inbox' | 'drafts' | 'compose' | 'triage' | 'digest';
type Provider = 'gmail' | 'outlook' | 'proton';

interface ProviderStatus {
  connected: boolean;
  email?: string;
}

const PROVIDERS: { id: Provider; name: string; icon: string }[] = [
  { id: 'gmail', name: 'Gmail', icon: '📧' },
  { id: 'outlook', name: 'Outlook', icon: '📬' },
  { id: 'proton', name: 'Proton', icon: '🔒' },
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
  const [sending, setSending] = useState(false);

  // Proton Bridge state
  const [protonUser, setProtonUser] = useState('');
  const [protonPass, setProtonPass] = useState('');

  // Intelligence state
  const [threadSummary, setThreadSummary] = useState<string | null>(null);
  const [smartReplies, setSmartReplies] = useState<string[]>([]);
  const [triageResults, setTriageResults] = useState<TriageResult[]>([]);
  const [digestText, setDigestText] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [actionItems, setActionItems] = useState<{task: string; assignee: string | null; deadline: string | null}[]>([]);

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

  const handleConnect = async (provider: Provider) => {
    if (provider === 'proton') return; // handled by bridge form
    // Redirect to OAuth flow
    window.location.href = `${API_BASE}/api/feeds/email/oauth/start?provider=${provider}`;
  };

  const handleConnectProton = async () => {
    if (!protonUser || !protonPass) return;
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/proton/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imap_user: protonUser, imap_password: protonPass }),
      });
      if (res.ok) {
        checkProviderStatus();
        setProtonUser('');
        setProtonPass('');
      }
    } catch (err) {
      console.error('Failed to connect Proton:', err);
    }
  };

  const handleComposeSend = async () => {
    if (!composeTo || !composeSubject) return;
    setSending(true);
    try {
      await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to: composeTo, subject: composeSubject, body: composeBody }),
      });
      setComposeTo('');
      setComposeSubject('');
      setComposeBody('');
      setViewMode('inbox');
      fetchInbox();
    } catch (err) {
      console.error('Failed to send:', err);
    } finally {
      setSending(false);
    }
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

  // ── Intelligence handlers ──

  const handleSummarize = async (email: Email) => {
    setAiLoading(true);
    setThreadSummary(null);
    setActionItems([]);
    setSmartReplies([]);
    try {
      const msgs = [{ from: email.from, subject: email.subject, snippet: email.snippet, date: email.date }];
      const [sumRes, actRes, repRes] = await Promise.all([
        fetch(`${API_BASE}/api/feeds/email/${activeProvider}/summarize`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: msgs }),
        }),
        fetch(`${API_BASE}/api/feeds/email/${activeProvider}/action-items`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ messages: msgs }),
        }),
        fetch(`${API_BASE}/api/feeds/email/${activeProvider}/smart-replies`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: { from: email.from, subject: email.subject, snippet: email.snippet } }),
        }),
      ]);
      if (sumRes.ok) { const d = await sumRes.json(); setThreadSummary(d.summary); }
      if (actRes.ok) { const d = await actRes.json(); setActionItems(d.action_items || []); }
      if (repRes.ok) { const d = await repRes.json(); setSmartReplies(d.replies || []); }
    } catch (err) {
      console.error('Intelligence error:', err);
    } finally {
      setAiLoading(false);
    }
  };

  const handleTriage = async () => {
    setAiLoading(true);
    setTriageResults([]);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/triage`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setTriageResults(data.results || []);
        setViewMode('triage');
      }
    } catch (err) {
      console.error('Triage error:', err);
    } finally {
      setAiLoading(false);
    }
  };

  const handleDigest = async () => {
    setAiLoading(true);
    setDigestText(null);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/email/${activeProvider}/digest`, {
        method: 'POST',
      });
      if (res.ok) {
        const data = await res.json();
        setDigestText(data.digest);
        setViewMode('digest');
      }
    } catch (err) {
      console.error('Digest error:', err);
    } finally {
      setAiLoading(false);
    }
  };

  const handleUseReply = (reply: string) => {
    setComposeBody(reply);
    if (selectedEmail) {
      setComposeTo(selectedEmail.from);
      setComposeSubject(selectedEmail.subject.startsWith('Re:') ? selectedEmail.subject : `Re: ${selectedEmail.subject}`);
    }
    setViewMode('compose');
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
            className={`provider-tab ${activeProvider === provider.id ? 'active' : ''}`}
            onClick={() => setActiveProvider(provider.id)}
          >
            <span className="provider-icon">{provider.icon}</span>
            <span className="provider-name">{provider.name}</span>
            {providerStatus[provider.id]?.connected && <span className="connected-dot">●</span>}
          </button>
        ))}
      </div>

      {/* Not Connected State */}
      {!currentStatus.connected ? (
        <div className="connect-prompt">
          <div className="connect-icon">{currentProviderConfig.icon}</div>
          <h3>Connect {currentProviderConfig.name}</h3>
          {activeProvider === 'proton' ? (
            <>
              <p>Connect via <a href="https://proton.me/mail/bridge" target="_blank" rel="noopener noreferrer">Proton Bridge</a> (runs on your machine).</p>
              <div className="proton-form">
                <input type="text" placeholder="Proton email address" value={protonUser} onChange={e => setProtonUser(e.target.value)} className="config-input" />
                <input type="password" placeholder="Bridge password (from Proton Bridge app)" value={protonPass} onChange={e => setProtonPass(e.target.value)} className="config-input" />
                <p className="config-hint">Open Proton Bridge → click your account → copy the password shown there. Default ports: IMAP 1143, SMTP 1025.</p>
                <button className="connect-btn" onClick={handleConnectProton} disabled={!protonUser || !protonPass}>Connect Proton Bridge</button>
              </div>
            </>
          ) : (
            <>
              <p>Connect your {currentProviderConfig.name} account to see your inbox, manage drafts, and send emails.</p>
              <button className="connect-btn" onClick={() => handleConnect(activeProvider)}>Connect with {currentProviderConfig.name}</button>
            </>
          )}
        </div>
      ) : (
        <>
          {/* View Mode Tabs */}
          <div className="viewer-tabs">
            <button className={`tab ${viewMode === 'inbox' ? 'active' : ''}`} onClick={() => setViewMode('inbox')}>
              📥 Inbox
            </button>
            <button className={`tab ${viewMode === 'triage' ? 'active' : ''}`} onClick={handleTriage} disabled={aiLoading}>
              {aiLoading && viewMode === 'triage' ? '⏳' : '🎯'} Triage
            </button>
            <button className={`tab ${viewMode === 'digest' ? 'active' : ''}`} onClick={handleDigest} disabled={aiLoading}>
              {aiLoading && viewMode === 'digest' ? '⏳' : '📋'} Digest
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
              <div className="email-inbox-layout">
                <div className="email-list">
                  {emails.length === 0 ? (
                    <div className="empty-state">No emails yet.</div>
                  ) : (
                    emails.map((email) => (
                      <div
                        key={email.id}
                        className={`email-item ${email.unread ? 'unread' : ''} ${selectedEmail?.id === email.id ? 'selected' : ''}`}
                        onClick={() => { setSelectedEmail(email); setThreadSummary(null); setSmartReplies([]); setActionItems([]); }}
                      >
                        <div className="email-from">{email.from}</div>
                        <div className="email-subject">{email.subject}</div>
                        <div className="email-snippet">{email.snippet}</div>
                        <div className="email-date">{formatDate(email.date)}</div>
                      </div>
                    ))
                  )}
                </div>

                {/* AI Panel — shown when an email is selected */}
                {selectedEmail && (
                  <div className="email-ai-panel">
                    <div className="ai-panel-header">
                      <strong>{selectedEmail.subject}</strong>
                      <button className="btn-ai" onClick={() => handleSummarize(selectedEmail)} disabled={aiLoading}>
                        {aiLoading ? '⏳ Analyzing…' : '✨ Analyze'}
                      </button>
                    </div>

                    <div className="ai-panel-snippet">{selectedEmail.snippet}</div>

                    {threadSummary && (
                      <div className="ai-section">
                        <div className="ai-section-label">Summary</div>
                        <div className="ai-section-body">{threadSummary}</div>
                      </div>
                    )}

                    {actionItems.length > 0 && (
                      <div className="ai-section">
                        <div className="ai-section-label">Action Items</div>
                        <ul className="ai-action-items">
                          {actionItems.map((item, i) => (
                            <li key={i}>
                              <span className="action-task">{item.task}</span>
                              {item.assignee && <span className="action-assignee"> — {item.assignee}</span>}
                              {item.deadline && <span className="action-deadline"> (by {item.deadline})</span>}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {smartReplies.length > 0 && (
                      <div className="ai-section">
                        <div className="ai-section-label">Quick Replies</div>
                        <div className="ai-replies">
                          {smartReplies.map((reply, i) => (
                            <button key={i} className="btn-reply" onClick={() => handleUseReply(reply)}>
                              {reply}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : viewMode === 'triage' ? (
              <div className="triage-view">
                {triageResults.length === 0 ? (
                  <div className="empty-state">{aiLoading ? 'Analyzing inbox…' : 'Click Triage to classify your unread emails.'}</div>
                ) : (
                  <div className="triage-list">
                    {triageResults.map((item) => (
                      <div key={item.id} className={`triage-item priority-${item.priority}`}>
                        <span className={`priority-badge ${item.priority}`}>{item.priority}</span>
                        <span className="triage-category">{item.category}</span>
                        <div className="triage-from">{item.from}</div>
                        <div className="triage-subject">{item.subject}</div>
                        <div className="triage-reason">{item.reason}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : viewMode === 'digest' ? (
              <div className="digest-view">
                {digestText ? (
                  <div className="digest-content">
                    <h3>📋 Daily Digest</h3>
                    <div className="digest-body">{digestText}</div>
                  </div>
                ) : (
                  <div className="empty-state">{aiLoading ? 'Generating digest…' : 'Click Digest to generate a briefing of your inbox.'}</div>
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
                  <button className="btn-primary" onClick={handleComposeSend} disabled={sending || !composeTo}>
                    {sending ? '📤 Sending…' : '📤 Send'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
