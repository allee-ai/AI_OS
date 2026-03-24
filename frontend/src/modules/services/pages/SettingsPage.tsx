import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { BASE_URL } from '../../../config/api';
import { 
  MemoryDashboard, 
  ConsolidationDashboard, 
  FactExtractorDashboard,
  IntegrationsDashboard,
  KernelDashboard,
  AgentDashboard 
} from '../components';
import './SettingsPage.css';

/* ───────────────────────── Types ───────────────────────── */

interface ServiceInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: string;
  message?: string;
  config?: { enabled: boolean; settings: Record<string, unknown> };
}

interface SettingItem {
  key: string;
  default: string;
  group: string;
  label: string;
  type: string;
  hint?: string;
  options?: string[];
  value: string;
  display: string;
}

interface MCPServer {
  name: string;
  command: string;
  args: string[];
  env: Record<string, string>;
  enabled: boolean;
}

interface MCPCatalogItem {
  name: string;
  description: string;
  command: string;
  args: string[];
  env_required?: string[];
  category: string;
  installed: boolean;
}

/* ───────────────────── Unsaved Dialog ──────────────────── */

const UnsavedChangesDialog = ({ isOpen, onConfirm, onCancel }: { isOpen: boolean; onConfirm: () => void; onCancel: () => void }) => {
  if (!isOpen) return null;
  return (
    <div className="dialog-overlay">
      <div className="dialog">
        <h3>Unsaved Changes</h3>
        <p>You have unsaved changes. Are you sure you want to leave?</p>
        <div className="dialog-actions">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn-primary" onClick={onConfirm}>Leave Anyway</button>
        </div>
      </div>
    </div>
  );
};

/* ───────────────────── Main Page ──────────────────────── */

export const SettingsPage = () => {
  const { section } = useParams<{ section?: string }>();
  const navigate = useNavigate();

  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);

  const activeSection = section || 'server';

  useEffect(() => {
    fetch(`${BASE_URL}/api/services/`)
      .then(r => r.ok ? r.json() : [])
      .then(setServices)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleNavigation = useCallback((path: string) => {
    if (hasUnsavedChanges) {
      setPendingNavigation(path);
      setShowDialog(true);
    } else {
      navigate(path);
    }
  }, [hasUnsavedChanges, navigate]);

  const handleDialogConfirm = () => {
    setShowDialog(false);
    setHasUnsavedChanges(false);
    if (pendingNavigation) { navigate(pendingNavigation); setPendingNavigation(null); }
  };

  const handleRestart = async () => {
    setRestarting(true);
    setRestartMessage(null);
    try {
      const res = await fetch(`${BASE_URL}/api/services/restart`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setRestartMessage(data.message);
        setHasUnsavedChanges(false);
        const sRes = await fetch(`${BASE_URL}/api/services/`);
        if (sRes.ok) setServices(await sRes.json());
      } else {
        setRestartMessage(`Error: ${(await res.json()).detail}`);
      }
    } catch { setRestartMessage('Failed to restart services'); }
    finally { setRestarting(false); }
  };

  const handleSaveServiceConfig = async (serviceId: string, config: { enabled: boolean; settings: Record<string, unknown> }) => {
    try {
      const res = await fetch(`${BASE_URL}/api/services/${serviceId}/config`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      if (res.ok) {
        setHasUnsavedChanges(false);
        const sRes = await fetch(`${BASE_URL}/api/services/`);
        if (sRes.ok) setServices(await sRes.json());
      }
    } catch (err) { console.error('Failed to save config:', err); }
  };

  const renderContent = () => {
    // Config-driven sections
    if (['server', 'provider', 'kernel', 'chat', 'workspace'].includes(activeSection)) {
      return <ConfigSection group={activeSection} onDirty={() => setHasUnsavedChanges(true)} onClean={() => setHasUnsavedChanges(false)} />;
    }
    if (activeSection === 'mcp') {
      return <MCPSection />;
    }
    if (activeSection === 'integrations') {
      return <IntegrationsDashboard />;
    }

    // Dynamic service dashboards
    const service = services.find(s => s.id === activeSection);
    if (!service) return <div className="settings-empty">Select a section from the sidebar</div>;

    const dashboardProps = {
      config: service.config || null,
      status: service.status,
      message: service.message,
      onChangesMade: () => setHasUnsavedChanges(true),
      onSave: (config: { enabled: boolean; settings: Record<string, unknown> }) =>
        handleSaveServiceConfig(service.id, config),
    };

    switch (service.id) {
      case 'memory': return <MemoryDashboard {...dashboardProps} />;
      case 'consolidation': return <ConsolidationDashboard {...dashboardProps} />;
      case 'fact-extractor': return <FactExtractorDashboard {...dashboardProps} />;
      case 'kernel': return <KernelDashboard {...dashboardProps} />;
      case 'agent': return <AgentDashboard {...dashboardProps} />;
      default: return <GenericServiceDashboard service={service} onChangesMade={() => setHasUnsavedChanges(true)} />;
    }
  };

  return (
    <div className="settings-page">
      <UnsavedChangesDialog isOpen={showDialog} onConfirm={handleDialogConfirm} onCancel={() => { setShowDialog(false); setPendingNavigation(null); }} />

      <aside className="settings-sidebar">
        <div className="sidebar-header">
          <Link to="/" className="back-link">← Dashboard</Link>
          <h2>Settings</h2>
        </div>

        <nav className="sidebar-nav">
          {/* ── Configuration ── */}
          <div className="sidebar-section-header">Configuration</div>

          <button className={`sidebar-item ${activeSection === 'server' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/server')}>
            <span className="sidebar-icon">🖥️</span><span>Server</span>
          </button>

          <button className={`sidebar-item ${activeSection === 'provider' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/provider')}>
            <span className="sidebar-icon">🤖</span><span>Provider & Models</span>
          </button>

          <button className={`sidebar-item ${activeSection === 'chat' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/chat')}>
            <span className="sidebar-icon">💬</span><span>Chat & Context</span>
          </button>

          <button className={`sidebar-item ${activeSection === 'kernel' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/kernel')}>
            <span className="sidebar-icon">🌐</span><span>Kernel</span>
          </button>

          <button className={`sidebar-item ${activeSection === 'mcp' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/mcp')}>
            <span className="sidebar-icon">🔌</span><span>MCP Servers</span>
          </button>

          <button className={`sidebar-item ${activeSection === 'workspace' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/workspace')}>
            <span className="sidebar-icon">📂</span><span>Workspace</span>
          </button>

          {/* ── Tools ── */}
          <div className="sidebar-section-header">Tools</div>

          <Link to="/subconscious" className="sidebar-item"><span className="sidebar-icon">🧠</span><span>Subconscious</span></Link>
          <Link to="/training" className="sidebar-item"><span className="sidebar-icon">🔥</span><span>Fine-tune</span></Link>
          <Link to="/eval" className="sidebar-item"><span className="sidebar-icon">🎯</span><span>Eval</span></Link>

          {/* ── Services ── */}
          <div className="sidebar-section-header">Services</div>

          <button className={`sidebar-item ${activeSection === 'integrations' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/integrations')}>
            <span className="sidebar-icon">🔗</span><span>Integrations</span>
          </button>

          {loading ? <div className="sidebar-loading">Loading...</div> : services.map(svc => (
            <button key={svc.id}
              className={`sidebar-item ${activeSection === svc.id ? 'active' : ''}`}
              onClick={() => handleNavigation(`/settings/${svc.id}`)}>
              <span className="sidebar-icon">{svc.icon}</span>
              <span>{svc.name}</span>
              <span className={`status-dot ${svc.status}`} />
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          {hasUnsavedChanges && <p className="unsaved-warning">⚠️ Unsaved changes</p>}
          <button className="restart-btn" onClick={handleRestart} disabled={restarting}>
            {restarting ? 'Restarting...' : '🔄 Restart Services'}
          </button>
          {restartMessage && (
            <p className={`restart-message ${restartMessage.includes('Error') ? 'error' : 'success'}`}>{restartMessage}</p>
          )}
        </div>
      </aside>

      <main className="settings-content">{renderContent()}</main>
    </div>
  );
};

/* ───────── Chat Context Info Banner ───────── */

const ChatContextInfo = () => {
  const [info, setInfo] = useState<{ model: string; context_length: number | null } | null>(null);
  const [chatReserve, setChatReserve] = useState(0.6);

  useEffect(() => {
    // Fetch current model info
    fetch(`${BASE_URL}/api/models/current`)
      .then(r => r.json())
      .then(data => {
        const model = data.model;
        // Find context_length from models list
        fetch(`${BASE_URL}/api/models`)
          .then(r2 => r2.json())
          .then(mData => {
            const match = mData.models?.find((m: any) => m.id === model?.id || m.id === model?.name);
            setInfo({ model: model?.id || model?.name || 'unknown', context_length: match?.context_length || null });
          })
          .catch(() => setInfo({ model: model?.id || 'unknown', context_length: null }));
      })
      .catch(() => {});
    // Fetch chat reserve setting
    fetch(`${BASE_URL}/api/settings`)
      .then(r => r.json())
      .then(data => {
        const chatItems = data.groups?.chat || [];
        const reserve = chatItems.find((i: any) => i.key === 'AIOS_CHAT_CONTEXT_RESERVE');
        if (reserve) setChatReserve(parseFloat(reserve.value || reserve.default || '0.6'));
      })
      .catch(() => {});
  }, []);

  if (!info) return null;

  const ctxLen = info.context_length;
  const chatBudget = ctxLen ? Math.round(ctxLen * chatReserve) : null;

  return (
    <div style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 16px', marginBottom: 16, fontSize: 13 }}>
      <div style={{ fontWeight: 600, marginBottom: 6 }}>Current Model Context</div>
      <div style={{ display: 'flex', gap: 24, color: 'var(--text-secondary)' }}>
        <span>Model: <strong style={{ color: 'var(--text-primary)' }}>{info.model}</strong></span>
        <span>Context Window: <strong style={{ color: 'var(--text-primary)' }}>{ctxLen ? ctxLen.toLocaleString() + ' tokens' : 'unknown'}</strong></span>
        {chatBudget && <span>Chat Budget: <strong style={{ color: 'var(--accent)' }}>{chatBudget.toLocaleString()} tokens</strong></span>}
      </div>
    </div>
  );
};

/* ───────── Config Section (server / provider / kernel / chat) ───────── */

const GROUP_META: Record<string, { icon: string; title: string; desc: string }> = {
  server: { icon: '🖥️', title: 'Server Configuration', desc: 'Host, port, CORS, and public URL settings.' },
  provider: { icon: '🤖', title: 'Provider & Models', desc: 'LLM provider, model, API keys, and extraction overrides.' },
  chat: { icon: '💬', title: 'Chat & Summarization', desc: 'Context window budgets, auto-summarization thresholds, and conversation limits.' },
  kernel: { icon: '🌐', title: 'Kernel Browser Automation', desc: 'API key, browser profile, stealth & headless settings.' },
  workspace: { icon: '📂', title: 'Workspace', desc: 'Control which workspace operations the LLM/agent can perform and file size limits.' },
};

const ConfigSection = ({ group, onDirty, onClean }: { group: string; onDirty: () => void; onClean: () => void }) => {
  const [items, setItems] = useState<SettingItem[]>([]);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BASE_URL}/api/settings`)
      .then(r => r.json())
      .then(data => setItems(data.groups?.[group] || []))
      .catch(() => {});
  }, [group]);

  const handleChange = (key: string, val: string) => {
    setEdits(prev => ({ ...prev, [key]: val }));
    onDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      const res = await fetch(`${BASE_URL}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: edits }),
      });
      if (res.ok) {
        setMessage('Saved! Restart services for changes to take effect.');
        setEdits({});
        onClean();
        // Re-fetch to sync display values
        const r2 = await fetch(`${BASE_URL}/api/settings`);
        if (r2.ok) { const d = await r2.json(); setItems(d.groups?.[group] || []); }
      } else {
        const err = await res.json();
        setMessage(`Error: ${err.detail}`);
      }
    } catch { setMessage('Save failed'); }
    finally { setSaving(false); }
  };

  const meta = GROUP_META[group] || { icon: '⚙️', title: group, desc: '' };
  const dirty = Object.keys(edits).length > 0;

  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">{meta.icon}</span>
        <div><h1>{meta.title}</h1><p className="settings-description">{meta.desc}</p></div>
      </div>

      {group === 'chat' && <ChatContextInfo />}

      <section className="settings-section">
        {items.map(item => {
          const val = edits[item.key] ?? item.value;
          return (
            <div key={item.key} className="setting-row-full">
              <div className="setting-label-row">
                <label>{item.label}</label>
                <code className="setting-env-key">{item.key}</code>
              </div>
              {item.type === 'select' && item.options ? (
                <select value={val} onChange={e => handleChange(item.key, e.target.value)} className="config-select">
                  {item.options.map(o => <option key={o} value={o}>{o}</option>)}
                </select>
              ) : item.type === 'bool' ? (
                <select value={val} onChange={e => handleChange(item.key, e.target.value)} className="config-select">
                  <option value="true">Enabled</option>
                  <option value="false">Disabled</option>
                </select>
              ) : item.type === 'password' ? (
                <input type="password" value={val} onChange={e => handleChange(item.key, e.target.value)}
                  placeholder={item.display !== val ? item.display : item.default || '(not set)'}
                  className="config-input" />
              ) : (
                <input type={item.type === 'number' ? 'number' : 'text'}
                  value={val} onChange={e => handleChange(item.key, e.target.value)}
                  placeholder={item.default || ''} className="config-input" />
              )}
              {item.hint && <p className="setting-hint">{item.hint}</p>}
            </div>
          );
        })}
      </section>

      {message && <div className={`config-result ${message.startsWith('Error') ? 'error' : 'success'}`}>{message}</div>}

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving || !dirty}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};

/* ──────────────────── MCP Section ─────────────────────── */

interface MCPConnectionInfo {
  name: string;
  connected: boolean;
  tools: { name: string; description: string }[];
}

const MCPSection = () => {
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [catalog, setCatalog] = useState<MCPCatalogItem[]>([]);
  const [connections, setConnections] = useState<Record<string, MCPConnectionInfo>>({});
  const [connecting, setConnecting] = useState<string | null>(null);
  const [showCatalog, setShowCatalog] = useState(false);
  const [expandedServer, setExpandedServer] = useState<string | null>(null);
  const [addingName, setAddingName] = useState('');
  const [addingCmd, setAddingCmd] = useState('');
  const [addingArgs, setAddingArgs] = useState('');
  const [message, setMessage] = useState<string | null>(null);

  const refresh = () => {
    fetch(`${BASE_URL}/api/mcp/servers`).then(r => r.json()).then(d => setServers(d.servers || [])).catch(() => {});
    fetch(`${BASE_URL}/api/mcp/catalog`).then(r => r.json()).then(d => setCatalog(d.servers || [])).catch(() => {});
    fetch(`${BASE_URL}/api/mcp/connections`).then(r => r.json()).then(d => {
      const map: Record<string, MCPConnectionInfo> = {};
      for (const c of d.connections || []) {
        map[c.name] = { name: c.name, connected: c.alive, tools: c.tools || [] };
      }
      setConnections(map);
    }).catch(() => {});
  };

  useEffect(refresh, []);

  const connectServer = async (name: string) => {
    setConnecting(name);
    setMessage(null);
    try {
      const res = await fetch(`${BASE_URL}/api/mcp/servers/${encodeURIComponent(name)}/connect`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setMessage(`Connected ${name} — ${data.tools_discovered} tools discovered`);
        refresh();
      } else {
        setMessage(`Error: ${data.detail}`);
      }
    } catch { setMessage(`Failed to connect ${name}`); }
    setConnecting(null);
  };

  const disconnectServer = async (name: string) => {
    setConnecting(name);
    try {
      const res = await fetch(`${BASE_URL}/api/mcp/servers/${encodeURIComponent(name)}/disconnect`, { method: 'POST' });
      const data = await res.json();
      if (res.ok) {
        setMessage(`Disconnected ${name} — ${data.tools_removed} tools removed`);
        refresh();
      }
    } catch { setMessage(`Failed to disconnect ${name}`); }
    setConnecting(null);
  };

  const addServer = async () => {
    if (!addingName || !addingCmd) return;
    try {
      const res = await fetch(`${BASE_URL}/api/mcp/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: addingName, command: addingCmd, args: addingArgs.split(' ').filter(Boolean) }),
      });
      if (res.ok) {
        setAddingName(''); setAddingCmd(''); setAddingArgs('');
        setMessage(`Added ${addingName}`);
        refresh();
      } else {
        const err = await res.json();
        setMessage(`Error: ${err.detail}`);
      }
    } catch { setMessage('Failed to add server'); }
  };

  const quickAdd = async (item: MCPCatalogItem) => {
    try {
      const res = await fetch(`${BASE_URL}/api/mcp/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: item.name, command: item.command, args: item.args }),
      });
      if (res.ok) { setMessage(`Added ${item.name}`); refresh(); }
    } catch { setMessage('Failed to add server'); }
  };

  const removeServer = async (name: string) => {
    try {
      // Disconnect first if connected
      if (connections[name]?.connected) await disconnectServer(name);
      await fetch(`${BASE_URL}/api/mcp/servers/${encodeURIComponent(name)}`, { method: 'DELETE' });
      refresh();
    } catch { setMessage(`Failed to remove ${name}`); }
  };

  const toggleServer = async (name: string) => {
    try {
      await fetch(`${BASE_URL}/api/mcp/servers/${encodeURIComponent(name)}/toggle`, { method: 'POST' });
      refresh();
    } catch { setMessage(`Failed to toggle ${name}`); }
  };

  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">🔌</span>
        <div><h1>MCP Servers</h1><p className="settings-description">Model Context Protocol servers give your agent access to external tools and data sources. Connect a server to discover its tools — they appear in Form thread automatically.</p></div>
      </div>

      {/* Installed servers */}
      <section className="settings-section">
        <h3>Configured Servers</h3>
        {servers.length === 0 ? (
          <p className="setting-hint">No MCP servers configured yet. Add one below or install from the catalog.</p>
        ) : (
          <div className="mcp-server-list">
            {servers.map(s => {
              const conn = connections[s.name];
              const isConnected = conn?.connected ?? false;
              const toolCount = conn?.tools?.length ?? 0;
              const isLoading = connecting === s.name;
              return (
                <div key={s.name} className={`mcp-server-card ${s.enabled ? '' : 'disabled'} ${isConnected ? 'connected' : ''}`}>
                  <div className="mcp-server-info">
                    <div className="mcp-server-header">
                      <span className={`mcp-status-dot ${isConnected ? 'active' : ''}`} />
                      <span className="mcp-server-name">{s.name}</span>
                      {isConnected && <span className="mcp-tool-count">{toolCount} tools</span>}
                    </div>
                    <code className="mcp-server-cmd">{s.command} {s.args.join(' ')}</code>
                  </div>
                  <div className="mcp-server-actions">
                    {s.enabled && (
                      isConnected ? (
                        <button className="btn-sm btn-disconnect" onClick={() => disconnectServer(s.name)} disabled={isLoading}>
                          {isLoading ? '...' : 'Disconnect'}
                        </button>
                      ) : (
                        <button className="btn-sm btn-connect" onClick={() => connectServer(s.name)} disabled={isLoading}>
                          {isLoading ? 'Connecting...' : 'Connect'}
                        </button>
                      )
                    )}
                    <button className="btn-sm" onClick={() => toggleServer(s.name)}>{s.enabled ? 'Disable' : 'Enable'}</button>
                    <button className="btn-sm btn-danger" onClick={() => removeServer(s.name)}>Remove</button>
                    {isConnected && toolCount > 0 && (
                      <button className="btn-sm" onClick={() => setExpandedServer(expandedServer === s.name ? null : s.name)}>
                        {expandedServer === s.name ? '▾ Hide tools' : '▸ Tools'}
                      </button>
                    )}
                  </div>
                  {expandedServer === s.name && conn?.tools && (
                    <div className="mcp-tools-list">
                      {conn.tools.map(t => (
                        <div key={t.name} className="mcp-tool-item">
                          <span className="mcp-tool-name">{t.name}</span>
                          <span className="mcp-tool-desc">{t.description}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </section>

      {/* Manual add */}
      <section className="settings-section">
        <h3>Add Server</h3>
        <div className="mcp-add-form">
          <input type="text" placeholder="Name (e.g. filesystem)" value={addingName} onChange={e => setAddingName(e.target.value)} className="config-input" />
          <input type="text" placeholder="Command (e.g. npx)" value={addingCmd} onChange={e => setAddingCmd(e.target.value)} className="config-input" />
          <input type="text" placeholder="Args (space-separated)" value={addingArgs} onChange={e => setAddingArgs(e.target.value)} className="config-input" />
          <button className="btn-primary" onClick={addServer} disabled={!addingName || !addingCmd}>Add</button>
        </div>
      </section>

      {/* Catalog */}
      <section className="settings-section">
        <button className="library-toggle" onClick={() => setShowCatalog(!showCatalog)}>
          {showCatalog ? '▾ Hide catalog' : '▸ Browse MCP catalog'}
        </button>
        {showCatalog && (
          <div className="mcp-catalog">
            {catalog.map(item => (
              <div key={item.name} className={`library-item ${item.installed ? 'installed' : ''}`}>
                <div className="library-item-info">
                  <span className="library-item-name">{item.name}</span>
                  <span className="library-item-meta">{item.category}{item.env_required ? ` · Requires: ${item.env_required.join(', ')}` : ''}</span>
                  <span className="library-item-desc">{item.description}</span>
                </div>
                <div className="library-item-action">
                  {item.installed ? (
                    <span className="library-badge-installed">Added</span>
                  ) : (
                    <button className="btn-pull" onClick={() => quickAdd(item)}>Add</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {message && <div className="config-result success">{message}</div>}
    </div>
  );
};

/* ───────── Generic Service Dashboard (fallback) ─────── */

const GenericServiceDashboard = ({ service, onChangesMade }: { service: ServiceInfo; onChangesMade: () => void }) => (
  <div className="settings-panel">
    <div className="service-header">
      <span className="service-icon">{service.icon}</span>
      <div><h1>{service.name}</h1><p className="settings-description">{service.description}</p></div>
    </div>
    <section className="settings-section">
      <h3>Status</h3>
      <div className="status-card">
        <div className={`status-indicator-large ${service.status}`}>
          <span className="status-dot-large" /><span className="status-text">{service.status}</span>
        </div>
        {service.message && <p className="status-message">{service.message}</p>}
      </div>
    </section>
    <section className="settings-section">
      <h3>Configuration</h3>
      <div className="setting-row">
        <label>Enabled</label>
        <input type="checkbox" checked={service.config?.enabled ?? true} onChange={onChangesMade} />
      </div>
    </section>
  </div>
);
