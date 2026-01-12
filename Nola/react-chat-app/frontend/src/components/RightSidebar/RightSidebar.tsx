import React from 'react';
import { useIntrospection } from '../../hooks/useIntrospection';
import { introspectionService } from '../../services/introspectionService';
import { CONTEXT_LEVELS, STATUS_COLORS } from '../../types/introspection';
import type { LogEvent } from '../../types/introspection';
import './RightSidebar.css';

export const RightSidebar: React.FC = () => {
  const { data, isLoading, error, level, setLevel, refresh } = useIntrospection({
    level: 2,
    pollInterval: 2000,
    autoStart: true
  });

  const [recentLimit, setRecentLimit] = React.useState<number>(20);
  const [recentEvents, setRecentEvents] = React.useState<LogEvent[]>([]);
  const [eventsLoading, setEventsLoading] = React.useState<boolean>(false);
  const [eventsError, setEventsError] = React.useState<string | null>(null);

  const [newEventType, setNewEventType] = React.useState<string>('user_action');
  const [newEventSource, setNewEventSource] = React.useState<string>('local');
  const [newEventMessage, setNewEventMessage] = React.useState<string>('');
  const [isAddingEvent, setIsAddingEvent] = React.useState<boolean>(false);
  const [addEventResult, setAddEventResult] = React.useState<string | null>(null);

  // Consolidation state
  const [isConsolidating, setIsConsolidating] = React.useState(false);
  const [consolidateResult, setConsolidateResult] = React.useState<string | null>(null);

  const loadRecentEvents = React.useCallback(async (limit: number = recentLimit) => {
    setEventsLoading(true);
    setEventsError(null);
    try {
      const events = await introspectionService.getRecentEvents(limit);
      setRecentEvents(events);
    } catch (err) {
      setEventsError('Failed to load events');
    } finally {
      setEventsLoading(false);
    }
  }, [recentLimit]);

  React.useEffect(() => {
    loadRecentEvents(recentLimit);
  }, [recentLimit, loadRecentEvents]);

  const handleConsolidate = async () => {
    setIsConsolidating(true);
    setConsolidateResult(null);
    try {
      const result = await introspectionService.consolidateMemory(false);
      if (result.success) {
        if (result.facts_processed === 0) {
          setConsolidateResult('✓ No pending facts');
        } else {
          setConsolidateResult(`✓ ${result.promoted_l2} L2, ${result.promoted_l3} L3 promoted`);
        }
      } else {
        setConsolidateResult(`⚠ ${result.message}`);
      }
      // Refresh to show updated stats
      setTimeout(refresh, 500);
    } catch (err) {
      setConsolidateResult('⚠ Failed');
    } finally {
      setIsConsolidating(false);
      // Clear message after 3 seconds
      setTimeout(() => setConsolidateResult(null), 3000);
    }
  };

  const renderStatusBadge = (status: string) => {
    const color = STATUS_COLORS[status as keyof typeof STATUS_COLORS] || STATUS_COLORS.unknown;
    return (
      <span 
        className="status-badge"
        style={{ backgroundColor: color }}
      >
        {status}
      </span>
    );
  };

  const renderContextFacts = () => {
    if (!data?.context?.facts || data.context.facts.length === 0) {
      return <p className="empty-text">No context assembled</p>;
    }

    return (
      <ul className="context-facts">
        {data.context.facts.slice(0, 10).map((fact, idx) => (
          <li key={idx}>{fact}</li>
        ))}
        {data.context.facts.length > 10 && (
          <li className="more-facts">+{data.context.facts.length - 10} more facts...</li>
        )}
      </ul>
    );
  };

  const renderRecentEvents = (events: LogEvent[]) => {
    if (events.length === 0) {
      return <p className="empty-text">No recent events</p>;
    }

    return (
      <div className="events-list">
        {events.slice(0, 5).map((event, idx) => (
          <div key={idx} className={`event-item event-${event.level.toLowerCase()}`}>
            <span className="event-type">{event.event_type}</span>
            <span className="event-source">{event.source}</span>
            {event.message && <p className="event-message">{event.message}</p>}
          </div>
        ))}
      </div>
    );
  };

  const renderThreadSnapshot = () => {
    // threads is at top-level, not inside context
    const threads = data?.threads || {};
    const entries = Object.entries(threads);
    if (entries.length === 0) return <p className="empty-text">No threads registered</p>;

    return (
      <div className="thread-chip-list">
        {entries.map(([name, info]: [string, any]) => (
          <div key={name} className={`thread-chip thread-${info.status || 'unknown'}`}>
            <span className="thread-chip-name">{name}</span>
            <span className={`thread-chip-status status-${info.status || 'unknown'}`}>
              {info.status || '?'}
            </span>
            {info.details?.total !== undefined && (
              <span className="thread-chip-count">{info.details.total} items</span>
            )}
          </div>
        ))}
      </div>
    );
  };

  const handleAddEvent = async () => {
    if (!newEventMessage.trim()) {
      setAddEventResult('Enter a message to log');
      return;
    }
    setIsAddingEvent(true);
    setAddEventResult(null);
    try {
      await introspectionService.addEvent({
        event_type: newEventType,
        data: newEventMessage.trim(),
        source: newEventSource || 'local'
      });
      setAddEventResult('✓ Event added');
      setNewEventMessage('');
      loadRecentEvents();
    } catch (err) {
      setAddEventResult('⚠ Failed to add');
    } finally {
      setIsAddingEvent(false);
      setTimeout(() => setAddEventResult(null), 2500);
    }
  };

  const renderTempMemoryFacts = () => {
    // temp_memory thread is at data.threads.temp_memory
    const tmThread = (data?.threads as any)?.temp_memory;
    const details = tmThread?.details;
    
    if (!details || details.pending_facts === 0) {
      return <p className="empty-text">No temp memory facts yet</p>;
    }
    
    return (
      <div className="temp-memory-summary">
        <div className="tm-stat">
          <span className="tm-label">Pending:</span>
          <span className="tm-value">{details.pending ?? 0}</span>
        </div>
        <div className="tm-stat">
          <span className="tm-label">Consolidated:</span>
          <span className="tm-value">{details.consolidated ?? 0}</span>
        </div>
        <div className="tm-stat">
          <span className="tm-label">Total:</span>
          <span className="tm-value">{details.total ?? 0}</span>
        </div>
        <div className="tm-stat">
          <span className="tm-label">Sessions:</span>
          <span className="tm-value">{details.sessions ?? 0}</span>
        </div>
      </div>
    );
  };

  if (error) {
    return (
      <div className="right-sidebar">
        <div className="right-sidebar-header">
          <h3>🔧 Introspection</h3>
        </div>
        <div className="right-sidebar-content">
          <div className="error-section">
            <p className="error-text">⚠️ {error}</p>
            <button onClick={refresh} className="retry-button">Retry</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="right-sidebar">
      <div className="right-sidebar-header">
        <h3>🧠 Nola State</h3>
        <div className="header-status">
          {data && renderStatusBadge(data.status)}
          {isLoading && <span className="loading-indicator">⟳</span>}
          <button className="refresh-button" onClick={refresh} title="Refresh now">↻</button>
        </div>
      </div>
      
      <div className="right-sidebar-content">
        {/* Context Level Selector */}
        <section className="sidebar-section">
          <h4>📊 Context Level</h4>
          <div className="level-selector">
            {[1, 2, 3].map((l) => (
              <button
                key={l}
                className={`level-button ${level === l ? 'active' : ''}`}
                onClick={() => setLevel(l)}
                title={CONTEXT_LEVELS[l as keyof typeof CONTEXT_LEVELS].description}
              >
                {CONTEXT_LEVELS[l as keyof typeof CONTEXT_LEVELS].icon} L{l}
              </button>
            ))}
          </div>
          <p className="level-description">
            {CONTEXT_LEVELS[level as keyof typeof CONTEXT_LEVELS].description}
          </p>
        </section>

        {/* State snapshot */}
        <section className="sidebar-section">
          <h4>🪞 State Snapshot</h4>
          <div className="state-meta">
            <small>Updated: {data?.context?.timestamp ? new Date(data.context.timestamp).toLocaleTimeString() : '—'}</small>
            <small>Threads: {data?.context?.thread_count ?? 0}</small>
          </div>
          {renderThreadSnapshot()}
        </section>

        {/* Temp Memory (in-flight facts) */}
        <section className="sidebar-section">
          <h4>🧩 Temp Memory</h4>
          {renderTempMemoryFacts()}
          <button 
            className="consolidate-button"
            onClick={handleConsolidate}
            disabled={isConsolidating}
            title="Process pending facts and promote to long-term memory"
          >
            {isConsolidating ? '⟳ Processing...' : '🔄 Consolidate Now'}
          </button>
          {consolidateResult && (
            <span className="consolidate-result">{consolidateResult}</span>
          )}
        </section>

        <section className="sidebar-section">
          <h4>💭 Context ({data?.context?.fact_count || 0} facts)</h4>
          {renderContextFacts()}
        </section>

        <section className="sidebar-section">
          <h4>📜 Recent Events</h4>
          <div className="events-controls">
            <label className="control-label" htmlFor="events-limit">Show</label>
            <select
              id="events-limit"
              value={recentLimit}
              onChange={(e) => setRecentLimit(Number(e.target.value))}
            >
              {[10, 20, 30, 50, 100].map((opt) => (
                <option key={opt} value={opt}>{opt} events</option>
              ))}
            </select>
            <button className="refresh-button" onClick={() => loadRecentEvents(recentLimit)} disabled={eventsLoading}>
              {eventsLoading ? '⟳' : '↻'}
            </button>
          </div>
          {eventsError && <p className="error-text">{eventsError}</p>}
          {renderRecentEvents(recentEvents)}
        </section>

        <section className="sidebar-section">
          <h4>➕ Add Event</h4>
          <div className="add-event-form">
            <div className="form-row">
              <label>Type</label>
              <select value={newEventType} onChange={(e) => setNewEventType(e.target.value)}>
                <option value="convo">convo</option>
                <option value="system">system</option>
                <option value="user_action">user_action</option>
                <option value="memory">memory</option>
                <option value="activation">activation</option>
                <option value="file">file</option>
              </select>
            </div>
            <div className="form-row">
              <label>Source</label>
              <select value={newEventSource} onChange={(e) => setNewEventSource(e.target.value)}>
                <option value="local">local</option>
                <option value="agent">agent</option>
                <option value="daemon">daemon</option>
                <option value="web_public">web_public</option>
              </select>
            </div>
            <div className="form-row">
              <label>Message</label>
              <textarea
                value={newEventMessage}
                onChange={(e) => setNewEventMessage(e.target.value)}
                placeholder="What happened?"
                rows={3}
              />
            </div>
            <button className="primary-button" onClick={handleAddEvent} disabled={isAddingEvent}>
              {isAddingEvent ? 'Logging…' : 'Add Event'}
            </button>
            {addEventResult && <small className="helper-text">{addEventResult}</small>}
          </div>
        </section>

        {/* Session Info */}
        {data?.session_id && (
          <section className="sidebar-section session-info">
            <small>Session: {data.session_id}</small>
            {data.wake_time && (
              <small>Awake since: {new Date(data.wake_time).toLocaleTimeString()}</small>
            )}
          </section>
        )}
      </div>
    </div>
  );
};
