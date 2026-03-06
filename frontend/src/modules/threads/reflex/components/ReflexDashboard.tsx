import { useState, useEffect, useCallback } from 'react';
import './ReflexDashboard.css';

interface Reflex {
  key: string;
  module: 'greetings' | 'shortcuts' | 'system';
  pattern: string;
  response: string;
  description: string;
  weight: number;
  icon: string;
}

interface Trigger {
  id: number;
  name: string;
  description: string;
  trigger_type: string;  // webhook | poll | schedule
  feed_name: string;
  event_type: string;
  condition_json: string | null;
  tool_name: string;
  tool_action: string;
  tool_params_json: string | null;
  response_mode: string;  // tool | agent | notify
  enabled: boolean;
  priority: number;
  poll_interval: number | null;
  cron_expression: string | null;
  execution_count: number;
  last_executed: string | null;
  last_error: string | null;
  created_at: string;
}

interface Protocol {
  triggers: number;
  description: string;
}

interface ReflexStats {
  total: number;
  by_module: {
    greetings: number;
    shortcuts: number;
    system: number;
  };
  average_weight: number;
}

const MODULE_INFO: Record<string, { icon: string; label: string; color: string; desc: string }> = {
  greetings: {
    icon: '👋',
    label: 'Greetings',
    color: '#22c55e',
    desc: 'Quick greeting responses'
  },
  shortcuts: {
    icon: '⚡',
    label: 'Shortcuts',
    color: '#f59e0b',
    desc: 'User-defined commands'
  },
  system: {
    icon: '🔧',
    label: 'System',
    color: '#6366f1',
    desc: 'System-level triggers'
  }
};

const RESPONSE_MODE_INFO: Record<string, { icon: string; label: string; color: string }> = {
  tool:   { icon: '🔧', label: 'Tool',   color: '#6366f1' },
  agent:  { icon: '🤖', label: 'Agent',  color: '#22c55e' },
  notify: { icon: '🔔', label: 'Notify', color: '#f59e0b' },
};

const TRIGGER_TYPE_LABELS: Record<string, string> = {
  webhook: '⚡ Webhook',
  poll: '🔄 Poll',
  schedule: '🕐 Schedule',
};

export default function ReflexDashboard() {
  const [reflexes, setReflexes] = useState<Reflex[]>([]);
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [protocols, setProtocols] = useState<Record<string, Protocol>>({});
  const [stats, setStats] = useState<ReflexStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedReflex, setSelectedReflex] = useState<Reflex | null>(null);
  const [selectedTrigger, setSelectedTrigger] = useState<Trigger | null>(null);
  const [moduleFilter, setModuleFilter] = useState<string>('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [testInput, setTestInput] = useState('');
  const [testResult, setTestResult] = useState<{ matched: boolean; response: string | null } | null>(null);
  const [installResult, setInstallResult] = useState<string | null>(null);

  // New reflex form state
  const [newModule, setNewModule] = useState<'greetings' | 'shortcuts' | 'system'>('greetings');
  const [newKey, setNewKey] = useState('');
  const [newPattern, setNewPattern] = useState('');
  const [newResponse, setNewResponse] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newWeight, setNewWeight] = useState(0.5);

  const fetchReflexes = useCallback(async () => {
    try {
      setLoading(true);
      const [allRes, statsRes, trigRes, protoRes] = await Promise.all([
        fetch('http://localhost:8000/api/reflex/all'),
        fetch('http://localhost:8000/api/reflex/stats'),
        fetch('http://localhost:8000/api/reflex/triggers'),
        fetch('http://localhost:8000/api/reflex/protocols'),
      ]);
      
      if (allRes.ok) {
        const data = await allRes.json();
        setReflexes(data.reflexes || []);
      }
      
      if (statsRes.ok) {
        const data = await statsRes.json();
        setStats(data);
      }

      if (trigRes.ok) {
        const data = await trigRes.json();
        setTriggers(data.triggers || []);
      }

      if (protoRes.ok) {
        const data = await protoRes.json();
        setProtocols(data.protocols || {});
      }
    } catch (err) {
      console.error('Failed to fetch reflexes:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchReflexes();
  }, [fetchReflexes]);

  const handleDelete = async (reflex: Reflex) => {
    if (!confirm(`Delete reflex "${reflex.key}"?`)) return;
    
    try {
      const res = await fetch(`http://localhost:8000/api/reflex/${reflex.module}/${reflex.key}`, {
        method: 'DELETE'
      });
      
      if (res.ok) {
        setSelectedReflex(null);
        fetchReflexes();
      }
    } catch (err) {
      console.error('Failed to delete reflex:', err);
    }
  };

  const handleTest = async () => {
    if (!testInput.trim()) return;
    
    try {
      const res = await fetch(`http://localhost:8000/api/reflex/test?text=${encodeURIComponent(testInput)}`, {
        method: 'POST'
      });
      
      if (res.ok) {
        const data = await res.json();
        setTestResult(data);
      }
    } catch (err) {
      console.error('Failed to test reflex:', err);
    }
  };

  const handleCreate = async () => {
    if (!newKey.trim()) return;
    
    try {
      let endpoint = '';
      let body: Record<string, any> = {};
      
      if (newModule === 'greetings') {
        endpoint = '/api/reflex/greetings';
        body = {
          key: newKey,
          pattern: newPattern || newKey,
          response: newResponse,
          description: newDescription,
          weight: newWeight
        };
      } else if (newModule === 'shortcuts') {
        endpoint = '/api/reflex/shortcuts';
        body = {
          trigger: newPattern || newKey,
          response: newResponse,
          description: newDescription
        };
      } else {
        endpoint = '/api/reflex/system';
        body = {
          key: newKey,
          trigger_type: newPattern,
          action: newResponse,
          description: newDescription,
          weight: newWeight
        };
      }
      
      const res = await fetch(`http://localhost:8000${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      
      if (res.ok) {
        setShowAddModal(false);
        resetForm();
        fetchReflexes();
      }
    } catch (err) {
      console.error('Failed to create reflex:', err);
    }
  };

  const resetForm = () => {
    setNewModule('greetings');
    setNewKey('');
    setNewPattern('');
    setNewResponse('');
    setNewDescription('');
    setNewWeight(0.5);
  };

  // ── Trigger actions ──

  const toggleTrigger = async (id: number) => {
    try {
      const res = await fetch(`http://localhost:8000/api/reflex/triggers/${id}/toggle`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setTriggers(prev => prev.map(t => t.id === id ? { ...t, enabled: data.enabled } : t));
        if (selectedTrigger?.id === id) setSelectedTrigger(prev => prev ? { ...prev, enabled: data.enabled } : null);
      }
    } catch (err) { console.error('Toggle failed:', err); }
  };

  const deleteTrigger = async (id: number) => {
    if (!confirm('Delete this trigger?')) return;
    try {
      const res = await fetch(`http://localhost:8000/api/reflex/triggers/${id}`, { method: 'DELETE' });
      if (res.ok) {
        setSelectedTrigger(null);
        fetchReflexes();
      }
    } catch (err) { console.error('Delete trigger failed:', err); }
  };

  const installProtocol = async (name: string) => {
    try {
      const res = await fetch(`http://localhost:8000/api/reflex/protocols/${name}/install`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setInstallResult(`✓ ${name}: ${data.triggers_created} trigger(s) installed`);
        fetchReflexes();
        setTimeout(() => setInstallResult(null), 4000);
      }
    } catch (err) {
      setInstallResult(`✕ Failed to install ${name}`);
      setTimeout(() => setInstallResult(null), 4000);
    }
  };

  const filteredReflexes = moduleFilter === 'all' 
    ? reflexes 
    : reflexes.filter(r => r.module === moduleFilter);

  const groupedReflexes = filteredReflexes.reduce((acc, r) => {
    if (!acc[r.module]) acc[r.module] = [];
    acc[r.module].push(r);
    return acc;
  }, {} as Record<string, Reflex[]>);

  if (loading) {
    return <div className="reflex-dashboard loading">Loading reflexes...</div>;
  }

  return (
    <div className="reflex-dashboard">
      <div className="reflex-layout">
        {/* Left: Reflex List */}
        <div className="reflex-list">
          <div className="reflex-list-header">
            <span>Reflexes</span>
            <button className="add-btn" onClick={() => setShowAddModal(true)}>+ Add</button>
          </div>
          
          {/* Stats Bar */}
          {stats && (
            <div className="stats-bar">
              <div className="stat-item">
                <span className="stat-value">{stats.total}</span>
                <span className="stat-label">Patterns</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{triggers.length}</span>
                <span className="stat-label">Triggers</span>
              </div>
              <div className="stat-item">
                <span className="stat-value">{triggers.filter(t => t.enabled).length}</span>
                <span className="stat-label">Active</span>
              </div>
            </div>
          )}
          
          {/* Filter */}
          <div className="reflex-filters">
            <select 
              value={moduleFilter} 
              onChange={(e) => setModuleFilter(e.target.value)}
              className="filter-select"
            >
              <option value="all">All Modules</option>
              <option value="greetings">👋 Greetings</option>
              <option value="shortcuts">⚡ Shortcuts</option>
              <option value="system">🔧 System</option>
            </select>
          </div>
          
          {/* Reflex Groups */}
          <div className="reflexes-grouped">
            {Object.entries(groupedReflexes).map(([module, items]) => (
              <div key={module} className="reflex-group">
                <div className="group-header" style={{ borderLeftColor: MODULE_INFO[module]?.color }}>
                  <span className="group-icon">{MODULE_INFO[module]?.icon}</span>
                  <span className="group-label">{MODULE_INFO[module]?.label}</span>
                  <span className="group-count">{items.length}</span>
                </div>
                
                {items.map(reflex => (
                  <button
                    key={reflex.key}
                    className={`reflex-item ${selectedReflex?.key === reflex.key ? 'active' : ''}`}
                    onClick={() => { setSelectedTrigger(null); setSelectedReflex(reflex); }}
                  >
                    <div className="reflex-info">
                      <span className="reflex-pattern">{reflex.pattern || reflex.key}</span>
                      <span className="reflex-response">{reflex.response}</span>
                    </div>
                    <div className="reflex-weight-indicator" style={{ 
                      width: `${reflex.weight * 100}%`,
                      background: MODULE_INFO[reflex.module]?.color 
                    }} />
                  </button>
                ))}
              </div>
            ))}
            
            {filteredReflexes.length === 0 && triggers.length === 0 && (
              <div className="no-reflexes">No reflexes or triggers found</div>
            )}

            {/* ── DB Triggers (persistent) ── */}
            {triggers.length > 0 && (
              <div className="reflex-group">
                <div className="group-header" style={{ borderLeftColor: '#8b5cf6' }}>
                  <span className="group-icon">🎯</span>
                  <span className="group-label">Triggers</span>
                  <span className="group-count">{triggers.length}</span>
                </div>
                {triggers.map(trig => (
                  <button
                    key={`trig-${trig.id}`}
                    className={`reflex-item ${selectedTrigger?.id === trig.id ? 'active' : ''}`}
                    onClick={() => { setSelectedReflex(null); setSelectedTrigger(trig); }}
                  >
                    <div className="reflex-info">
                      <span className="reflex-pattern">
                        {!trig.enabled && <span style={{ opacity: 0.4 }}>⏸ </span>}
                        {trig.name}
                      </span>
                      <span className="reflex-response">
                        {RESPONSE_MODE_INFO[trig.response_mode]?.icon || '🔧'}{' '}
                        {trig.feed_name}/{trig.event_type}
                      </span>
                    </div>
                    <div className="reflex-weight-indicator" style={{
                      width: `${(trig.priority / 10) * 100}%`,
                      background: RESPONSE_MODE_INFO[trig.response_mode]?.color || '#8b5cf6',
                    }} />
                  </button>
                ))}
              </div>
            )}

            {/* ── Protocol Templates ── */}
            {Object.keys(protocols).length > 0 && (
              <div className="reflex-group">
                <div className="group-header" style={{ borderLeftColor: '#ec4899' }}>
                  <span className="group-icon">📋</span>
                  <span className="group-label">Protocols</span>
                  <span className="group-count">{Object.keys(protocols).length}</span>
                </div>
                {Object.entries(protocols).map(([name, proto]) => (
                  <button
                    key={`proto-${name}`}
                    className="reflex-item protocol-item"
                    onClick={() => installProtocol(name)}
                    title={proto.description}
                  >
                    <div className="reflex-info">
                      <span className="reflex-pattern">{name.replace(/_/g, ' ')}</span>
                      <span className="reflex-response">{proto.description}</span>
                    </div>
                  </button>
                ))}
                {installResult && (
                  <div className="install-result">{installResult}</div>
                )}
              </div>
            )}
          </div>
        </div>
        
        {/* Right: Detail Panel */}
        <div className="reflex-detail">
          {selectedTrigger ? (
            /* ── Trigger Detail ── */
            <>
              <div className="detail-header">
                <div className="detail-title">
                  <span className="detail-icon">🎯</span>
                  <div>
                    <h2>{selectedTrigger.name}</h2>
                    <span className="detail-module">
                      {TRIGGER_TYPE_LABELS[selectedTrigger.trigger_type] || selectedTrigger.trigger_type}
                      {' · '}
                      {RESPONSE_MODE_INFO[selectedTrigger.response_mode]?.icon}{' '}
                      {RESPONSE_MODE_INFO[selectedTrigger.response_mode]?.label}
                    </span>
                  </div>
                </div>
                <div className="detail-actions">
                  <button
                    className={`toggle-btn ${selectedTrigger.enabled ? 'enabled' : 'disabled'}`}
                    onClick={() => toggleTrigger(selectedTrigger.id)}
                  >
                    {selectedTrigger.enabled ? '● Enabled' : '○ Disabled'}
                  </button>
                  <button className="delete-btn" onClick={() => deleteTrigger(selectedTrigger.id)}>Delete</button>
                </div>
              </div>

              <div className="detail-sections">
                {selectedTrigger.description && (
                  <div className="detail-section">
                    <h3>Description</h3>
                    <p>{selectedTrigger.description}</p>
                  </div>
                )}

                <div className="detail-section">
                  <h3>Source</h3>
                  <div className="trigger-config-grid">
                    <div className="trigger-config-row">
                      <span className="config-label">Feed</span>
                      <span className="config-value">{selectedTrigger.feed_name}</span>
                    </div>
                    <div className="trigger-config-row">
                      <span className="config-label">Event</span>
                      <span className="config-value">{selectedTrigger.event_type}</span>
                    </div>
                    {selectedTrigger.cron_expression && (
                      <div className="trigger-config-row">
                        <span className="config-label">Cron</span>
                        <code className="config-value mono">{selectedTrigger.cron_expression}</code>
                      </div>
                    )}
                    {selectedTrigger.poll_interval && (
                      <div className="trigger-config-row">
                        <span className="config-label">Poll</span>
                        <span className="config-value">Every {selectedTrigger.poll_interval}s</span>
                      </div>
                    )}
                    {selectedTrigger.condition_json && (
                      <div className="trigger-config-row">
                        <span className="config-label">Condition</span>
                        <code className="config-value mono condition-json">
                          {typeof selectedTrigger.condition_json === 'string'
                            ? selectedTrigger.condition_json
                            : JSON.stringify(selectedTrigger.condition_json, null, 2)}
                        </code>
                      </div>
                    )}
                  </div>
                </div>

                <div className="detail-section">
                  <h3>Action</h3>
                  <div className="trigger-config-grid">
                    <div className="trigger-config-row">
                      <span className="config-label">Mode</span>
                      <span className="config-value"
                        style={{ color: RESPONSE_MODE_INFO[selectedTrigger.response_mode]?.color }}>
                        {RESPONSE_MODE_INFO[selectedTrigger.response_mode]?.icon}{' '}
                        {RESPONSE_MODE_INFO[selectedTrigger.response_mode]?.label}
                      </span>
                    </div>
                    {selectedTrigger.tool_name && (
                      <div className="trigger-config-row">
                        <span className="config-label">Tool</span>
                        <span className="config-value">{selectedTrigger.tool_name}</span>
                      </div>
                    )}
                    {selectedTrigger.tool_action && (
                      <div className="trigger-config-row">
                        <span className="config-label">Action</span>
                        <span className="config-value">{selectedTrigger.tool_action}</span>
                      </div>
                    )}
                    <div className="trigger-config-row">
                      <span className="config-label">Priority</span>
                      <span className="config-value">{selectedTrigger.priority} / 10</span>
                    </div>
                  </div>
                </div>

                <div className="detail-section">
                  <h3>Stats</h3>
                  <div className="trigger-config-grid">
                    <div className="trigger-config-row">
                      <span className="config-label">Executions</span>
                      <span className="config-value">{selectedTrigger.execution_count}</span>
                    </div>
                    {selectedTrigger.last_executed && (
                      <div className="trigger-config-row">
                        <span className="config-label">Last Run</span>
                        <span className="config-value">
                          {new Date(selectedTrigger.last_executed).toLocaleString()}
                        </span>
                      </div>
                    )}
                    {selectedTrigger.last_error && (
                      <div className="trigger-config-row">
                        <span className="config-label">Last Error</span>
                        <span className="config-value error-text">{selectedTrigger.last_error}</span>
                      </div>
                    )}
                    <div className="trigger-config-row">
                      <span className="config-label">Created</span>
                      <span className="config-value">
                        {new Date(selectedTrigger.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </>
          ) : selectedReflex ? (
            <>
              <div className="detail-header">
                <div className="detail-title">
                  <span className="detail-icon">{MODULE_INFO[selectedReflex.module]?.icon}</span>
                  <div>
                    <h2>{selectedReflex.key}</h2>
                    <span className="detail-module">{MODULE_INFO[selectedReflex.module]?.label}</span>
                  </div>
                </div>
                <div className="detail-actions">
                  <button className="delete-btn" onClick={() => handleDelete(selectedReflex)}>Delete</button>
                </div>
              </div>
              
              <div className="detail-sections">
                <div className="detail-section">
                  <h3>Pattern / Trigger</h3>
                  <div className="pattern-display">
                    <code>{selectedReflex.pattern || selectedReflex.key}</code>
                  </div>
                </div>
                
                <div className="detail-section">
                  <h3>Response / Action</h3>
                  <div className="response-display">
                    {selectedReflex.response}
                  </div>
                </div>
                
                {selectedReflex.description && (
                  <div className="detail-section">
                    <h3>Description</h3>
                    <p>{selectedReflex.description}</p>
                  </div>
                )}
                
                <div className="detail-section">
                  <h3>Weight (Priority)</h3>
                  <div className="weight-bar">
                    <div 
                      className="weight-fill" 
                      style={{ 
                        width: `${selectedReflex.weight * 100}%`,
                        background: MODULE_INFO[selectedReflex.module]?.color
                      }} 
                    />
                    <span className="weight-label">{(selectedReflex.weight * 100).toFixed(0)}%</span>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="no-selection">
              <div className="no-selection-icon">⚡</div>
              <h3>Reflex Dashboard</h3>
              <p>Select a reflex to view details</p>
              
              {/* Test Area */}
              <div className="test-area">
                <h4>Test Reflexes</h4>
                <div className="test-input-group">
                  <input
                    type="text"
                    value={testInput}
                    onChange={(e) => setTestInput(e.target.value)}
                    placeholder="Type a message to test..."
                    onKeyDown={(e) => e.key === 'Enter' && handleTest()}
                  />
                  <button onClick={handleTest}>Test</button>
                </div>
                
                {testResult && (
                  <div className={`test-result ${testResult.matched ? 'matched' : 'no-match'}`}>
                    {testResult.matched ? (
                      <>
                        <span className="match-label">✓ Match found</span>
                        <span className="match-response">{testResult.response}</span>
                      </>
                    ) : (
                      <span className="no-match-label">No reflex matched</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      
      {/* Add Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Add Reflex</h2>
              <button className="close-btn" onClick={() => setShowAddModal(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div className="form-group">
                <label>Module</label>
                <select 
                  value={newModule} 
                  onChange={(e) => setNewModule(e.target.value as any)}
                >
                  <option value="greetings">👋 Greetings</option>
                  <option value="shortcuts">⚡ Shortcuts</option>
                  <option value="system">🔧 System</option>
                </select>
              </div>
              
              <div className="form-group">
                <label>Key (unique identifier)</label>
                <input
                  type="text"
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  placeholder={newModule === 'greetings' ? 'hello' : newModule === 'shortcuts' ? 'help' : 'error_handler'}
                />
              </div>
              
              <div className="form-group">
                <label>
                  {newModule === 'greetings' ? 'Pattern (trigger word)' : 
                   newModule === 'shortcuts' ? 'Trigger (e.g., /help)' : 
                   'Trigger Type (e.g., error, timeout)'}
                </label>
                <input
                  type="text"
                  value={newPattern}
                  onChange={(e) => setNewPattern(e.target.value)}
                  placeholder={newModule === 'greetings' ? 'hello, hi' : newModule === 'shortcuts' ? '/help' : 'error'}
                />
              </div>
              
              <div className="form-group">
                <label>
                  {newModule === 'system' ? 'Action' : 'Response'}
                </label>
                <textarea
                  value={newResponse}
                  onChange={(e) => setNewResponse(e.target.value)}
                  placeholder={newModule === 'greetings' ? 'Hey! How can I help?' : newModule === 'shortcuts' ? 'Here are the available commands...' : 'log_and_notify'}
                  rows={3}
                />
              </div>
              
              <div className="form-group">
                <label>Description (optional)</label>
                <input
                  type="text"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Brief description of this reflex"
                />
              </div>
              
              {newModule !== 'shortcuts' && (
                <div className="form-group">
                  <label>Weight (Priority): {(newWeight * 100).toFixed(0)}%</label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={newWeight}
                    onChange={(e) => setNewWeight(parseFloat(e.target.value))}
                  />
                </div>
              )}
            </div>
            
            <div className="modal-footer">
              <button className="cancel-btn" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button 
                className="create-btn" 
                onClick={handleCreate}
                disabled={!newKey.trim()}
              >
                Create Reflex
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
