import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './LogDashboard.css';

/* ── Types ── */
interface LogTableInfo {
  name: string;
  count: number;
  icon: string;
  label: string;
  columns: string[];
}

interface LogRow {
  [key: string]: unknown;
}

/* ── Constants ── */
const CORE_TABLES = ['unified_events', 'log_system', 'log_server', 'log_function_calls'];
const PAGE_SIZE = 50;

/* ── API helpers ── */
async function fetchTables(): Promise<LogTableInfo[]> {
  const r = await fetch('/api/log/tables');
  const d = await r.json();
  return d.tables || [];
}

async function fetchTableData(table: LogTableInfo, _page: number, search: string, filters: Record<string, string>): Promise<{ rows: LogRow[]; total: number }> {
  const limit = PAGE_SIZE;

  if (table.name === 'unified_events') {
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters.event_type) params.set('event_type', filters.event_type);
    if (filters.source) params.set('source', filters.source);
    if (search) params.set('q', search);
    // Use search endpoint if searching, otherwise events
    if (search) {
      const r = await fetch(`/api/log/events/search?${params}`);
      const d = await r.json();
      return { rows: d.events || d.results || [], total: (d.events || d.results || []).length };
    }
    const r = await fetch(`/api/log/events?${params}`);
    const d = await r.json();
    return { rows: d.events || [], total: d.count || d.events?.length || 0 };
  }

  if (table.name === 'log_system') {
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters.level) params.set('level', filters.level);
    if (filters.source) params.set('source', filters.source);
    const r = await fetch(`/api/log/daemon?${params}`);
    const d = await r.json();
    return { rows: d.logs || [], total: (d.logs || []).length };
  }

  if (table.name === 'log_server') {
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters.method) params.set('method', filters.method);
    if (filters.level) params.set('level', filters.level);
    const r = await fetch(`/api/log/server?${params}`);
    const d = await r.json();
    return { rows: d.logs || [], total: (d.logs || []).length };
  }

  if (table.name === 'log_function_calls') {
    const params = new URLSearchParams({ limit: String(limit) });
    if (filters.module) params.set('module', filters.module);
    if (filters.function_name) params.set('function_name', filters.function_name);
    const r = await fetch(`/api/log/functions?${params}`);
    const d = await r.json();
    return { rows: d.calls || [], total: d.count || (d.calls || []).length };
  }

  // Dynamic module tables
  const moduleName = table.name.replace(/^log_/, '');
  const params = new URLSearchParams({ limit: String(limit) });
  const r = await fetch(`/api/log/modules/${moduleName}?${params}`);
  const d = await r.json();
  return { rows: d.entries || [], total: (d.entries || []).length };
}

/* ── Main Component ── */
export function LogDashboard() {
  const [tables, setTables] = useState<LogTableInfo[]>([]);
  const [selected, setSelected] = useState<LogTableInfo | null>(null);
  const [rows, setRows] = useState<LogRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [search, setSearch] = useState('');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  // Load table list
  useEffect(() => {
    fetchTables().then(t => {
      setTables(t);
      if (t.length > 0) setSelected(t[0]);
    });
  }, []);

  // Load data when selection/page/filters change
  const loadData = useCallback(async () => {
    if (!selected) return;
    setLoading(true);
    try {
      const { rows: r, total: t } = await fetchTableData(selected, page, search, filters);
      setRows(r);
      setTotal(t);
    } catch { setRows([]); setTotal(0); }
    setLoading(false);
  }, [selected, page, search, filters]);

  useEffect(() => { loadData(); }, [loadData]);

  const coreTables = tables.filter(t => CORE_TABLES.includes(t.name));
  const moduleTables = tables.filter(t => !CORE_TABLES.includes(t.name));

  // Determine visible columns for current table
  const columns = selected?.columns || [];

  // Format cell values
  const formatCell = (value: unknown, col: string): string => {
    if (value === null || value === undefined) return '—';
    if (col === 'metadata_json' || col === 'data_json' || col === 'data') {
      if (typeof value === 'object') return JSON.stringify(value).slice(0, 120);
      return String(value).slice(0, 120);
    }
    if (col === 'timestamp' || col === 'created_at') {
      try { return new Date(String(value)).toLocaleString(); } catch { return String(value); }
    }
    if (col === 'duration_ms') return `${Number(value).toFixed(1)}ms`;
    if (col === 'success') return value ? '✅' : '❌';
    return String(value);
  };

  const badgeClass = (value: unknown, col: string): string => {
    if (col === 'level') {
      const v = String(value).toLowerCase();
      if (v === 'error' || v === 'critical') return 'badge badge-error';
      if (v === 'warning') return 'badge badge-warn';
      if (v === 'info') return 'badge badge-info';
      return 'badge badge-muted';
    }
    if (col === 'status_code') {
      const n = Number(value);
      if (n >= 500) return 'badge badge-error';
      if (n >= 400) return 'badge badge-warn';
      if (n >= 200 && n < 300) return 'badge badge-success';
      return 'badge badge-muted';
    }
    if (col === 'event_type') return 'badge badge-info';
    return '';
  };

  // Get filter options per table
  const renderFilters = () => {
    if (!selected) return null;
    const name = selected.name;

    const setF = (k: string, v: string) => {
      setFilters(prev => ({ ...prev, [k]: v }));
      setPage(0);
    };

    if (name === 'unified_events') return (
      <>
        <select value={filters.event_type || ''} onChange={e => setF('event_type', e.target.value)}>
          <option value="">All types</option>
          {['convo', 'system', 'user_action', 'file', 'memory', 'activation'].map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <select value={filters.source || ''} onChange={e => setF('source', e.target.value)}>
          <option value="">All sources</option>
          {['system', 'local', 'agent', 'daemon', 'web_public'].map(s => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </>
    );

    if (name === 'log_system') return (
      <>
        <select value={filters.level || ''} onChange={e => setF('level', e.target.value)}>
          <option value="">All levels</option>
          {['debug', 'info', 'warning', 'error', 'critical'].map(l => (
            <option key={l} value={l}>{l}</option>
          ))}
        </select>
      </>
    );

    if (name === 'log_server') return (
      <>
        <select value={filters.method || ''} onChange={e => setF('method', e.target.value)}>
          <option value="">All methods</option>
          {['GET', 'POST', 'PUT', 'DELETE'].map(m => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </>
    );

    if (name === 'log_function_calls') return (
      <input
        placeholder="Filter by module..."
        value={filters.module || ''}
        onChange={e => setF('module', e.target.value)}
      />
    );

    return null;
  };

  return (
    <div className="log-dashboard">
      {/* ── Sidebar ── */}
      <nav className="log-sidebar">
        <div className="log-sidebar-header">
          <span className="logo">📋</span>
          <h3>Logs</h3>
        </div>
        <div className="log-sidebar-links">
          {coreTables.length > 0 && <div className="log-sidebar-section">System</div>}
          {coreTables.map(t => (
            <button
              key={t.name}
              className={`log-table-btn ${selected?.name === t.name ? 'active' : ''}`}
              onClick={() => { setSelected(t); setPage(0); setSearch(''); setFilters({}); setExpandedRow(null); }}
            >
              <span className="icon">{t.icon}</span>
              <span className="name">{t.label}</span>
              <span className="count">{t.count.toLocaleString()}</span>
            </button>
          ))}
          {moduleTables.length > 0 && <div className="log-sidebar-section">Modules</div>}
          {moduleTables.map(t => (
            <button
              key={t.name}
              className={`log-table-btn ${selected?.name === t.name ? 'active' : ''}`}
              onClick={() => { setSelected(t); setPage(0); setSearch(''); setFilters({}); setExpandedRow(null); }}
            >
              <span className="icon">{t.icon}</span>
              <span className="name">{t.label}</span>
              <span className="count">{t.count.toLocaleString()}</span>
            </button>
          ))}
        </div>
        <div className="log-sidebar-footer">
          <Link to="/">← Back to App</Link>
        </div>
      </nav>

      {/* ── Main Area ── */}
      <div className="log-main">
        {selected ? (
          <>
            <h2>{selected.icon} {selected.label}</h2>
            <p className="subtitle">{selected.count.toLocaleString()} entries in {selected.name}</p>

            {/* Filters */}
            <div className="log-filters">
              {selected.name === 'unified_events' && (
                <input
                  placeholder="Search events..."
                  value={search}
                  onChange={e => { setSearch(e.target.value); setPage(0); }}
                />
              )}
              {renderFilters()}
              <button onClick={loadData}>↻ Refresh</button>
            </div>

            {/* Table */}
            {loading ? (
              <div className="log-empty"><div className="icon">⏳</div><p>Loading...</p></div>
            ) : rows.length === 0 ? (
              <div className="log-empty"><div className="icon">📭</div><p>No entries found</p></div>
            ) : (
              <>
                <div className="log-table-wrapper">
                  <table className="log-table">
                    <thead>
                      <tr>
                        {columns.map(col => (
                          <th key={col}>{col.replace(/_/g, ' ')}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((row, i) => (
                        <>
                          <tr key={i} onClick={() => setExpandedRow(expandedRow === i ? null : i)} style={{ cursor: 'pointer' }}>
                            {columns.map(col => {
                              const val = row[col];
                              const bc = badgeClass(val, col);
                              return (
                                <td key={col}>
                                  {bc ? <span className={bc}>{formatCell(val, col)}</span> : formatCell(val, col)}
                                </td>
                              );
                            })}
                          </tr>
                          {expandedRow === i && (
                            <tr key={`${i}-exp`}>
                              <td colSpan={columns.length} className="log-expanded">
                                {JSON.stringify(row, null, 2)}
                              </td>
                            </tr>
                          )}
                        </>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="log-pagination">
                  <span>Showing {rows.length} of {total} entries</span>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
                    <button disabled={rows.length < PAGE_SIZE} onClick={() => setPage(p => p + 1)}>Next →</button>
                  </div>
                </div>
              </>
            )}
          </>
        ) : (
          <div className="log-empty"><div className="icon">📋</div><p>Select a log table from the sidebar</p></div>
        )}
      </div>
    </div>
  );
}
