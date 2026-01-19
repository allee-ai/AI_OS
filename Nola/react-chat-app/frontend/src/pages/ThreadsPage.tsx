import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './ThreadsPage.css';
import ToolDashboard from '../components/ToolDashboard';
import ReflexDashboard from '../components/ReflexDashboard';
import ProfilesPage from './ProfilesPage';
import ConceptGraph3D from '../components/ConceptGraph3D';

interface ThreadHealth {
  name: string;
  status: string;
  message: string;
  has_data: boolean;
}

interface IdentityRow {
  key: string;
  metadata_type: string;
  metadata_desc: string;
  l1: string;
  l2: string;
  l3: string;
  weight: number;
}

// Philosophy uses same structure as Identity
type PhilosophyRow = IdentityRow;

interface GenericRow {
  key: string;
  data: Record<string, any>;
  metadata: Record<string, any>;
  level: number;
  weight: number;
}

interface LogEvent {
  id: number;
  timestamp: string;
  event_type: string;
  source: string;
  message: string;
  level?: string;
  metadata?: Record<string, any>;
  session_id?: string;
}

const THREAD_ICONS: Record<string, string> = {
  identity: '🪪',
  log: '📜',
  philosophy: '🏛️',
  reflex: '⚡',
  form: '🔧',
  linking_core: '🔗',
};

// Threads that display documentation instead of data tables
const DOC_THREADS = new Set<string>([]);  // linking_core now has 3D viz

// Event type options for log
const EVENT_TYPES = ['convo', 'system', 'user_action', 'memory', 'activation', 'file'];
const EVENT_SOURCES = ['local', 'agent', 'daemon', 'web_public'];

// Type options for identity and philosophy
const IDENTITY_TYPES = ['user', 'nola', 'machine', 'relationship'];
const PHILOSOPHY_TYPES = ['value', 'constraint', 'style'];

export const ThreadsPage = () => {
  const [threads, setThreads] = useState<Record<string, ThreadHealth>>({});
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [identityRows, setIdentityRows] = useState<IdentityRow[]>([]);
  const [philosophyRows, setPhilosophyRows] = useState<PhilosophyRow[]>([]);
  const [genericModules, setGenericModules] = useState<Record<string, GenericRow[]>>({});
  const [readmeContent, setReadmeContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);
  const [activeLevel, setActiveLevel] = useState<1 | 2 | 3>(2);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<Partial<IdentityRow>>({});
  const [saving, setSaving] = useState(false);

  // Log thread state
  const [logEvents, setLogEvents] = useState<LogEvent[]>([]);
  const [logLimit, setLogLimit] = useState<number>(20);
  const [logSortField, setLogSortField] = useState<'timestamp' | 'event_type' | 'source'>('timestamp');
  const [logSortAsc, setLogSortAsc] = useState<boolean>(false);
  const [logTypeFilter, setLogTypeFilter] = useState<string>('');
  const [logSourceFilter, setLogSourceFilter] = useState<string>('');
  const [logLoading, setLogLoading] = useState<boolean>(false);

  // Add event form
  const [newEventType, setNewEventType] = useState<string>('user_action');
  const [newEventSource, setNewEventSource] = useState<string>('local');
  const [newEventMessage, setNewEventMessage] = useState<string>('');
  const [addingEvent, setAddingEvent] = useState<boolean>(false);
  const [addEventResult, setAddEventResult] = useState<string | null>(null);

  // Add row form state (shared for identity/philosophy)
  const [showAddRow, setShowAddRow] = useState<boolean>(false);
  const [newRowKey, setNewRowKey] = useState<string>('');
  const [newRowType, setNewRowType] = useState<string>('user');
  const [newRowDesc, setNewRowDesc] = useState<string>('');
  const [newRowL1, setNewRowL1] = useState<string>('');
  const [newRowL2, setNewRowL2] = useState<string>('');
  const [newRowL3, setNewRowL3] = useState<string>('');
  const [newRowWeight, setNewRowWeight] = useState<number>(0.5);
  const [addingRow, setAddingRow] = useState<boolean>(false);
  const [addRowResult, setAddRowResult] = useState<string | null>(null);

  const fetchIdentityData = () => {
    fetch('http://localhost:8000/api/introspection/identity/table')
      .then(res => res.json())
      .then(data => {
        setIdentityRows(data.rows || []);
        setGenericModules({});
        setDataLoading(false);
      })
      .catch(() => {
        setIdentityRows([]);
        setDataLoading(false);
      });
  };

  const fetchPhilosophyData = () => {
    fetch('http://localhost:8000/api/introspection/philosophy/table')
      .then(res => res.json())
      .then(data => {
        setPhilosophyRows(data.rows || []);
        setGenericModules({});
        setDataLoading(false);
      })
      .catch(() => {
        setPhilosophyRows([]);
        setDataLoading(false);
      });
  };

  const fetchLogEvents = useCallback(() => {
    setLogLoading(true);
    const params = new URLSearchParams({ limit: String(logLimit) });
    if (logTypeFilter) params.set('event_type', logTypeFilter);
    if (logSourceFilter) params.set('source', logSourceFilter);

    fetch(`http://localhost:8000/api/introspection/events?${params}`)
      .then(res => res.json())
      .then((data: LogEvent[]) => {
        // Sort client-side
        const sorted = [...data].sort((a, b) => {
          let cmp = 0;
          if (logSortField === 'timestamp') {
            cmp = new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime();
          } else if (logSortField === 'event_type') {
            cmp = a.event_type.localeCompare(b.event_type);
          } else if (logSortField === 'source') {
            cmp = a.source.localeCompare(b.source);
          }
          return logSortAsc ? cmp : -cmp;
        });
        setLogEvents(sorted);
        setLogLoading(false);
      })
      .catch(() => {
        setLogEvents([]);
        setLogLoading(false);
      });
  }, [logLimit, logTypeFilter, logSourceFilter, logSortField, logSortAsc]);

  const handleAddEvent = async () => {
    if (!newEventMessage.trim()) {
      setAddEventResult('Enter a message');
      return;
    }
    setAddingEvent(true);
    setAddEventResult(null);
    try {
      const res = await fetch('http://localhost:8000/api/introspection/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: newEventType,
          data: newEventMessage.trim(),
          source: newEventSource,
        }),
      });
      if (res.ok) {
        setAddEventResult('✓ Added');
        setNewEventMessage('');
        fetchLogEvents();
      } else {
        setAddEventResult('⚠ Failed');
      }
    } catch {
      setAddEventResult('⚠ Error');
    } finally {
      setAddingEvent(false);
      setTimeout(() => setAddEventResult(null), 2500);
    }
  };

  useEffect(() => {
    fetch('http://localhost:8000/api/introspection/threads/health')
      .then(res => res.json())
      .then(data => {
        setThreads(data.threads || {});
        setLoading(false);
        const firstWithData = Object.values(data.threads || {}).find((t: any) => t.has_data);
        if (firstWithData) {
          setActiveThread((firstWithData as ThreadHealth).name);
        }
      })
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!activeThread) return;
    
    setDataLoading(true);
    setEditingKey(null);
    setReadmeContent('');
    
    // Documentation threads - fetch README
    if (DOC_THREADS.has(activeThread)) {
      fetch(`http://localhost:8000/api/introspection/threads/${activeThread}/readme`)
        .then(res => res.json())
        .then(data => {
          setReadmeContent(data.content || '');
          setIdentityRows([]);
          setGenericModules({});
          setDataLoading(false);
        })
        .catch(() => {
          setReadmeContent('');
          setDataLoading(false);
        });
      return;
    }
    
    if (activeThread === 'identity') {
      // fetchIdentityData(); // Replaced by ProfilesPage component
      setDataLoading(false);
    } else if (activeThread === 'philosophy') {
      fetchPhilosophyData();
    } else if (activeThread === 'log') {
      fetchLogEvents();
      setDataLoading(false);
    } else {
      fetch(`http://localhost:8000/api/introspection/threads/${activeThread}?level=2`)
        .then(res => res.json())
        .then(data => {
          setGenericModules(data.modules || {});
          setIdentityRows([]);
          setPhilosophyRows([]);
          setDataLoading(false);
        })
        .catch(() => {
          setGenericModules({});
          setDataLoading(false);
        });
    }
  }, [activeThread, fetchLogEvents]);

  const startEditing = (row: IdentityRow | PhilosophyRow) => {
    setEditingKey(row.key);
    setEditForm({ ...row });
  };

  const cancelEditing = () => {
    setEditingKey(null);
    setEditForm({});
  };

  const saveEdit = async () => {
    if (!editingKey || !editForm.l1 || !editForm.l2 || !editForm.l3) return;
    
    // Determine which thread we're editing
    const endpoint = activeThread === 'philosophy' 
      ? `http://localhost:8000/api/introspection/philosophy/${editingKey}`
      : `http://localhost:8000/api/introspection/identity/${editingKey}`;
    
    setSaving(true);
    try {
      const res = await fetch(endpoint, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          l1: editForm.l1,
          l2: editForm.l2,
          l3: editForm.l3,
          weight: editForm.weight,
          metadata_type: editForm.metadata_type,
          metadata_desc: editForm.metadata_desc,
        }),
      });
      
      if (res.ok) {
        if (activeThread === 'philosophy') {
          fetchPhilosophyData();
        } else {
          fetchIdentityData();
        }
        setEditingKey(null);
        setEditForm({});
      }
    } catch (e) {
      console.error('Save failed:', e);
    }
    setSaving(false);
  };

  const resetAddRowForm = () => {
    setNewRowKey('');
    setNewRowType(activeThread === 'philosophy' ? 'value' : 'user');
    setNewRowDesc('');
    setNewRowL1('');
    setNewRowL2('');
    setNewRowL3('');
    setNewRowWeight(0.5);
    setShowAddRow(false);
    setAddRowResult(null);
  };

  const handleAddRow = async () => {
    if (!newRowKey.trim() || !newRowL1.trim() || !newRowL2.trim() || !newRowL3.trim()) {
      setAddRowResult('⚠ Fill in key and all L1/L2/L3 fields');
      return;
    }
    
    const endpoint = activeThread === 'philosophy'
      ? `http://localhost:8000/api/introspection/philosophy?key=${encodeURIComponent(newRowKey.trim())}`
      : `http://localhost:8000/api/introspection/identity?key=${encodeURIComponent(newRowKey.trim())}`;
    
    setAddingRow(true);
    setAddRowResult(null);
    
    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          l1: newRowL1.trim(),
          l2: newRowL2.trim(),
          l3: newRowL3.trim(),
          weight: newRowWeight,
          metadata_type: newRowType,
          metadata_desc: newRowDesc.trim(),
        }),
      });
      
      if (res.ok) {
        setAddRowResult('✓ Added');
        if (activeThread === 'philosophy') {
          fetchPhilosophyData();
        } else {
          fetchIdentityData();
        }
        setTimeout(() => {
          resetAddRowForm();
        }, 1000);
      } else {
        const err = await res.json();
        setAddRowResult(`⚠ ${err.detail || 'Failed'}`);
      }
    } catch {
      setAddRowResult('⚠ Error');
    } finally {
      setAddingRow(false);
    }
  };

  const formatValue = (value: any): string => {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object' && value !== null) {
      if (value.value !== undefined) return formatValue(value.value);
      return JSON.stringify(value);
    }
    return String(value);
  };

  const totalItems = activeThread === 'identity' 
    ? identityRows.length 
    : activeThread === 'philosophy'
    ? philosophyRows.length
    : activeThread === 'log'
    ? logEvents.length
    : Object.values(genericModules).reduce((sum, arr) => sum + arr.length, 0);

  // Generic flat table renderer for identity-like threads
  const renderFlatTable = (rows: IdentityRow[], threadType: 'identity' | 'philosophy') => (
    <div className="identity-table-container">
      <div className="level-tabs">
        <button 
          className={`level-tab ${activeLevel === 1 ? 'active' : ''}`}
          onClick={() => setActiveLevel(1)}
        >
          L1 Quick
        </button>
        <button 
          className={`level-tab ${activeLevel === 2 ? 'active' : ''}`}
          onClick={() => setActiveLevel(2)}
        >
          L2 Standard
        </button>
        <button 
          className={`level-tab ${activeLevel === 3 ? 'active' : ''}`}
          onClick={() => setActiveLevel(3)}
        >
          L3 Full
        </button>
      </div>
      
      <table className="identity-table">
        <thead>
          <tr>
            <th className="col-key">Key</th>
            <th className="col-type">Type</th>
            <th className="col-value">
              {activeLevel === 1 ? 'L1 (Quick)' : activeLevel === 2 ? 'L2 (Standard)' : 'L3 (Full)'}
            </th>
            <th className="col-weight">Weight</th>
            <th className="col-actions"></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            editingKey === row.key ? (
              <tr key={row.key} className="editing-row">
                <td colSpan={5}>
                  <div className="edit-panel">
                    <div className="edit-header">
                      <span className="key-name">{row.key}</span>
                      <span className="key-desc">{row.metadata_desc}</span>
                    </div>
                    
                    <div className="edit-fields">
                      <label className="edit-field">
                        <span className="field-label">L1 (Quick)</span>
                        <input
                          type="text"
                          value={editForm.l1 || ''}
                          onChange={e => setEditForm({ ...editForm, l1: e.target.value })}
                          placeholder="Brief, ~10 tokens"
                        />
                      </label>
                      
                      <label className="edit-field">
                        <span className="field-label">L2 (Standard)</span>
                        <textarea
                          value={editForm.l2 || ''}
                          onChange={e => setEditForm({ ...editForm, l2: e.target.value })}
                          rows={2}
                          placeholder="Standard detail, ~30 tokens"
                        />
                      </label>
                      
                      <label className="edit-field">
                        <span className="field-label">L3 (Full)</span>
                        <textarea
                          value={editForm.l3 || ''}
                          onChange={e => setEditForm({ ...editForm, l3: e.target.value })}
                          rows={3}
                          placeholder="Full context, ~100 tokens"
                        />
                      </label>
                      
                      <label className="edit-field weight-field">
                        <span className="field-label">Weight: {((editForm.weight || 0.5) * 100).toFixed(0)}%</span>
                        <input
                          type="range"
                          min="0"
                          max="1"
                          step="0.05"
                          value={editForm.weight || 0.5}
                          onChange={e => setEditForm({ ...editForm, weight: parseFloat(e.target.value) })}
                        />
                      </label>
                    </div>
                    
                    <div className="edit-actions">
                      <button className="btn-cancel" onClick={cancelEditing} disabled={saving}>
                        Cancel
                      </button>
                      <button className="btn-save" onClick={saveEdit} disabled={saving}>
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                    </div>
                  </div>
                </td>
              </tr>
            ) : (
              <tr key={row.key}>
                <td className="col-key">
                  <span className="key-name">{row.key}</span>
                  <span className="key-desc">{row.metadata_desc}</span>
                </td>
                <td className="col-type">
                  <span className={`type-badge ${row.metadata_type}`}>{row.metadata_type}</span>
                </td>
                <td className="col-value">
                  {activeLevel === 1 ? row.l1 : activeLevel === 2 ? row.l2 : row.l3}
                </td>
                <td className="col-weight">
                  <div className="weight-bar">
                    <div className="weight-fill" style={{ width: `${row.weight * 100}%` }} />
                  </div>
                  <span className="weight-num">{(row.weight * 100).toFixed(0)}%</span>
                </td>
                <td className="col-actions">
                  <button className="btn-edit" onClick={() => startEditing(row)}>✏️</button>
                </td>
              </tr>
            )
          ))}
        </tbody>
      </table>

      {/* Add Row Section */}
      <div className="add-row-section">
        {!showAddRow ? (
          <button 
            className="btn-add-row" 
            onClick={() => {
              setNewRowType(threadType === 'philosophy' ? 'value' : 'user');
              setShowAddRow(true);
            }}
          >
            ➕ Add {threadType === 'philosophy' ? 'Value' : 'Fact'}
          </button>
        ) : (
          <div className="add-row-form">
            <div className="add-row-header">
              <h4>➕ New {threadType === 'philosophy' ? 'Philosophy Entry' : 'Identity Fact'}</h4>
              <button className="btn-close" onClick={resetAddRowForm}>✕</button>
            </div>
            
            <div className="add-row-fields">
              <div className="add-row-top">
                <label className="add-field">
                  <span>Key</span>
                  <input
                    type="text"
                    value={newRowKey}
                    onChange={e => setNewRowKey(e.target.value)}
                    placeholder="unique_key_name"
                  />
                </label>
                
                <label className="add-field">
                  <span>Type</span>
                  <select value={newRowType} onChange={e => setNewRowType(e.target.value)}>
                    {(threadType === 'philosophy' ? PHILOSOPHY_TYPES : IDENTITY_TYPES).map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </label>
                
                <label className="add-field">
                  <span>Description</span>
                  <input
                    type="text"
                    value={newRowDesc}
                    onChange={e => setNewRowDesc(e.target.value)}
                    placeholder="Optional description"
                  />
                </label>
              </div>
              
              <label className="add-field">
                <span>L1 (Quick)</span>
                <input
                  type="text"
                  value={newRowL1}
                  onChange={e => setNewRowL1(e.target.value)}
                  placeholder="Brief version (~10 tokens)"
                />
              </label>
              
              <label className="add-field">
                <span>L2 (Standard)</span>
                <textarea
                  value={newRowL2}
                  onChange={e => setNewRowL2(e.target.value)}
                  rows={2}
                  placeholder="Standard version (~30 tokens)"
                />
              </label>
              
              <label className="add-field">
                <span>L3 (Full)</span>
                <textarea
                  value={newRowL3}
                  onChange={e => setNewRowL3(e.target.value)}
                  rows={3}
                  placeholder="Full version (~100 tokens)"
                />
              </label>
              
              <label className="add-field weight-field">
                <span>Weight: {(newRowWeight * 100).toFixed(0)}%</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={newRowWeight}
                  onChange={e => setNewRowWeight(parseFloat(e.target.value))}
                />
              </label>
            </div>
            
            <div className="add-row-actions">
              <button className="btn-cancel" onClick={resetAddRowForm}>Cancel</button>
              <button className="btn-save" onClick={handleAddRow} disabled={addingRow}>
                {addingRow ? 'Adding...' : 'Add'}
              </button>
              {addRowResult && <span className="add-row-result">{addRowResult}</span>}
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // renderIdentityTable is now handled by ProfilesPage component
  const renderPhilosophyTable = () => renderFlatTable(philosophyRows, 'philosophy');

  const renderGenericView = () => (
    <div className="thread-data">
      {Object.entries(genericModules).map(([moduleName, rows]) => (
        <div key={moduleName} className="module-section">
          <h3 className="module-name">{moduleName}</h3>
          <div className="thread-rows">
            {rows.map((row, i) => (
              <div key={row.key || i} className="thread-row">
                <div className="row-header">
                  <span className="row-key">{row.key}</span>
                  <span className="row-level">L{row.level}</span>
                  <span className="row-weight">{(row.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="row-value">
                  {formatValue(row.data)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );

  const renderReadme = () => (
    <div className="readme-content">
      <pre className="readme-markdown">{readmeContent}</pre>
    </div>
  );

  const renderLogView = () => (
    <div className="log-view">
      {/* Controls row */}
      <div className="log-controls">
        <div className="log-control-group">
          <label>Show</label>
          <select value={logLimit} onChange={e => setLogLimit(Number(e.target.value))}>
            {[10, 20, 30, 50, 100].map(n => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </div>

        <div className="log-control-group">
          <label>Type</label>
          <select value={logTypeFilter} onChange={e => setLogTypeFilter(e.target.value)}>
            <option value="">All</option>
            {EVENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>

        <div className="log-control-group">
          <label>Source</label>
          <select value={logSourceFilter} onChange={e => setLogSourceFilter(e.target.value)}>
            <option value="">All</option>
            {EVENT_SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>

        <div className="log-control-group">
          <label>Sort</label>
          <select value={logSortField} onChange={e => setLogSortField(e.target.value as any)}>
            <option value="timestamp">Time</option>
            <option value="event_type">Type</option>
            <option value="source">Source</option>
          </select>
          <button className="sort-dir-btn" onClick={() => setLogSortAsc(!logSortAsc)}>
            {logSortAsc ? '↑' : '↓'}
          </button>
        </div>

        <button className="refresh-btn" onClick={fetchLogEvents} disabled={logLoading}>
          {logLoading ? '⟳' : '↻'}
        </button>
      </div>

      {/* Events list */}
      <div className="log-events-list">
        {logEvents.length === 0 ? (
          <p className="empty-state">No events found</p>
        ) : (
          logEvents.map((ev, idx) => (
            <div key={ev.id ?? idx} className={`log-event log-event-${ev.event_type}`}>
              <div className="log-event-header">
                <span className="log-event-type">{ev.event_type}</span>
                <span className="log-event-source">{ev.source}</span>
                <span className="log-event-time">
                  {new Date(ev.timestamp).toLocaleString()}
                </span>
              </div>
              <div className="log-event-data">{ev.message}</div>
            </div>
          ))
        )}
      </div>

      {/* Add event form */}
      <div className="add-event-section">
        <h4>➕ Add Event</h4>
        <div className="add-event-form">
          <select value={newEventType} onChange={e => setNewEventType(e.target.value)}>
            {EVENT_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={newEventSource} onChange={e => setNewEventSource(e.target.value)}>
            {EVENT_SOURCES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input
            type="text"
            placeholder="What happened?"
            value={newEventMessage}
            onChange={e => setNewEventMessage(e.target.value)}
          />
          <button onClick={handleAddEvent} disabled={addingEvent}>
            {addingEvent ? '…' : 'Add'}
          </button>
          {addEventResult && <span className="add-event-result">{addEventResult}</span>}
        </div>
      </div>
    </div>
  );

  return (
    <div className="page-wrapper threads-page">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>🧵 Threads</h1>
      </div>

      <nav className="thread-nav">
        {loading ? (
          <div className="muted">Loading...</div>
        ) : (
          Object.values(threads).map(t => (
            <button
              key={t.name}
              className={`thread-tab ${activeThread === t.name ? 'active' : ''} ${t.status}`}
              onClick={() => setActiveThread(t.name)}
            >
              <span className="thread-icon">{THREAD_ICONS[t.name] || '🧵'}</span>
              <span className="thread-name">{t.name}</span>
              <span className={`thread-status-dot ${t.status}`} />
            </button>
          ))
        )}
      </nav>

      <div className="threads-layout">
        <main className="thread-content">
          {!activeThread ? (
            <div className="empty-state">Select a thread to view</div>
          ) : dataLoading ? (
            <div className="empty-state">Loading {activeThread}...</div>
          ) : DOC_THREADS.has(activeThread) && readmeContent ? (
            <>
              <div className="thread-data-header">
                <h2>{THREAD_ICONS[activeThread]} {activeThread}</h2>
                <span className="item-count">Documentation</span>
              </div>
              {renderReadme()}
            </>
          ) : totalItems === 0 && !DOC_THREADS.has(activeThread) && activeThread !== 'identity' && activeThread !== 'linking_core' ? (
            <div className="empty-state">
              <p>No data in {activeThread}</p>
              <p className="muted">{threads[activeThread]?.message}</p>
            </div>
          ) : (
            <>
              {activeThread === 'identity' ? (
                <div style={{ height: '100%', width: '100%' }}>
                  <ProfilesPage />
                </div>
              ) : activeThread === 'linking_core' ? (
                <div style={{ height: '100%', width: '100%', minHeight: '600px' }}>
                  <ConceptGraph3D mode="ambient" />
                </div>
              ) : (
                <>
                  <div className="thread-data-header">
                    <h2>{THREAD_ICONS[activeThread]} {activeThread}</h2>
                    <span className="item-count">{totalItems} items</span>
                  </div>
                  
                  {activeThread === 'philosophy'
                    ? renderPhilosophyTable()
                    : activeThread === 'log' 
                    ? renderLogView() 
                    : activeThread === 'form'
                    ? <ToolDashboard />
                    : activeThread === 'reflex'
                    ? <ReflexDashboard />
                    : renderGenericView()}
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
};
