import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './FeedsPage.css';
import { FEED_VIEWERS, DefaultViewer } from '../viewers';

interface FeedsSource {
  name: string;
  type: string;
  enabled: boolean;
  poll_interval: number;
  has_auth: boolean;
  description?: string;
}

interface SourceTemplate {
  name: string;
  description: string;
  icon?: string;
  exists?: boolean;
}

interface SourceConfig {
  name: string;
  type: string;
  enabled: boolean;
  poll_interval: number;
  description?: string;
  auth: Record<string, any>;
  pull: Record<string, any>;
  push: Record<string, any>;
}

interface EventTrigger {
  feed_name: string;
  event_type: string;
  description: string;
  payload_schema: Record<string, string>;
}

const API_BASE = 'http://localhost:8000';

const SOURCE_ICONS: Record<string, string> = {
  gmail: '📧',
  slack: '💬',
  sms: '📱',
  discord: '🎮',
  telegram: '✈️',
  webhook: '🔗',
  rest: '🌐',
  github: '🐙',
  linear: '📐',
  notion: '📓',
  twitter: '🐦',
  whatsapp: '💚',
  teams: '👥',
  intercom: '💬',
  zendesk: '🎫',
  jira: '📋',
  airtable: '📊',
  todoist: '🌀',
  gcal: '📅',
  shopify: '🛒',
  hubspot: '🧡',
};

export const FeedsPage = () => {
  const [sources, setSources] = useState<FeedsSource[]>([]);
  const [templates, setTemplates] = useState<SourceTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeSource, setActiveSource] = useState<string | null>(null);
  const [sourceConfig, setSourceConfig] = useState<SourceConfig | null>(null);
  const [configLoading, setConfigLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; message: string } | null>(null);
  
  // Edit mode state
  const [editingSection, setEditingSection] = useState<'settings' | 'auth' | 'pull' | 'push' | null>(null);
  const [editedConfig, setEditedConfig] = useState<SourceConfig | null>(null);
  const [saving, setSaving] = useState(false);

  // Form state for new source
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceType, setNewSourceType] = useState('rest');

  // Triggers state
  const [triggers, setTriggers] = useState<EventTrigger[]>([]);
  const [showTriggers, setShowTriggers] = useState(false);
  const [newSourceDesc, setNewSourceDesc] = useState('');

  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sources`);
      const data = await res.json();
      setSources(data);
    } catch (err) {
      console.error('Failed to fetch sources:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchTemplates = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/templates`);
      const data = await res.json();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    }
  }, []);

  const fetchTriggers = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/feeds/events/triggers`);
      const data = await res.json();
      setTriggers(data);
    } catch (err) {
      console.error('Failed to fetch triggers:', err);
    }
  }, []);

  const fetchSourceConfig = useCallback(async (name: string) => {
    setConfigLoading(true);
    setTestResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sources/${name}`);
      const data = await res.json();
      setSourceConfig(data);
    } catch (err) {
      console.error('Failed to fetch source config:', err);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchSources();
    fetchTemplates();
    fetchTriggers();
  }, [fetchSources, fetchTemplates, fetchTriggers]);

  useEffect(() => {
    if (activeSource) {
      fetchSourceConfig(activeSource);
    }
  }, [activeSource, fetchSourceConfig]);

  // Get triggers for the active source
  const feedTriggers = activeSource
    ? triggers.filter((t) => t.feed_name === activeSource)
    : [];

  // Get all unique event types across all feeds
  const allEventTypes = Array.from(new Set(triggers.map((t) => t.event_type)));

  const handleToggle = async (name: string) => {
    try {
      await fetch(`${API_BASE}/api/feeds/sources/${name}/toggle`, { method: 'POST' });
      fetchSources();
      if (activeSource === name) {
        fetchSourceConfig(name);
      }
    } catch (err) {
      console.error('Failed to toggle source:', err);
    }
  };

  const handleTest = async (name: string) => {
    setTestResult({ status: 'testing', message: 'Testing connection...' });
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sources/${name}/test`, { method: 'POST' });
      const data = await res.json();
      setTestResult(data);
    } catch (err) {
      setTestResult({ status: 'error', message: 'Failed to test connection' });
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete source "${name}"? This cannot be undone.`)) return;
    
    try {
      await fetch(`${API_BASE}/api/feeds/sources/${name}`, { method: 'DELETE' });
      fetchSources();
      if (activeSource === name) {
        setActiveSource(null);
        setSourceConfig(null);
      }
    } catch (err) {
      console.error('Failed to delete source:', err);
    }
  };

  const handleCreateSource = async () => {
    if (!newSourceName.trim()) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newSourceName.trim().toLowerCase().replace(/\s+/g, '_'),
          type: newSourceType,
          description: newSourceDesc || null,
          enabled: false,
          poll_interval: 300,
          auth: {},
          pull: {},
          push: {},
        }),
      });
      
      if (res.ok) {
        setShowAddModal(false);
        setNewSourceName('');
        setNewSourceDesc('');
        fetchSources();
      }
    } catch (err) {
      console.error('Failed to create source:', err);
    }
  };

  const getIcon = (source: FeedsSource) => {
    return SOURCE_ICONS[source.name] || SOURCE_ICONS[source.type] || '📡';
  };

  const startEditing = (section: 'settings' | 'auth' | 'pull' | 'push') => {
    setEditingSection(section);
    setEditedConfig(sourceConfig ? { ...sourceConfig } : null);
  };

  const cancelEditing = () => {
    setEditingSection(null);
    setEditedConfig(null);
  };

  const saveConfig = async () => {
    if (!editedConfig || !activeSource) return;
    
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/feeds/sources/${activeSource}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editedConfig),
      });
      
      if (res.ok) {
        setSourceConfig(editedConfig);
        setEditingSection(null);
        setEditedConfig(null);
        fetchSources();
      }
    } catch (err) {
      console.error('Failed to save config:', err);
    } finally {
      setSaving(false);
    }
  };

  const updateEditedJson = (section: 'auth' | 'pull' | 'push', jsonStr: string) => {
    if (!editedConfig) return;
    
    try {
      const parsed = JSON.parse(jsonStr);
      setEditedConfig({
        ...editedConfig,
        [section]: parsed,
      });
    } catch {
      // Invalid JSON, don't update
    }
  };

  return (
    <div className="page-wrapper feeds-page">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>📡 Feeds Sources</h1>
        <p className="subtitle">Connect external APIs to receive and respond to messages</p>
      </div>

      <div className="feeds-layout">
        {/* Left: Source List */}
        <div className="source-list">
          <div className="source-list-header">
            <span>Sources</span>
            <button className="add-btn" onClick={() => setShowAddModal(true)}>+ Add</button>
          </div>

          {loading ? (
            <div className="loading">Loading...</div>
          ) : sources.length === 0 ? (
            <div className="empty-sources">
              <p>No sources configured</p>
              <button onClick={() => setShowAddModal(true)}>Add your first source</button>
            </div>
          ) : (
            <div className="sources">
              {sources.map((source) => (
                <button
                  key={source.name}
                  className={`source-item ${activeSource === source.name ? 'active' : ''}`}
                  onClick={() => setActiveSource(source.name)}
                >
                  <span className="source-icon">{getIcon(source)}</span>
                  <div className="source-info">
                    <span className="source-name">{source.name}</span>
                    <span className="source-type">{source.type}</span>
                  </div>
                  <div className={`status-indicator ${source.enabled ? 'enabled' : 'disabled'}`} />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Source Detail */}
        <div className="source-detail">
          {!activeSource ? (
            <div className="no-selection">
              <div className="no-selection-icon">📡</div>
              <h3>Select a feed</h3>
              <p>Choose a feed module to view messages, drafts, and actions.</p>
              <button className="primary-btn" onClick={() => setShowAddModal(true)}>
                + Add New Feed
              </button>
            </div>
          ) : configLoading ? (
            <div className="loading">Loading...</div>
          ) : sourceConfig ? (
            <>
              {/* Native Feed Viewer */}
              <div className="feed-viewer-container">
                {FEED_VIEWERS[activeSource] ? (
                  (() => {
                    const ViewerComponent = FEED_VIEWERS[activeSource];
                    return <ViewerComponent />;
                  })()
                ) : (
                  <DefaultViewer feedName={activeSource} />
                )}
              </div>

              {/* Triggers Dropdown */}
              <div className="triggers-section">
                <div 
                  className="section-header clickable"
                  onClick={() => setShowTriggers(!showTriggers)}
                >
                  <h3>⚡ Event Triggers</h3>
                  <div className="trigger-badge">
                    {feedTriggers.length > 0 ? (
                      <span className="trigger-count">{feedTriggers.length}</span>
                    ) : (
                      <span className="trigger-count empty">0</span>
                    )}
                    <span className="expand-arrow">{showTriggers ? '▼' : '▶'}</span>
                  </div>
                </div>
                
                {showTriggers && (
                  <div className="triggers-content">
                    {feedTriggers.length === 0 ? (
                      <div className="no-triggers">
                        <p>No triggers registered for this feed</p>
                        <small>Event types are defined in the feed module</small>
                      </div>
                    ) : (
                      <div className="triggers-list">
                        {feedTriggers.map((trigger) => (
                          <div key={`${trigger.feed_name}.${trigger.event_type}`} className="trigger-item">
                            <div className="trigger-header">
                              <span className="trigger-name">{trigger.event_type}</span>
                            </div>
                            <p className="trigger-desc">{trigger.description}</p>
                            {Object.keys(trigger.payload_schema).length > 0 && (
                              <div className="trigger-schema">
                                {Object.entries(trigger.payload_schema).map(([key, type]) => (
                                  <span key={key} className="schema-field">
                                    <code>{key}</code>: {type}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Settings accordion (collapsed by default) */}
              <details className="feed-settings-accordion">
                <summary>⚙️ Feed Settings</summary>
                <div className="detail-header">
                  <div className="detail-title">
                    <span className="detail-icon">{getIcon(sources.find(s => s.name === activeSource)!)}</span>
                    <div>
                      <h2>{sourceConfig.name}</h2>
                      <span className="detail-type">{sourceConfig.type}</span>
                    </div>
                  </div>
                  <div className="detail-actions">
                    <button
                      className={`toggle-btn ${sourceConfig.enabled ? 'enabled' : ''}`}
                      onClick={() => handleToggle(sourceConfig.name)}
                    >
                      {sourceConfig.enabled ? '✓ Enabled' : 'Disabled'}
                    </button>
                    <button className="test-btn" onClick={() => handleTest(sourceConfig.name)}>
                      Test
                    </button>
                    <button className="delete-btn" onClick={() => handleDelete(sourceConfig.name)}>
                      Delete
                    </button>
                  </div>
                </div>

                {testResult && (
                  <div className={`test-result ${testResult.status}`}>
                    {testResult.status === 'testing' && '⏳ '}
                    {testResult.status === 'ok' && '✓ '}
                    {testResult.status === 'error' && '✗ '}
                    {testResult.message}
                  </div>
                )}

                {sourceConfig.description && (
                  <p className="detail-description">{sourceConfig.description}</p>
                )}

                <div className="config-sections">
                <div className="config-section">
                  <div className="section-header">
                    <h3>⚙️ Settings</h3>
                    {editingSection === 'settings' ? (
                      <div className="edit-actions">
                        <button className="save-btn" onClick={saveConfig} disabled={saving}>
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button className="cancel-edit-btn" onClick={cancelEditing}>Cancel</button>
                      </div>
                    ) : (
                      <button className="edit-btn" onClick={() => startEditing('settings')}>Edit</button>
                    )}
                  </div>
                  {editingSection === 'settings' && editedConfig ? (
                    <div className="config-grid">
                      <div className="config-item">
                        <label>Poll Interval (seconds)</label>
                        <input
                          type="number"
                          value={editedConfig.poll_interval}
                          onChange={(e) => setEditedConfig({ ...editedConfig, poll_interval: parseInt(e.target.value) || 300 })}
                        />
                      </div>
                      <div className="config-item">
                        <label>Type</label>
                        <select
                          value={editedConfig.type}
                          onChange={(e) => setEditedConfig({ ...editedConfig, type: e.target.value })}
                        >
                          <option value="rest">REST API</option>
                          <option value="websocket">WebSocket</option>
                          <option value="webhook">Webhook</option>
                          <option value="imap">IMAP</option>
                        </select>
                      </div>
                      <div className="config-item full">
                        <label>Description</label>
                        <input
                          type="text"
                          value={editedConfig.description || ''}
                          onChange={(e) => setEditedConfig({ ...editedConfig, description: e.target.value })}
                          placeholder="Optional description"
                        />
                      </div>
                    </div>
                  ) : (
                    <div className="config-grid">
                      <div className="config-item">
                        <label>Poll Interval</label>
                        <span>{sourceConfig.poll_interval}s</span>
                      </div>
                      <div className="config-item">
                        <label>Type</label>
                        <span>{sourceConfig.type}</span>
                      </div>
                    </div>
                  )}
                </div>

                <div className="config-section">
                  <div className="section-header">
                    <h3>🔐 Authentication</h3>
                    {editingSection === 'auth' ? (
                      <div className="edit-actions">
                        <button className="save-btn" onClick={saveConfig} disabled={saving}>
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button className="cancel-edit-btn" onClick={cancelEditing}>Cancel</button>
                      </div>
                    ) : (
                      <button className="edit-btn" onClick={() => startEditing('auth')}>Edit</button>
                    )}
                  </div>
                  {editingSection === 'auth' && editedConfig ? (
                    <div className="json-editor">
                      <textarea
                        value={JSON.stringify(editedConfig.auth, null, 2)}
                        onChange={(e) => updateEditedJson('auth', e.target.value)}
                        rows={8}
                        spellCheck={false}
                      />
                    </div>
                  ) : Object.keys(sourceConfig.auth).length === 0 ? (
                    <p className="config-empty">No authentication configured</p>
                  ) : (
                    <div className="config-grid">
                      <div className="config-item">
                        <label>Method</label>
                        <span>{sourceConfig.auth.method || 'none'}</span>
                      </div>
                      {sourceConfig.auth.token_env && (
                        <div className="config-item">
                          <label>Token Env</label>
                          <code>{sourceConfig.auth.token_env}</code>
                        </div>
                      )}
                      {sourceConfig.auth.token_path && (
                        <div className="config-item">
                          <label>Token Path</label>
                          <code>{sourceConfig.auth.token_path}</code>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="config-section">
                  <div className="section-header">
                    <h3>📥 Pull Configuration</h3>
                    {editingSection === 'pull' ? (
                      <div className="edit-actions">
                        <button className="save-btn" onClick={saveConfig} disabled={saving}>
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button className="cancel-edit-btn" onClick={cancelEditing}>Cancel</button>
                      </div>
                    ) : (
                      <button className="edit-btn" onClick={() => startEditing('pull')}>Edit</button>
                    )}
                  </div>
                  {editingSection === 'pull' && editedConfig ? (
                    <div className="json-editor">
                      <textarea
                        value={JSON.stringify(editedConfig.pull, null, 2)}
                        onChange={(e) => updateEditedJson('pull', e.target.value)}
                        rows={12}
                        spellCheck={false}
                      />
                    </div>
                  ) : Object.keys(sourceConfig.pull).length === 0 ? (
                    <p className="config-empty">No pull endpoint configured</p>
                  ) : (
                    <div className="config-grid">
                      <div className="config-item full">
                        <label>Endpoint</label>
                        <code>{sourceConfig.pull.endpoint || 'Not set'}</code>
                      </div>
                      <div className="config-item">
                        <label>Method</label>
                        <span>{sourceConfig.pull.method || 'GET'}</span>
                      </div>
                      {sourceConfig.pull.params && (
                        <div className="config-item full">
                          <label>Params</label>
                          <code className="small">{JSON.stringify(sourceConfig.pull.params)}</code>
                        </div>
                      )}
                      {sourceConfig.pull.mapping && (
                        <div className="config-item full">
                          <label>Field Mapping</label>
                          <pre className="mapping-preview">{JSON.stringify(sourceConfig.pull.mapping, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="config-section">
                  <div className="section-header">
                    <h3>📤 Push Configuration</h3>
                    {editingSection === 'push' ? (
                      <div className="edit-actions">
                        <button className="save-btn" onClick={saveConfig} disabled={saving}>
                          {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button className="cancel-edit-btn" onClick={cancelEditing}>Cancel</button>
                      </div>
                    ) : (
                      <button className="edit-btn" onClick={() => startEditing('push')}>Edit</button>
                    )}
                  </div>
                  {editingSection === 'push' && editedConfig ? (
                    <div className="json-editor">
                      <textarea
                        value={JSON.stringify(editedConfig.push, null, 2)}
                        onChange={(e) => updateEditedJson('push', e.target.value)}
                        rows={12}
                        spellCheck={false}
                      />
                    </div>
                  ) : Object.keys(sourceConfig.push).length === 0 ? (
                    <p className="config-empty">No push endpoint configured</p>
                  ) : (
                    <div className="config-grid">
                      <div className="config-item full">
                        <label>Endpoint</label>
                        <code>{sourceConfig.push.endpoint || 'Not set'}</code>
                      </div>
                      <div className="config-item">
                        <label>Method</label>
                        <span>{sourceConfig.push.method || 'POST'}</span>
                      </div>
                      {sourceConfig.push.body_template && (
                        <div className="config-item full">
                          <label>Body Template</label>
                          <pre className="mapping-preview">{JSON.stringify(sourceConfig.push.body_template, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="config-section collapsible">
                  <details>
                    <summary><h3>📝 Raw Config (JSON)</h3></summary>
                    <pre className="yaml-preview">
                      {JSON.stringify(sourceConfig, null, 2)}
                    </pre>
                  </details>
                </div>
              </div>
              </details>
            </>
          ) : null}
        </div>
      </div>

      {/* Add Source Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h2>Add Feeds Source</h2>
            
            <div className="template-grid">
              {templates.filter(t => t.icon).map((template) => (
                <button
                  key={template.name}
                  className={`template-card ${template.exists ? 'exists' : ''}`}
                  onClick={() => {
                    if (!template.exists) {
                      setNewSourceName(template.name);
                      setNewSourceType('rest');
                      setNewSourceDesc(template.description);
                    }
                  }}
                  disabled={template.exists}
                >
                  <span className="template-icon">{template.icon}</span>
                  <span className="template-name">{template.name}</span>
                  <span className="template-desc">{template.description}</span>
                  {template.exists && <span className="exists-badge">Added</span>}
                </button>
              ))}
            </div>

            <div className="divider">or create custom</div>

            <div className="form-group">
              <label>Source Name</label>
              <input
                type="text"
                value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)}
                placeholder="my_api"
              />
            </div>

            <div className="form-group">
              <label>Type</label>
              <select value={newSourceType} onChange={(e) => setNewSourceType(e.target.value)}>
                <option value="rest">REST API</option>
                <option value="websocket">WebSocket</option>
                <option value="imap">IMAP (Email)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Description</label>
              <input
                type="text"
                value={newSourceDesc}
                onChange={(e) => setNewSourceDesc(e.target.value)}
                placeholder="Optional description"
              />
            </div>

            <div className="modal-actions">
              <button className="cancel-btn" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button 
                className="create-btn" 
                onClick={handleCreateSource}
                disabled={!newSourceName.trim()}
              >
                Create Source
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
