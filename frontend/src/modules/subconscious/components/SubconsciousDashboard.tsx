/**
 * Subconscious Dashboard
 * ======================
 * Monitors background loops, temp_facts, and memory consolidation.
 * 
 * Full visibility into:
 * - Background loop status + editable intervals + pause/resume
 * - Extraction model selection
 * - Unread conversation queue
 * - Temp fact review queue with approve/reject/edit/delete
 * - Potentiation stats (SHORT vs LONG memory)
 * - Export readiness for finetuning
 */

import { useState, useEffect, useCallback } from 'react';
import './SubconsciousDashboard.css';

const API = 'http://localhost:8000/api/subconscious';

interface LoopStats {
  name: string;
  status: string;
  interval: number;
  last_run: string | null;
  run_count: number;
  error_count: number;
  consecutive_errors: number;
  model?: string;
  unprocessed_turns?: number;
  last_processed_turn_id?: number | null;
}

interface TempFact {
  id: number;
  text: string;
  status: string;
  source: string;
  session_id: string;
  confidence_score: number | null;
  hier_key: string | null;
  timestamp: string;
}

interface PotentiationStats {
  SHORT: { count: number; avg_strength: number; avg_fires: number };
  LONG: { count: number; avg_strength: number; avg_fires: number };
}

interface QueueInfo {
  unprocessed: number;
  total_turns: number;
  last_processed_turn_id: number | null;
  model: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  running: '#22c55e',
  stopped: '#6b7280',
  paused: '#f59e0b',
  error: '#ef4444'
};

const FACT_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: '#e5e7eb', text: '#4b5563' },
  pending_review: { bg: '#fef3c7', text: '#92400e' },
  approved: { bg: '#d1fae5', text: '#065f46' },
  consolidated: { bg: '#ede9fe', text: '#5b21b6' },
  rejected: { bg: '#fee2e2', text: '#991b1b' },
};

export default function SubconsciousDashboard() {
  const [loops, setLoops] = useState<LoopStats[]>([]);
  const [tempFacts, setTempFacts] = useState<TempFact[]>([]);
  const [factsByStatus, setFactsByStatus] = useState<Record<string, number>>({});
  const [potentiation, setPotentiation] = useState<PotentiationStats | null>(null);
  const [queue, setQueue] = useState<QueueInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<string | null>(null);

  // Editing states
  const [editingInterval, setEditingInterval] = useState<string | null>(null);
  const [intervalValue, setIntervalValue] = useState('');
  const [editingFact, setEditingFact] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [modelInput, setModelInput] = useState('');
  const [showModelInput, setShowModelInput] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [loopsRes, factsRes, potRes, queueRes] = await Promise.all([
        fetch(`${API}/loops`),
        fetch(`${API}/temp-facts`),
        fetch(`${API}/potentiation`),
        fetch(`${API}/queue`),
      ]);

      if (loopsRes.ok) {
        const data = await loopsRes.json();
        setLoops(data.loops || []);
      }

      if (factsRes.ok) {
        const data = await factsRes.json();
        setTempFacts(data.recent || []);
        setFactsByStatus(data.by_status || {});
      }

      if (potRes.ok) {
        const data = await potRes.json();
        setPotentiation(data.potentiation || null);
      }

      if (queueRes.ok) {
        const data = await queueRes.json();
        setQueue(data);
        if (data.model) setModelInput(data.model);
      }
    } catch (err) {
      console.error('Failed to fetch subconscious data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // ── Fact actions ──────────────────────────────────────────

  const approveFact = async (factId: number) => {
    await fetch(`${API}/temp-facts/${factId}/approve`, { method: 'POST' });
    fetchData();
  };

  const rejectFact = async (factId: number) => {
    await fetch(`${API}/temp-facts/${factId}/reject`, { method: 'POST' });
    fetchData();
  };

  const deleteFact = async (factId: number) => {
    await fetch(`${API}/temp-facts/${factId}`, { method: 'DELETE' });
    fetchData();
  };

  const saveFact = async (factId: number) => {
    if (!editText.trim()) return;
    await fetch(`${API}/temp-facts/${factId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: editText }),
    });
    setEditingFact(null);
    setEditText('');
    fetchData();
  };

  const approveAll = async () => {
    await fetch(`${API}/temp-facts/approve-all`, { method: 'POST' });
    fetchData();
  };

  const rejectAll = async () => {
    await fetch(`${API}/temp-facts/reject-all`, { method: 'POST' });
    fetchData();
  };

  // ── Loop actions ──────────────────────────────────────────

  const saveInterval = async (loopName: string) => {
    const val = parseFloat(intervalValue);
    if (isNaN(val) || val < 5) return;
    await fetch(`${API}/loops/${loopName}/interval`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval: val }),
    });
    setEditingInterval(null);
    fetchData();
  };

  const toggleLoop = async (loopName: string, currentStatus: string) => {
    const action = currentStatus === 'paused' ? 'resume' : 'pause';
    await fetch(`${API}/loops/${loopName}/${action}`, { method: 'POST' });
    fetchData();
  };

  const saveModel = async () => {
    if (!modelInput.trim()) return;
    await fetch(`${API}/loops/memory/model`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: modelInput }),
    });
    setShowModelInput(false);
    fetchData();
  };

  // ── Consolidation/Export ──────────────────────────────────

  const handleConsolidate = async () => {
    try {
      const res = await fetch(`${API}/consolidate`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setExportResult(`Consolidated: ${data.result?.promoted || 0} links promoted`);
        fetchData();
      }
    } catch { setExportResult('Consolidation failed'); }
    setTimeout(() => setExportResult(null), 3000);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('http://localhost:8000/api/finetune/export', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const total = data.results?.combined?.total_examples || 0;
        setExportResult(`Exported ${total} training examples`);
      }
    } catch { setExportResult('Export failed'); }
    finally {
      setExporting(false);
      setTimeout(() => setExportResult(null), 5000);
    }
  };

  if (loading) {
    return <div className="subconscious-dashboard loading">Loading subconscious...</div>;
  }

  const totalPending = Object.values(factsByStatus).reduce((a, b) => a + b, 0);
  const reviewCount = (factsByStatus['pending'] || 0) + (factsByStatus['pending_review'] || 0);
  const longCount = potentiation?.LONG?.count || 0;
  const shortCount = potentiation?.SHORT?.count || 0;

  return (
    <div className="subconscious-dashboard">
      {/* Header Stats */}
      <div className="subconscious-stats">
        <div className="stat-card">
          <span className="stat-value">{loops.length}</span>
          <span className="stat-label">Loops</span>
        </div>
        <div className={`stat-card ${(queue?.unprocessed || 0) > 0 ? 'highlight' : ''}`}>
          <span className="stat-value">{queue?.unprocessed || 0}</span>
          <span className="stat-label">Unread Turns</span>
        </div>
        <div className={`stat-card ${reviewCount > 0 ? 'highlight' : ''}`}>
          <span className="stat-value">{reviewCount}</span>
          <span className="stat-label">Needs Review</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{totalPending}</span>
          <span className="stat-label">Total Pending</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{shortCount}</span>
          <span className="stat-label">SHORT</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{longCount}</span>
          <span className="stat-label">LONG</span>
        </div>
      </div>

      {/* Actions Row */}
      <div className="subconscious-actions">
        <button onClick={handleConsolidate} className="action-btn consolidate">
          🧠 Consolidate
        </button>
        <button onClick={handleExport} disabled={exporting} className="action-btn export">
          {exporting ? '⏳ Exporting...' : '📦 Export'}
        </button>
        {exportResult && <span className="action-result">{exportResult}</span>}
      </div>

      <div className="subconscious-layout">
        {/* ── Left Column: Loops + Queue ── */}
        <div className="panel loops-panel">
          <h3>🔄 Background Loops</h3>

          {/* Model selector */}
          <div className="model-section">
            <span className="model-label">Extraction model:</span>
            {showModelInput ? (
              <div className="model-edit">
                <input
                  type="text"
                  value={modelInput}
                  onChange={e => setModelInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && saveModel()}
                  className="model-input"
                  placeholder="e.g. qwen2.5:7b"
                  autoFocus
                />
                <button onClick={saveModel} className="btn-sm save">✓</button>
                <button onClick={() => setShowModelInput(false)} className="btn-sm cancel">✕</button>
              </div>
            ) : (
              <button className="model-value" onClick={() => setShowModelInput(true)}>
                {queue?.model || 'default'} ✎
              </button>
            )}
          </div>

          {/* Unread queue */}
          {(queue?.unprocessed || 0) > 0 && (
            <div className="queue-bar">
              <div className="queue-progress">
                <div
                  className="queue-fill"
                  style={{
                    width: `${Math.min(100, ((queue!.total_turns - queue!.unprocessed) / (queue!.total_turns || 1)) * 100)}%`
                  }}
                />
              </div>
              <span className="queue-text">
                {queue!.unprocessed} conversation turns waiting to be read
              </span>
            </div>
          )}

          {/* Loop cards */}
          <div className="loops-list">
            {loops.map(loop => (
              <div key={loop.name} className="loop-item">
                <div className="loop-header">
                  <span
                    className="loop-status-dot"
                    style={{ background: STATUS_COLORS[loop.status] || '#6b7280' }}
                  />
                  <span className="loop-name">{loop.name}</span>
                  <div className="loop-controls">
                    {(loop.status === 'running' || loop.status === 'paused') && (
                      <button
                        className="btn-sm"
                        onClick={() => toggleLoop(loop.name, loop.status)}
                        title={loop.status === 'paused' ? 'Resume' : 'Pause'}
                      >
                        {loop.status === 'paused' ? '▶' : '⏸'}
                      </button>
                    )}
                  </div>
                </div>
                <div className="loop-details">
                  {editingInterval === loop.name ? (
                    <div className="interval-edit">
                      <input
                        type="number"
                        min="5"
                        value={intervalValue}
                        onChange={e => setIntervalValue(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && saveInterval(loop.name)}
                        className="interval-input"
                        autoFocus
                      />
                      <span className="interval-unit">s</span>
                      <button onClick={() => saveInterval(loop.name)} className="btn-sm save">✓</button>
                      <button onClick={() => setEditingInterval(null)} className="btn-sm cancel">✕</button>
                    </div>
                  ) : (
                    <span
                      className="interval-click"
                      onClick={() => { setEditingInterval(loop.name); setIntervalValue(String(loop.interval)); }}
                      title="Click to edit interval"
                    >
                      Every {loop.interval}s ✎
                    </span>
                  )}
                  <span>Runs: {loop.run_count}</span>
                  {loop.error_count > 0 && (
                    <span className="loop-errors">Errors: {loop.error_count}</span>
                  )}
                </div>
                {loop.last_run && (
                  <div className="loop-last-run">
                    Last: {new Date(loop.last_run).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ))}
            {loops.length === 0 && (
              <div className="no-data">No loops registered</div>
            )}
          </div>
        </div>

        {/* ── Middle Column: Fact Review Queue ── */}
        <div className="panel facts-panel">
          <h3>📝 Fact Review Queue</h3>
          <div className="facts-status-bar">
            {Object.entries(factsByStatus).map(([status, count]) => (
              <div
                key={status}
                className="status-chip"
                style={{
                  background: FACT_STATUS_COLORS[status]?.bg || '#e5e7eb',
                  color: FACT_STATUS_COLORS[status]?.text || '#4b5563',
                }}
              >
                {status}: {count}
              </div>
            ))}
          </div>

          {reviewCount > 0 && (
            <div className="bulk-actions">
              <button onClick={approveAll} className="btn-sm approve-all">✓ Approve All</button>
              <button onClick={rejectAll} className="btn-sm reject-all">✕ Reject All</button>
            </div>
          )}

          <div className="facts-list">
            {tempFacts.map(fact => (
              <div key={fact.id} className="fact-item-expanded">
                {editingFact === fact.id ? (
                  <div className="fact-edit-row">
                    <textarea
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      className="fact-edit-input"
                      rows={2}
                      autoFocus
                    />
                    <div className="fact-edit-actions">
                      <button onClick={() => saveFact(fact.id)} className="btn-sm save">Save</button>
                      <button onClick={() => setEditingFact(null)} className="btn-sm cancel">Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="fact-top">
                      <span className="fact-text-full">{fact.text}</span>
                      <span
                        className="fact-status-badge"
                        style={{
                          background: FACT_STATUS_COLORS[fact.status]?.bg || '#e5e7eb',
                          color: FACT_STATUS_COLORS[fact.status]?.text || '#4b5563',
                        }}
                      >
                        {fact.status}
                      </span>
                    </div>
                    <div className="fact-meta">
                      {fact.hier_key && <span className="fact-key">{fact.hier_key}</span>}
                      {fact.confidence_score != null && (
                        <span className="fact-confidence">
                          conf: {(fact.confidence_score * 100).toFixed(0)}%
                        </span>
                      )}
                      <span className="fact-source">{fact.source}</span>
                    </div>
                    <div className="fact-actions">
                      {(fact.status === 'pending' || fact.status === 'pending_review') && (
                        <>
                          <button onClick={() => approveFact(fact.id)} className="btn-sm approve" title="Approve">✓</button>
                          <button onClick={() => rejectFact(fact.id)} className="btn-sm reject" title="Reject">✕</button>
                        </>
                      )}
                      <button
                        onClick={() => { setEditingFact(fact.id); setEditText(fact.text); }}
                        className="btn-sm edit"
                        title="Edit"
                      >✎</button>
                      <button onClick={() => deleteFact(fact.id)} className="btn-sm delete" title="Delete">🗑</button>
                    </div>
                  </>
                )}
              </div>
            ))}
            {tempFacts.length === 0 && (
              <div className="no-data">No pending facts — memory is clean</div>
            )}
          </div>
        </div>

        {/* ── Right Column: Potentiation ── */}
        <div className="panel potentiation-panel">
          <h3>⚡ Memory Potentiation</h3>
          <div className="potentiation-visual">
            <div className="potentiation-bar">
              <div
                className="bar-short"
                style={{ width: `${(shortCount / (shortCount + longCount || 1)) * 100}%` }}
              >
                SHORT
              </div>
              <div
                className="bar-long"
                style={{ width: `${(longCount / (shortCount + longCount || 1)) * 100}%` }}
              >
                LONG
              </div>
            </div>
          </div>

          {potentiation && (
            <div className="potentiation-details">
              <div className="pot-row">
                <span className="pot-label">SHORT</span>
                <span className="pot-count">{shortCount} links</span>
                <span className="pot-meta">
                  avg strength: {potentiation.SHORT?.avg_strength?.toFixed(2) || '0'}
                </span>
              </div>
              <div className="pot-row highlight">
                <span className="pot-label">LONG</span>
                <span className="pot-count">{longCount} links</span>
                <span className="pot-meta">
                  avg fires: {potentiation.LONG?.avg_fires?.toFixed(1) || '0'}
                </span>
              </div>
            </div>
          )}

          <div className="export-readiness">
            <h4>📦 Export Readiness</h4>
            <p>{longCount} consolidated memories ready for finetuning</p>
            {longCount >= 50 && (
              <span className="ready-badge">✓ Ready to export</span>
            )}
            {longCount < 50 && longCount > 0 && (
              <span className="building-badge">Building... ({longCount}/50)</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
