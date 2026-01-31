import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './ThreadsPage.css';
import { ToolDashboard } from '../form';
import { ReflexDashboard } from '../reflex';
import IdentityProfilesPage from '../identity/pages/ProfilesPage';
import PhilosophyProfilesPage from '../philosophy/pages/ProfilesPage';
import { ConceptGraph3D } from '../linking_core';

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

export const ThreadsPage = () => {
  const [threads, setThreads] = useState<Record<string, ThreadHealth>>({});
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [identityRows, setIdentityRows] = useState<IdentityRow[]>([]);
  const [philosophyRows, setPhilosophyRows] = useState<PhilosophyRow[]>([]);
  const [genericModules, setGenericModules] = useState<Record<string, GenericRow[]>>({});
  const [readmeContent, setReadmeContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);

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

  const fetchIdentityCount = () => {
    fetch('http://localhost:8000/api/identity/table')
      .then(res => res.json())
      .then(data => {
        setIdentityRows(data.rows || []);
        setDataLoading(false);
      })
      .catch(() => {
        setIdentityRows([]);
        setDataLoading(false);
      });
  };

  const fetchPhilosophyData = () => {
    fetch('http://localhost:8000/api/philosophy/table')
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

    fetch(`http://localhost:8000/api/log/events?${params}`)
      .then(res => res.json())
      .then((response) => {
        const data: LogEvent[] = response.events || [];
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
      const res = await fetch('http://localhost:8000/api/log/events', {
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
    fetch('http://localhost:8000/api/subconscious/threads')
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
    setReadmeContent('');
    
    // Documentation threads - fetch README
    if (DOC_THREADS.has(activeThread)) {
      fetch(`http://localhost:8000/api/${activeThread}/readme`)
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
      fetchIdentityCount();
    } else if (activeThread === 'philosophy') {
      fetchPhilosophyData();
    } else if (activeThread === 'log') {
      fetchLogEvents();
      setDataLoading(false);
    } else if (activeThread === 'form' || activeThread === 'reflex' || activeThread === 'linking_core') {
      // These threads have their own dashboards that fetch their own data
      setDataLoading(false);
    } else {
      fetch(`http://localhost:8000/api/${activeThread}/introspect?level=2`)
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
          ) : totalItems === 0 && !DOC_THREADS.has(activeThread) && activeThread !== 'identity' && activeThread !== 'philosophy' && activeThread !== 'linking_core' && activeThread !== 'form' && activeThread !== 'reflex' ? (
            <div className="empty-state">
              <p>No data in {activeThread}</p>
              <p className="muted">{threads[activeThread]?.message}</p>
            </div>
          ) : (
            <>
              {activeThread === 'identity' ? (
                <div style={{ height: '100%', width: '100%' }}>
                  <IdentityProfilesPage />
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
                    ? <PhilosophyProfilesPage />
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
