import { useState, useEffect, useRef } from 'react';
import './FeedViewer.css';

interface Notification {
  id: string;
  repo: string;
  type: string;
  title: string;
  url: string;
  unread: boolean;
  updated_at: string;
}

interface Issue {
  number: number;
  title: string;
  state: string;
  author: string;
  labels: string[];
  url: string;
  created_at: string;
}

interface PR {
  number: number;
  title: string;
  state: string;
  author: string;
  base: string;
  head: string;
  url: string;
  created_at: string;
}

interface DeviceFlowState {
  userCode: string;
  verificationUri: string;
  deviceCode: string;
  expiresAt: number;
  interval: number;
}

type ViewMode = 'notifications' | 'issues' | 'prs';

const API_BASE = 'http://localhost:8000';

export default function GithubViewer() {
  const [viewMode, setViewMode] = useState<ViewMode>('notifications');
  const [connected, setConnected] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [prs, setPRs] = useState<PR[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Device flow state
  const [deviceFlow, setDeviceFlow] = useState<DeviceFlowState | null>(null);
  const [deviceFlowStatus, setDeviceFlowStatus] = useState<string>('');
  const pollInterval = useRef<number | null>(null);

  useEffect(() => {
    checkConnection();
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, []);

  useEffect(() => {
    if (connected) {
      if (viewMode === 'notifications') fetchNotifications();
      else if (viewMode === 'issues') fetchIssues();
      else if (viewMode === 'prs') fetchPRs();
    }
  }, [connected, viewMode]);

  const checkConnection = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/github/status`);
      if (res.ok) {
        const data = await res.json();
        setConnected(data.connected);
        setUsername(data.username);
      }
    } catch (err) {
      console.error('Failed to check GitHub status:', err);
    } finally {
      setLoading(false);
    }
  };

  const startDeviceFlow = async () => {
    try {
      setDeviceFlowStatus('Starting...');
      const res = await fetch(`${API_BASE}/api/feeds/github/device/start`, { method: 'POST' });
      
      if (!res.ok) {
        const error = await res.json();
        setDeviceFlowStatus(`Error: ${error.detail}`);
        return;
      }
      
      const data = await res.json();
      setDeviceFlow({
        userCode: data.user_code,
        verificationUri: data.verification_uri,
        deviceCode: data.device_code,
        expiresAt: Date.now() + (data.expires_in * 1000),
        interval: data.interval * 1000,
      });
      setDeviceFlowStatus('Enter the code at GitHub');
      
      // Start polling
      pollInterval.current = window.setInterval(() => pollForToken(data.device_code), data.interval * 1000);
    } catch (err) {
      setDeviceFlowStatus(`Failed to start: ${err}`);
    }
  };

  const pollForToken = async (deviceCode: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/github/device/poll?device_code=${deviceCode}`, { 
        method: 'POST' 
      });
      const data = await res.json();
      
      if (data.status === 'success') {
        // Connected!
        if (pollInterval.current) clearInterval(pollInterval.current);
        setDeviceFlow(null);
        setDeviceFlowStatus('');
        setConnected(true);
        checkConnection(); // Refresh to get username
      } else if (data.status === 'pending') {
        setDeviceFlowStatus('Waiting for authorization...');
      } else if (data.status === 'slow_down') {
        // Slow down polling
        if (pollInterval.current) {
          clearInterval(pollInterval.current);
          pollInterval.current = window.setInterval(() => pollForToken(deviceCode), data.interval * 1000);
        }
      } else if (res.status >= 400) {
        // Error
        if (pollInterval.current) clearInterval(pollInterval.current);
        setDeviceFlow(null);
        setDeviceFlowStatus(data.detail || 'Authorization failed');
      }
    } catch (err) {
      console.error('Poll error:', err);
    }
  };

  const cancelDeviceFlow = () => {
    if (pollInterval.current) clearInterval(pollInterval.current);
    setDeviceFlow(null);
    setDeviceFlowStatus('');
  };

  const handleConnect = () => {
    startDeviceFlow();
  };

  const fetchNotifications = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/github/notifications`);
      if (res.ok) {
        const data = await res.json();
        setNotifications(data);
      }
    } catch (err) {
      console.error('Failed to fetch notifications:', err);
      // Demo data
      setNotifications([
        {
          id: '1',
          repo: 'owner/repo',
          type: 'PullRequest',
          title: 'Review requested: feat: Add new feature',
          url: 'https://github.com/owner/repo/pull/123',
          unread: true,
          updated_at: '2026-02-01T10:30:00Z',
        },
        {
          id: '2',
          repo: 'owner/repo',
          type: 'Issue',
          title: 'Bug: App crashes on startup',
          url: 'https://github.com/owner/repo/issues/456',
          unread: false,
          updated_at: '2026-02-01T09:15:00Z',
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const fetchIssues = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/github/issues`);
      if (res.ok) {
        const data = await res.json();
        setIssues(data);
      }
    } catch (err) {
      console.error('Failed to fetch issues:', err);
      setIssues([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchPRs = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/github/pulls`);
      if (res.ok) {
        const data = await res.json();
        setPRs(data);
      }
    } catch (err) {
      console.error('Failed to fetch PRs:', err);
      setPRs([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'PullRequest': return '🔀';
      case 'Issue': return '🐛';
      case 'Release': return '🚀';
      case 'Discussion': return '💬';
      default: return '📌';
    }
  };

  if (loading && !connected && !deviceFlow) {
    return (
      <div className="feed-viewer github-viewer">
        <div className="viewer-loading">Checking connection...</div>
      </div>
    );
  }

  // Device Flow UI - show code to enter
  if (deviceFlow) {
    return (
      <div className="feed-viewer github-viewer">
        <div className="connect-prompt device-flow">
          <div className="connect-icon">🐙</div>
          <h3>Enter this code at GitHub</h3>
          
          <div className="device-code-display">
            <code className="user-code">{deviceFlow.userCode}</code>
          </div>
          
          <p className="device-flow-instructions">
            1. Click the button below to open GitHub<br/>
            2. Enter the code above<br/>
            3. Click "Authorize"
          </p>
          
          <a 
            href={deviceFlow.verificationUri} 
            target="_blank" 
            rel="noopener noreferrer"
            className="connect-btn github-btn"
          >
            <span className="btn-icon">🔗</span>
            Open GitHub
          </a>
          
          <p className="device-flow-status">{deviceFlowStatus}</p>
          
          <button className="cancel-btn" onClick={cancelDeviceFlow}>
            Cancel
          </button>
        </div>
      </div>
    );
  }

  if (!connected) {
    return (
      <div className="feed-viewer github-viewer">
        <div className="connect-prompt">
          <div className="connect-icon">🐙</div>
          <h3>Connect GitHub</h3>
          <p>Connect your GitHub account to see notifications, issues, and pull requests.</p>
          {deviceFlowStatus && <p className="error-message">{deviceFlowStatus}</p>}
          <button className="connect-btn github-btn" onClick={handleConnect}>
            <span className="btn-icon">🐙</span>
            Login with GitHub
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="feed-viewer github-viewer">
      {/* User badge */}
      {username && (
        <div className="github-user-badge">
          <span className="user-icon">👤</span>
          <span className="username">@{username}</span>
          <span className="connected-status">Connected</span>
        </div>
      )}

      {/* View Mode Tabs */}
      <div className="viewer-tabs">
        <button className={`tab ${viewMode === 'notifications' ? 'active' : ''}`} onClick={() => setViewMode('notifications')}>
          🔔 Notifications
        </button>
        <button className={`tab ${viewMode === 'issues' ? 'active' : ''}`} onClick={() => setViewMode('issues')}>
          🐛 Issues
        </button>
        <button className={`tab ${viewMode === 'prs' ? 'active' : ''}`} onClick={() => setViewMode('prs')}>
          🔀 Pull Requests
        </button>
      </div>

      <div className="viewer-content">
        {loading ? (
          <div className="viewer-loading">Loading...</div>
        ) : viewMode === 'notifications' ? (
          <div className="notification-list">
            {notifications.length === 0 ? (
              <div className="empty-state">No notifications. You're all caught up! 🎉</div>
            ) : (
              notifications.map((notif) => (
                <a
                  key={notif.id}
                  href={notif.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={`notification-item ${notif.unread ? 'unread' : ''}`}
                >
                  <span className="notif-type-icon">{getTypeIcon(notif.type)}</span>
                  <div className="notif-content">
                    <div className="notif-repo">{notif.repo}</div>
                    <div className="notif-title">{notif.title}</div>
                  </div>
                  <div className="notif-meta">
                    <span className="notif-date">{formatDate(notif.updated_at)}</span>
                  </div>
                </a>
              ))
            )}
          </div>
        ) : viewMode === 'issues' ? (
          <div className="issue-list">
            {issues.length === 0 ? (
              <div className="empty-state">No open issues assigned to you.</div>
            ) : (
              issues.map((issue) => (
                <a
                  key={issue.number}
                  href={issue.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="issue-item"
                >
                  <span className="issue-number">#{issue.number}</span>
                  <div className="issue-content">
                    <div className="issue-title">{issue.title}</div>
                    <div className="issue-meta">
                      <span className={`issue-state ${issue.state}`}>{issue.state}</span>
                      {issue.labels.map((label) => (
                        <span key={label} className="issue-label">{label}</span>
                      ))}
                    </div>
                  </div>
                </a>
              ))
            )}
          </div>
        ) : (
          <div className="pr-list">
            {prs.length === 0 ? (
              <div className="empty-state">No open pull requests.</div>
            ) : (
              prs.map((pr) => (
                <a
                  key={pr.number}
                  href={pr.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="pr-item"
                >
                  <span className="pr-number">#{pr.number}</span>
                  <div className="pr-content">
                    <div className="pr-title">{pr.title}</div>
                    <div className="pr-meta">
                      <span className="pr-branch">{pr.head} → {pr.base}</span>
                      <span className="pr-author">by {pr.author}</span>
                    </div>
                  </div>
                </a>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
