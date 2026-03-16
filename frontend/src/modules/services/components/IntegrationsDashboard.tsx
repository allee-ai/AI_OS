/**
 * IntegrationsDashboard — Connect & configure external feeds
 *
 * Lives under Settings → Integrations.
 * Shows Email/GitHub/Discord as cards with connect/disconnect flows,
 * status indicators, and one-click reflex protocol install.
 */
import { useState, useEffect, useCallback } from 'react';
import { BASE_URL } from '../../../config/api';
import './IntegrationsDashboard.css';

const API = BASE_URL;

// ── Types ─────────────────────────────────────────────────
interface ConfigField {
  key: string;
  label: string;
  type: 'env' | 'secret';
  secret: boolean;
}

interface ProviderStatus {
  connected: boolean;
  label: string;
  auth_method: string;
}

interface Integration {
  id: string;
  name: string;
  icon: string;
  description: string;
  category: string;
  connected: boolean;
  username?: string;
  auth_method: string;
  config_fields: ConfigField[];
  suggested_protocols: string[];
  docs_url?: string;
  providers?: Record<string, ProviderStatus>;
}

interface PollingStatus {
  status: string;
  enabled_feeds: string[];
  name?: string;
  runs?: number;
  errors?: number;
}

interface DeviceFlowState {
  user_code: string;
  verification_uri: string;
  device_code: string;
  expires_in: number;
  interval: number;
}

// ── Component ─────────────────────────────────────────────
export const IntegrationsDashboard = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [polling, setPolling] = useState<PollingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [deviceFlow, setDeviceFlow] = useState<DeviceFlowState | null>(null);
  const [devicePolling, setDevicePolling] = useState(false);
  const [botToken, setBotToken] = useState('');
  const [actionMsg, setActionMsg] = useState<{ id: string; msg: string; ok: boolean } | null>(null);
  const [installedProtocols, setInstalledProtocols] = useState<Set<string>>(new Set());

  const fetchIntegrations = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/feeds/integrations`);
      if (!res.ok) throw new Error('Failed');
      const data = await res.json();
      setIntegrations(data.integrations || []);
      setPolling(data.polling || null);
    } catch (e) {
      console.error('Failed to fetch integrations:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchIntegrations(); }, [fetchIntegrations]);

  // ── Actions ───────────────────────────────────────────────

  const flash = (id: string, msg: string, ok: boolean) => {
    setActionMsg({ id, msg, ok });
    setTimeout(() => setActionMsg(null), 4000);
  };

  const connectEmail = async (provider: string) => {
    try {
      const res = await fetch(`${API}/api/feeds/integrations/email/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'provider', value: provider }),
      });
      const data = await res.json();
      if (data.auth_url) {
        window.open(data.auth_url, '_blank', 'width=600,height=700');
        flash('email', `Opened ${provider} login — complete it in the popup`, true);
      }
    } catch {
      flash('email', 'Failed to start OAuth flow', false);
    }
  };

  const connectGitHub = async () => {
    try {
      const res = await fetch(`${API}/api/feeds/integrations/github/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await res.json();
      if (data.user_code) {
        setDeviceFlow(data);
        window.open(data.verification_uri, '_blank');
        pollDeviceFlow(data.device_code, data.interval);
      }
    } catch {
      flash('github', 'Failed to start device flow', false);
    }
  };

  const pollDeviceFlow = async (deviceCode: string, interval: number) => {
    setDevicePolling(true);
    const poll = async () => {
      try {
        const res = await fetch(`${API}/api/feeds/github/device/poll?device_code=${deviceCode}`, {
          method: 'POST',
        });
        const data = await res.json();
        if (data.status === 'success') {
          setDeviceFlow(null);
          setDevicePolling(false);
          flash('github', 'GitHub connected!', true);
          fetchIntegrations();
          return;
        }
        if (data.status === 'pending' || data.status === 'slow_down') {
          setTimeout(poll, (data.interval || interval) * 1000);
          return;
        }
        // error
        setDeviceFlow(null);
        setDevicePolling(false);
        flash('github', data.detail || 'Device flow failed', false);
      } catch {
        setDeviceFlow(null);
        setDevicePolling(false);
      }
    };
    setTimeout(poll, interval * 1000);
  };

  const connectDiscord = async () => {
    if (!botToken.trim()) return;
    try {
      const res = await fetch(`${API}/api/feeds/integrations/discord/connect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key: 'bot_token', value: botToken.trim() }),
      });
      if (res.ok) {
        flash('discord', 'Discord bot connected!', true);
        setBotToken('');
        fetchIntegrations();
      } else {
        flash('discord', 'Failed to store token', false);
      }
    } catch {
      flash('discord', 'Connection error', false);
    }
  };

  const disconnect = async (feedName: string, provider?: string) => {
    try {
      const url = provider
        ? `${API}/api/feeds/integrations/${feedName}/disconnect?provider=${provider}`
        : `${API}/api/feeds/integrations/${feedName}/disconnect`;
      await fetch(url, { method: 'POST' });
      flash(feedName, 'Disconnected', true);
      fetchIntegrations();
    } catch {
      flash(feedName, 'Failed to disconnect', false);
    }
  };

  const toggleEnabled = async (feedName: string, enabled: boolean) => {
    try {
      await fetch(`${API}/api/feeds/integrations/${feedName}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled }),
      });
      fetchIntegrations();
    } catch (e) {
      console.error(e);
    }
  };

  const installProtocol = async (protocolName: string) => {
    try {
      const res = await fetch(`${API}/api/reflex/protocols/${protocolName}/install`, {
        method: 'POST',
      });
      if (res.ok) {
        setInstalledProtocols(prev => new Set(prev).add(protocolName));
        flash(protocolName, `Protocol "${protocolName}" installed`, true);
      }
    } catch {
      flash(protocolName, 'Failed to install protocol', false);
    }
  };

  // ── Render helpers ────────────────────────────────────────

  const renderEmailCard = (integ: Integration) => {
    const providers = integ.providers || {};
    return (
      <div className="integ-connect-section">
        <h4>Email Providers</h4>
        <div className="provider-grid">
          {Object.entries(providers).map(([key, prov]) => (
            <div key={key} className={`provider-card ${prov.connected ? 'connected' : ''}`}>
              <span className="provider-name">{prov.label}</span>
              {prov.connected ? (
                <div className="provider-actions">
                  <span className="connected-badge">● Connected</span>
                  <button className="btn-sm btn-danger" onClick={() => disconnect('email', key)}>
                    Disconnect
                  </button>
                </div>
              ) : (
                <button className="btn-sm btn-connect" onClick={() => connectEmail(key)}>
                  Connect
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderGitHubCard = (integ: Integration) => (
    <div className="integ-connect-section">
      {integ.connected ? (
        <div className="connected-status">
          <span className="connected-badge">● Connected</span>
          {integ.username && <span className="username">@{integ.username}</span>}
          <button className="btn-sm btn-danger" onClick={() => disconnect('github')}>
            Disconnect
          </button>
        </div>
      ) : deviceFlow ? (
        <div className="device-flow-box">
          <p>Enter this code at GitHub:</p>
          <div className="device-code">{deviceFlow.user_code}</div>
          <a href={deviceFlow.verification_uri} target="_blank" rel="noopener noreferrer">
            {deviceFlow.verification_uri}
          </a>
          {devicePolling && <p className="polling-msg">Waiting for authorization...</p>}
        </div>
      ) : (
        <button className="btn-connect" onClick={connectGitHub}>
          Connect with GitHub
        </button>
      )}
    </div>
  );

  const renderDiscordCard = (integ: Integration) => (
    <div className="integ-connect-section">
      {integ.connected ? (
        <div className="connected-status">
          <span className="connected-badge">● Connected</span>
          <button className="btn-sm btn-danger" onClick={() => disconnect('discord')}>
            Disconnect
          </button>
        </div>
      ) : (
        <div className="token-input-row">
          <input
            type="password"
            placeholder="Paste your bot token"
            value={botToken}
            onChange={e => setBotToken(e.target.value)}
            className="token-input"
          />
          <button className="btn-sm btn-connect" onClick={connectDiscord} disabled={!botToken.trim()}>
            Save Token
          </button>
        </div>
      )}
    </div>
  );

  const renderConnectSection = (integ: Integration) => {
    switch (integ.id) {
      case 'email': return renderEmailCard(integ);
      case 'github': return renderGitHubCard(integ);
      case 'discord': return renderDiscordCard(integ);
      default: return null;
    }
  };

  // ── Protocols ─────────────────────────────────────────────

  const PROTOCOL_INFO: Record<string, { label: string; desc: string }> = {
    email_triage: { label: 'Email Triage', desc: 'AI reads incoming emails and drafts replies' },
    morning_briefing: { label: 'Morning Briefing', desc: 'Daily summary of pending items at 8 AM' },
    github_review: { label: 'Code Review Alerts', desc: 'Notify when review is requested on a PR' },
    daily_digest: { label: 'Daily Digest', desc: 'End-of-day summary of all activity' },
  };

  // ── Main render ───────────────────────────────────────────

  if (loading) {
    return <div className="integ-loading">Loading integrations...</div>;
  }

  return (
    <div className="integrations-dashboard">
      <div className="integ-header">
        <h1>Integrations</h1>
        <p className="integ-subtitle">Connect external services to your AI agent</p>
      </div>

      {/* Polling status bar */}
      {polling && (
        <div className="polling-bar">
          <span className={`polling-dot ${polling.status === 'stopped' ? 'off' : 'on'}`} />
          <span>Feed polling: {polling.status}</span>
          {polling.enabled_feeds.length > 0 && (
            <span className="polling-feeds">
              Active: {polling.enabled_feeds.join(', ')}
            </span>
          )}
        </div>
      )}

      {/* Integration cards */}
      <div className="integ-cards">
        {integrations.map(integ => (
          <div
            key={integ.id}
            className={`integ-card ${integ.connected ? 'connected' : ''} ${expanded === integ.id ? 'expanded' : ''}`}
          >
            <div className="integ-card-header" onClick={() => setExpanded(expanded === integ.id ? null : integ.id)}>
              <div className="integ-card-left">
                <span className="integ-icon">{integ.icon}</span>
                <div>
                  <h3 className="integ-name">{integ.name}</h3>
                  <p className="integ-desc">{integ.description}</p>
                </div>
              </div>
              <div className="integ-card-right">
                <span className={`integ-status ${integ.connected ? 'on' : 'off'}`}>
                  {integ.connected ? '● Connected' : '○ Not connected'}
                </span>
                <span className="integ-chevron">{expanded === integ.id ? '▾' : '▸'}</span>
              </div>
            </div>

            {expanded === integ.id && (
              <div className="integ-card-body">
                {/* Flash message */}
                {actionMsg && actionMsg.id === integ.id && (
                  <div className={`integ-flash ${actionMsg.ok ? 'success' : 'error'}`}>
                    {actionMsg.msg}
                  </div>
                )}

                {/* Connect / Status */}
                {renderConnectSection(integ)}

                {/* Enable / Disable polling */}
                <div className="integ-toggle-row">
                  <label className="integ-toggle-label">Enable polling</label>
                  <button
                    className={`toggle-btn ${polling?.enabled_feeds.includes(integ.id) ? 'on' : 'off'}`}
                    onClick={() => toggleEnabled(integ.id, !polling?.enabled_feeds.includes(integ.id))}
                  >
                    {polling?.enabled_feeds.includes(integ.id) ? 'ON' : 'OFF'}
                  </button>
                </div>

                {/* Docs link */}
                {integ.docs_url && (
                  <a href={integ.docs_url} target="_blank" rel="noopener noreferrer" className="docs-link">
                    📖 Setup instructions
                  </a>
                )}

                {/* Suggested reflex protocols */}
                {integ.suggested_protocols.length > 0 && (
                  <div className="integ-protocols">
                    <h4>Suggested Automations</h4>
                    {integ.suggested_protocols.map(proto => {
                      const info = PROTOCOL_INFO[proto] || { label: proto, desc: '' };
                      const installed = installedProtocols.has(proto);
                      return (
                        <div key={proto} className="protocol-row">
                          <div>
                            <span className="protocol-name">{info.label}</span>
                            <span className="protocol-desc">{info.desc}</span>
                          </div>
                          <button
                            className={`btn-sm ${installed ? 'btn-installed' : 'btn-install'}`}
                            onClick={() => !installed && installProtocol(proto)}
                            disabled={installed}
                          >
                            {installed ? '✓ Installed' : 'Install'}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Flash for protocols */}
                {actionMsg && integ.suggested_protocols.includes(actionMsg.id) && (
                  <div className={`integ-flash ${actionMsg.ok ? 'success' : 'error'}`}>
                    {actionMsg.msg}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};
