/**
 * Subconscious Dashboard — Master-Detail Layout
 * ===============================================
 * Click a loop on the left to see its detail panel on the right.
 * 
 * Layout: 280px sidebar (loop list) + flex:1 detail panel
 * 
 * Features:
 * - All loops (built-in + custom) listed with status dots
 * - Per-loop detail: config, associated facts, stats
 * - Model selector, interval editor, pause/resume
 * - Fact review queue (approve/reject/edit/delete)
 * - Create custom chain-of-thought loops with source + prompt
 * - Unread queue progress bar
 * - Potentiation stats + export readiness
 */

import { useState, useEffect, useCallback } from 'react';
import './SubconsciousDashboard.css';

const API = 'http://localhost:8000/api/subconscious';

// ── Types ──────────────────────────────────────────────────

interface LoopStats {
  name: string;
  status: string;
  interval: number;
  enabled: boolean;
  context_aware: boolean;
  max_errors: number;
  error_backoff: number;
  last_run: string | null;
  run_count: number;
  error_count: number;
  consecutive_errors: number;
  model?: string;
  unprocessed_turns?: number;
  last_processed_turn_id?: number | null;
  source?: string;
  target?: string;
  prompt_preview?: string;
  is_custom?: boolean;
  auto_approve_threshold?: number;
  duplicate_threshold?: number;
  prompts?: Record<string, string>;
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
  error: '#ef4444',
};

const FACT_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: '#e5e7eb', text: '#4b5563' },
  pending_review: { bg: '#fef3c7', text: '#92400e' },
  approved: { bg: '#d1fae5', text: '#065f46' },
  consolidated: { bg: '#ede9fe', text: '#5b21b6' },
  rejected: { bg: '#fee2e2', text: '#991b1b' },
};

// ── Component ──────────────────────────────────────────────

export default function SubconsciousDashboard() {
  // Data state
  const [loops, setLoops] = useState<LoopStats[]>([]);
  const [tempFacts, setTempFacts] = useState<TempFact[]>([]);
  const [factsByStatus, setFactsByStatus] = useState<Record<string, number>>({});
  const [potentiation, setPotentiation] = useState<PotentiationStats | null>(null);
  const [queue, setQueue] = useState<QueueInfo | null>(null);
  const [customLoopMeta, setCustomLoopMeta] = useState<{
    sources: string[];
    targets: string[];
  }>({ sources: [], targets: [] });
  const [loading, setLoading] = useState(true);

  // UI state
  const [selectedLoop, setSelectedLoop] = useState<string | null>(null);
  const [showAddLoop, setShowAddLoop] = useState(false);
  const [editingInterval, setEditingInterval] = useState(false);
  const [intervalValue, setIntervalValue] = useState('');
  const [editingFact, setEditingFact] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  const [editingModel, setEditingModel] = useState(false);
  const [modelValue, setModelValue] = useState('');
  const [editingPrompt, setEditingPrompt] = useState<string | null>(null);
  const [promptValue, setPromptValue] = useState('');
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<string | null>(null);

  // New loop form
  const [newLoop, setNewLoop] = useState({
    name: '',
    source: 'convos',
    target: 'temp_memory',
    interval: 300,
    model: '',
    prompt: '',
  });

  // State preview
  const [previewQuery, setPreviewQuery] = useState('');
  const [previewResult, setPreviewResult] = useState<{
    thread_scores: Record<string, number>;
    state_block: string;
    total_tokens: number;
  } | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  // ── Data fetching ────────────────────────────────────────

  const fetchData = useCallback(async () => {
    try {
      const [loopsRes, factsRes, potRes, queueRes, customRes] = await Promise.all([
        fetch(`${API}/loops`),
        fetch(`${API}/temp-facts`),
        fetch(`${API}/potentiation`),
        fetch(`${API}/queue`),
        fetch(`${API}/loops/custom`),
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
      }
      if (customRes.ok) {
        const data = await customRes.json();
        setCustomLoopMeta({
          sources: data.available_sources || [],
          targets: data.available_targets || [],
        });
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

  // ── Derived state ────────────────────────────────────────

  const selected = loops.find(l => l.name === selectedLoop);
  const reviewCount = (factsByStatus['pending'] || 0) + (factsByStatus['pending_review'] || 0);
  const longCount = potentiation?.LONG?.count || 0;
  const shortCount = potentiation?.SHORT?.count || 0;

  // Filter facts relevant to selected loop
  const selectedFacts = selected
    ? tempFacts.filter(f => {
        if (selected.name === 'memory') return f.source === 'conversation';
        if (selected.name === 'consolidation') return false;
        if (selected.is_custom) return f.source === `loop:${selected.name}`;
        return false;
      })
    : [];

  // ── Fact actions ─────────────────────────────────────────

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

  // ── Loop actions ─────────────────────────────────────────

  const saveInterval = async () => {
    if (!selected) return;
    const val = parseFloat(intervalValue);
    if (isNaN(val) || val < 5) return;

    if (selected.is_custom) {
      await fetch(`${API}/loops/custom/${selected.name}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval: val }),
      });
    } else {
      await fetch(`${API}/loops/${selected.name}/interval`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ interval: val }),
      });
    }
    setEditingInterval(false);
    fetchData();
  };

  const runPreview = async () => {
    if (!previewQuery.trim()) return;
    setPreviewLoading(true);
    try {
      const res = await fetch(`${API}/preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: previewQuery }),
      });
      if (res.ok) {
        const data = await res.json();
        setPreviewResult(data);
        setShowPreview(true);
      }
    } catch (err) {
      console.error('Preview failed:', err);
    } finally {
      setPreviewLoading(false);
    }
  };

  const toggleLoop = async (loopName: string, currentStatus: string) => {
    const action = currentStatus === 'paused' ? 'resume' : 'pause';
    await fetch(`${API}/loops/${loopName}/${action}`, { method: 'POST' });
    fetchData();
  };

  const toggleContextAware = async (loopName: string, currentValue: boolean) => {
    await fetch(`${API}/loops/${loopName}/context-aware`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: !currentValue }),
    });
    fetchData();
  };

  const savePrompt = async (stage: string) => {
    if (!selected) return;
    const isReset = promptValue.trim() === '';
    await fetch(`${API}/loops/${selected.name}/prompts/${stage}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: isReset ? '' : promptValue }),
    });
    setEditingPrompt(null);
    fetchData();
  };

  const saveModel = async () => {
    if (!selected || !modelValue.trim()) return;

    if (selected.name === 'memory') {
      await fetch(`${API}/loops/memory/model`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelValue }),
      });
    } else if (selected.is_custom) {
      await fetch(`${API}/loops/custom/${selected.name}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelValue }),
      });
    }
    setEditingModel(false);
    fetchData();
  };

  const deleteCustomLoop = async (name: string) => {
    if (!confirm(`Delete custom loop "${name}"?`)) return;
    await fetch(`${API}/loops/custom/${name}`, { method: 'DELETE' });
    if (selectedLoop === name) setSelectedLoop(null);
    fetchData();
  };

  // ── Custom loop creation ─────────────────────────────────

  const createCustomLoop = async () => {
    if (!newLoop.name.trim() || !newLoop.prompt.trim()) return;
    const res = await fetch(`${API}/loops/custom`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newLoop.name.trim(),
        source: newLoop.source,
        target: newLoop.target,
        interval: newLoop.interval,
        model: newLoop.model || null,
        prompt: newLoop.prompt,
      }),
    });
    if (res.ok) {
      const loopName = newLoop.name.trim();
      setShowAddLoop(false);
      setNewLoop({ name: '', source: 'convos', target: 'temp_memory', interval: 300, model: '', prompt: '' });
      fetchData();
      setTimeout(() => setSelectedLoop(loopName), 500);
    }
  };

  // ── Consolidation/Export ─────────────────────────────────

  const handleConsolidate = async () => {
    try {
      const res = await fetch(`${API}/consolidate`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setExportResult(`Consolidated: ${data.result?.promoted || 0} promoted`);
        fetchData();
      }
    } catch { setExportResult('Failed'); }
    setTimeout(() => setExportResult(null), 3000);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('http://localhost:8000/api/finetune/export', { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        const total = data.results?.combined?.total_examples || 0;
        setExportResult(`Exported ${total} examples`);
      }
    } catch { setExportResult('Export failed'); }
    finally {
      setExporting(false);
      setTimeout(() => setExportResult(null), 5000);
    }
  };

  // ── Render ───────────────────────────────────────────────

  if (loading) {
    return <div className="subconscious-dashboard loading">Loading subconscious...</div>;
  }

  const builtinLoops = loops.filter(l => !l.is_custom);
  const customLoopsList = loops.filter(l => l.is_custom);

  return (
    <div className="subconscious-dashboard">
      {/* ── Top: Stats Row ── */}
      <div className="subconscious-stats">
        <div className="stat-card">
          <span className="stat-value">{loops.length}</span>
          <span className="stat-label">Loops</span>
        </div>
        <div className={`stat-card ${(queue?.unprocessed || 0) > 0 ? 'highlight' : ''}`}>
          <span className="stat-value">{queue?.unprocessed || 0}</span>
          <span className="stat-label">Unread</span>
        </div>
        <div className={`stat-card ${reviewCount > 0 ? 'highlight' : ''}`}>
          <span className="stat-value">{reviewCount}</span>
          <span className="stat-label">Review</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{shortCount}</span>
          <span className="stat-label">SHORT</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{longCount}</span>
          <span className="stat-label">LONG</span>
        </div>
        <div className="stat-card actions-card">
          <button onClick={handleConsolidate} className="action-btn-sm consolidate">🧠 Consolidate</button>
          <button onClick={handleExport} disabled={exporting} className="action-btn-sm export">
            {exporting ? '⏳...' : '📦 Export'}
          </button>
          {exportResult && <span className="action-result-sm">{exportResult}</span>}
        </div>
      </div>

      {/* ── State Preview ── */}
      <div className="state-preview-bar">
        <input
          type="text"
          className="preview-input"
          placeholder="Test a query… see what STATE the model would receive"
          value={previewQuery}
          onChange={e => setPreviewQuery(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && runPreview()}
        />
        <button
          className="btn-preview"
          onClick={runPreview}
          disabled={previewLoading || !previewQuery.trim()}
        >
          {previewLoading ? '⏳' : '▶ Preview'}
        </button>
        {previewResult && (
          <button
            className="btn-preview toggle"
            onClick={() => setShowPreview(!showPreview)}
          >
            {showPreview ? '▲ Hide' : '▼ Show'}
          </button>
        )}
      </div>

      {showPreview && previewResult && (
        <div className="state-preview-panel">
          <div className="preview-scores">
            <h4>Thread Scores</h4>
            <div className="score-bars">
              {Object.entries(previewResult.thread_scores)
                .sort(([,a], [,b]) => b - a)
                .map(([thread, score]) => (
                  <div key={thread} className="score-bar-row">
                    <span className="score-thread-name">{thread}</span>
                    <div className="score-bar-track">
                      <div
                        className={`score-bar-fill ${score >= 7 ? 'l3' : score >= 3.5 ? 'l2' : 'l1'}`}
                        style={{ width: `${(score / 10) * 100}%` }}
                      />
                    </div>
                    <span className="score-value">{score.toFixed(1)}</span>
                    <span className="score-level">
                      {score >= 7 ? 'L3' : score >= 3.5 ? 'L2' : 'L1'}
                    </span>
                  </div>
                ))}
            </div>
            <div className="preview-token-count">
              ~{previewResult.total_tokens} tokens
            </div>
          </div>
          <div className="preview-state-block">
            <h4>STATE Block</h4>
            <pre className="state-code">{previewResult.state_block}</pre>
          </div>
        </div>
      )}

      {/* ── Main: Master-Detail ── */}
      <div className="subconscious-layout">

        {/* ── LEFT: Loop List (sidebar) ── */}
        <div className="loop-sidebar">
          <div className="sidebar-header">
            <span>Loops</span>
            <button className="btn-add" onClick={() => setShowAddLoop(true)} title="Add custom loop">+</button>
          </div>

          {/* Queue bar */}
          {(queue?.unprocessed || 0) > 0 && (
            <div className="queue-bar-mini">
              <div className="queue-progress-mini">
                <div
                  className="queue-fill-mini"
                  style={{
                    width: `${Math.min(100, ((queue!.total_turns - queue!.unprocessed) / (queue!.total_turns || 1)) * 100)}%`
                  }}
                />
              </div>
              <span className="queue-text-mini">{queue!.unprocessed} turns queued</span>
            </div>
          )}

          {/* Built-in loops */}
          <div className="loop-group-label">Built-in</div>
          {builtinLoops.map(loop => (
            <div
              key={loop.name}
              className={`loop-list-item ${selectedLoop === loop.name ? 'active' : ''}`}
              onClick={() => { setSelectedLoop(loop.name); setShowAddLoop(false); }}
            >
              <span
                className="loop-dot"
                style={{ background: STATUS_COLORS[loop.status] || '#6b7280' }}
              />
              <span className="loop-list-name">{loop.name}</span>
              <span className="loop-list-meta">
                {loop.run_count > 0 ? `${loop.run_count} runs` : loop.status}
              </span>
            </div>
          ))}

          {/* Custom loops */}
          {customLoopsList.length > 0 && (
            <>
              <div className="loop-group-label">Custom</div>
              {customLoopsList.map(loop => (
                <div
                  key={loop.name}
                  className={`loop-list-item ${selectedLoop === loop.name ? 'active' : ''}`}
                  onClick={() => { setSelectedLoop(loop.name); setShowAddLoop(false); }}
                >
                  <span
                    className="loop-dot"
                    style={{ background: STATUS_COLORS[loop.status] || '#6b7280' }}
                  />
                  <span className="loop-list-name">{loop.name}</span>
                  <span className="loop-list-source">{loop.source}</span>
                </div>
              ))}
            </>
          )}

          {/* Potentiation summary at bottom of sidebar */}
          <div className="sidebar-footer">
            <div className="pot-bar-mini">
              <div
                className="pot-short-mini"
                style={{ width: `${(shortCount / Math.max(shortCount + longCount, 1)) * 100}%` }}
              />
              <div
                className="pot-long-mini"
                style={{ width: `${(longCount / Math.max(shortCount + longCount, 1)) * 100}%` }}
              />
            </div>
            <div className="pot-legend">
              <span>SHORT: {shortCount}</span>
              <span>LONG: {longCount}</span>
            </div>
            {longCount >= 50 && <span className="ready-badge-mini">✓ Export ready</span>}
          </div>
        </div>

        {/* ── RIGHT: Detail Panel ── */}
        <div className="loop-detail">
          {showAddLoop ? (
            /* ── Add Custom Loop Form ── */
            <div className="detail-section">
              <h3>Add Custom Loop</h3>
              <p className="detail-hint">Create a chain-of-thought loop that reads from a source, processes with an LLM, and writes results to a target.</p>

              <div className="form-grid">
                <label className="form-label">
                  Name
                  <input
                    type="text"
                    value={newLoop.name}
                    onChange={e => setNewLoop({ ...newLoop, name: e.target.value })}
                    placeholder="e.g. sentiment-tracker"
                    className="form-input"
                  />
                </label>

                <label className="form-label">
                  Source
                  <select
                    value={newLoop.source}
                    onChange={e => setNewLoop({ ...newLoop, source: e.target.value })}
                    className="form-select"
                  >
                    {(customLoopMeta.sources.length > 0 ? customLoopMeta.sources : ['convos', 'feeds', 'temp_memory', 'identity', 'philosophy', 'log', 'workspace']).map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </label>

                <label className="form-label">
                  Target
                  <select
                    value={newLoop.target}
                    onChange={e => setNewLoop({ ...newLoop, target: e.target.value })}
                    className="form-select"
                  >
                    {(customLoopMeta.targets.length > 0 ? customLoopMeta.targets : ['temp_memory', 'log']).map(t => (
                      <option key={t} value={t}>{t}</option>
                    ))}
                  </select>
                </label>

                <label className="form-label">
                  Interval (seconds)
                  <input
                    type="number"
                    min={5}
                    value={newLoop.interval}
                    onChange={e => setNewLoop({ ...newLoop, interval: parseInt(e.target.value) || 300 })}
                    className="form-input"
                  />
                </label>

                <label className="form-label">
                  Model (optional)
                  <input
                    type="text"
                    value={newLoop.model}
                    onChange={e => setNewLoop({ ...newLoop, model: e.target.value })}
                    placeholder="e.g. qwen2.5:7b"
                    className="form-input mono"
                  />
                </label>
              </div>

              <label className="form-label full-width">
                Prompt Template
                <textarea
                  value={newLoop.prompt}
                  onChange={e => setNewLoop({ ...newLoop, prompt: e.target.value })}
                  placeholder="Analyze the following data and extract key insights..."
                  className="form-textarea"
                  rows={5}
                />
              </label>

              <div className="form-actions">
                <button onClick={createCustomLoop} className="btn-primary" disabled={!newLoop.name.trim() || !newLoop.prompt.trim()}>
                  Create Loop
                </button>
                <button onClick={() => setShowAddLoop(false)} className="btn-secondary">Cancel</button>
              </div>
            </div>
          ) : selected ? (
            /* ── Loop Detail View ── */
            <>
              <div className="detail-header">
                <div className="detail-title-row">
                  <span
                    className="detail-status-dot"
                    style={{ background: STATUS_COLORS[selected.status] || '#6b7280' }}
                  />
                  <h3 className="detail-title">{selected.name}</h3>
                  {selected.is_custom && (
                    <span className="custom-badge">custom</span>
                  )}
                  <span className={`status-label ${selected.status}`}>{selected.status}</span>
                </div>
                <div className="detail-actions">
                  {(selected.status === 'running' || selected.status === 'paused') && (
                    <button
                      className="btn-sm"
                      onClick={() => toggleLoop(selected.name, selected.status)}
                    >
                      {selected.status === 'paused' ? '▶ Resume' : '⏸ Pause'}
                    </button>
                  )}
                  {selected.is_custom && (
                    <button
                      className="btn-sm delete"
                      onClick={() => deleteCustomLoop(selected.name)}
                    >
                      🗑 Delete
                    </button>
                  )}
                </div>
              </div>

              {/* Config section */}
              <div className="detail-section">
                <h4>Configuration</h4>
                <div className="config-grid">
                  {/* Interval */}
                  <div className="config-row">
                    <span className="config-label">Interval</span>
                    {editingInterval ? (
                      <div className="config-edit">
                        <input
                          type="number"
                          min={5}
                          value={intervalValue}
                          onChange={e => setIntervalValue(e.target.value)}
                          onKeyDown={e => e.key === 'Enter' && saveInterval()}
                          className="config-input"
                          autoFocus
                        />
                        <span className="config-unit">s</span>
                        <button onClick={saveInterval} className="btn-sm save">✓</button>
                        <button onClick={() => setEditingInterval(false)} className="btn-sm cancel">✕</button>
                      </div>
                    ) : (
                      <span
                        className="config-value editable"
                        onClick={() => { setEditingInterval(true); setIntervalValue(String(selected.interval)); }}
                      >
                        Every {selected.interval}s ✎
                      </span>
                    )}
                  </div>

                  {/* Model */}
                  {(selected.model || selected.name === 'memory' || selected.is_custom) && (
                    <div className="config-row">
                      <span className="config-label">Model</span>
                      {editingModel ? (
                        <div className="config-edit">
                          <input
                            type="text"
                            value={modelValue}
                            onChange={e => setModelValue(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && saveModel()}
                            className="config-input mono"
                            autoFocus
                          />
                          <button onClick={saveModel} className="btn-sm save">✓</button>
                          <button onClick={() => setEditingModel(false)} className="btn-sm cancel">✕</button>
                        </div>
                      ) : (
                        <span
                          className="config-value editable mono"
                          onClick={() => { setEditingModel(true); setModelValue(selected.model || ''); }}
                        >
                          {selected.model || 'default'} ✎
                        </span>
                      )}
                    </div>
                  )}

                  {/* Source (custom loops) */}
                  {selected.source && (
                    <div className="config-row">
                      <span className="config-label">Source</span>
                      <span className="config-value">{selected.source}</span>
                    </div>
                  )}

                  {/* Target (custom loops) */}
                  {selected.target && (
                    <div className="config-row">
                      <span className="config-label">Target</span>
                      <span className="config-value">{selected.target}</span>
                    </div>
                  )}

                  {/* Prompt preview (custom loops) */}
                  {selected.prompt_preview && (
                    <div className="config-row">
                      <span className="config-label">Prompt</span>
                      <span className="config-value prompt-preview">{selected.prompt_preview}</span>
                    </div>
                  )}

                  {/* Context-Aware toggle */}
                  <div className="config-row">
                    <span className="config-label">Context-Aware</span>
                    <span
                      className="config-value editable"
                      onClick={() => toggleContextAware(selected.name, selected.context_aware)}
                      title="When ON, the orchestrator STATE (identity, philosophy, linking, log) is injected into this loop's LLM prompts"
                    >
                      {selected.context_aware
                        ? <span style={{ color: '#22c55e' }}>◉ ON — full STATE injection</span>
                        : <span style={{ color: '#6b7280' }}>○ OFF — raw prompts only</span>
                      }
                    </span>
                  </div>

                  {/* Error tolerance */}
                  <div className="config-row">
                    <span className="config-label">Max Errors</span>
                    <span className="config-value">{selected.max_errors ?? 3} consecutive</span>
                  </div>
                  <div className="config-row">
                    <span className="config-label">Error Backoff</span>
                    <span className="config-value">{selected.error_backoff ?? 2.0}× interval</span>
                  </div>

                  {/* Consolidation thresholds */}
                  {selected.auto_approve_threshold != null && (
                    <div className="config-row">
                      <span className="config-label">Auto-Approve</span>
                      <span className="config-value">≥ {(selected.auto_approve_threshold * 100).toFixed(0)}% confidence</span>
                    </div>
                  )}
                  {selected.duplicate_threshold != null && (
                    <div className="config-row">
                      <span className="config-label">Dup Threshold</span>
                      <span className="config-value">≥ {(selected.duplicate_threshold * 100).toFixed(0)}% similarity</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Prompts section — visible for loops that have LLM prompts */}
              {selected.prompts && Object.keys(selected.prompts).length > 0 && (
                <div className="detail-section">
                  <h4>Prompts</h4>
                  <div className="prompts-list">
                    {Object.entries(selected.prompts).map(([stage, text]) => (
                      <div key={stage} className="prompt-item">
                        <div className="prompt-header">
                          <span className="prompt-stage">{stage}</span>
                          {editingPrompt === stage ? (
                            <div className="prompt-edit-actions">
                              <button onClick={() => savePrompt(stage)} className="btn-sm save">Save</button>
                              <button onClick={() => setEditingPrompt(null)} className="btn-sm cancel">Cancel</button>
                              <button
                                onClick={() => { setPromptValue(''); savePrompt(stage); }}
                                className="btn-sm"
                                title="Reset to default"
                              >↺ Default</button>
                            </div>
                          ) : (
                            <button
                              onClick={() => { setEditingPrompt(stage); setPromptValue(text); }}
                              className="btn-sm edit"
                            >✎ Edit</button>
                          )}
                        </div>
                        {editingPrompt === stage ? (
                          <textarea
                            value={promptValue}
                            onChange={e => setPromptValue(e.target.value)}
                            className="prompt-textarea"
                            rows={Math.min(20, Math.max(6, text.split('\n').length + 2))}
                            spellCheck={false}
                          />
                        ) : (
                          <pre className="prompt-preview-block">{text}</pre>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Stats section */}
              <div className="detail-section">
                <h4>Stats</h4>
                <div className="stats-grid">
                  <div className="stat-mini">
                    <span className="stat-mini-value">{selected.run_count}</span>
                    <span className="stat-mini-label">Runs</span>
                  </div>
                  <div className="stat-mini">
                    <span className="stat-mini-value">{selected.error_count}</span>
                    <span className="stat-mini-label">Errors</span>
                  </div>
                  {selected.unprocessed_turns != null && (
                    <div className="stat-mini">
                      <span className="stat-mini-value">{selected.unprocessed_turns}</span>
                      <span className="stat-mini-label">Queued</span>
                    </div>
                  )}
                  {selected.last_run && (
                    <div className="stat-mini wide">
                      <span className="stat-mini-value time">
                        {new Date(selected.last_run).toLocaleTimeString()}
                      </span>
                      <span className="stat-mini-label">Last Run</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Queue bar for memory loop */}
              {selected.name === 'memory' && (queue?.unprocessed || 0) > 0 && (
                <div className="detail-section">
                  <h4>Unread Queue</h4>
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
                      {queue!.unprocessed} of {queue!.total_turns} turns waiting
                    </span>
                  </div>
                </div>
              )}

              {/* Facts section - for loops that produce facts */}
              {(selected.name === 'memory' || selected.is_custom) && (
                <div className="detail-section">
                  <div className="section-header-row">
                    <h4>Facts ({selectedFacts.length})</h4>
                    {selectedFacts.length > 0 && (
                      <div className="bulk-actions">
                        <button onClick={approveAll} className="btn-sm approve">✓ All</button>
                        <button onClick={rejectAll} className="btn-sm reject">✕ All</button>
                      </div>
                    )}
                  </div>
                  <div className="facts-list">
                    {selectedFacts.map(fact => (
                      <div key={fact.id} className="fact-item">
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
                                className="fact-badge"
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
                                  {(fact.confidence_score * 100).toFixed(0)}%
                                </span>
                              )}
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
                    {selectedFacts.length === 0 && (
                      <div className="no-data">No facts from this loop yet</div>
                    )}
                  </div>
                </div>
              )}

              {/* Consolidation detail */}
              {selected.name === 'consolidation' && potentiation && (
                <div className="detail-section">
                  <h4>Potentiation</h4>
                  <div className="potentiation-visual">
                    <div className="potentiation-bar">
                      <div
                        className="bar-short"
                        style={{ width: `${(shortCount / Math.max(shortCount + longCount, 1)) * 100}%` }}
                      >
                        SHORT
                      </div>
                      <div
                        className="bar-long"
                        style={{ width: `${(longCount / Math.max(shortCount + longCount, 1)) * 100}%` }}
                      >
                        LONG
                      </div>
                    </div>
                  </div>
                  <div className="potentiation-details">
                    <div className="pot-row">
                      <span className="pot-label">SHORT</span>
                      <span>{shortCount} links</span>
                      <span className="pot-meta">avg str: {potentiation.SHORT?.avg_strength?.toFixed(2) || '0'}</span>
                    </div>
                    <div className="pot-row highlight">
                      <span className="pot-label">LONG</span>
                      <span>{longCount} links</span>
                      <span className="pot-meta">avg fires: {potentiation.LONG?.avg_fires?.toFixed(1) || '0'}</span>
                    </div>
                  </div>
                  <div className="export-readiness">
                    <p>{longCount} memories ready for finetuning</p>
                    {longCount >= 50 && <span className="ready-badge">✓ Ready to export</span>}
                    {longCount < 50 && longCount > 0 && (
                      <span className="building-badge">Building... ({longCount}/50)</span>
                    )}
                  </div>
                </div>
              )}

              {/* All facts view when clicking consolidation */}
              {selected.name === 'consolidation' && (
                <div className="detail-section">
                  <div className="section-header-row">
                    <h4>All Facts ({tempFacts.length})</h4>
                    <div className="facts-status-bar">
                      {Object.entries(factsByStatus).map(([status, count]) => (
                        <span
                          key={status}
                          className="status-chip"
                          style={{
                            background: FACT_STATUS_COLORS[status]?.bg || '#e5e7eb',
                            color: FACT_STATUS_COLORS[status]?.text || '#4b5563',
                          }}
                        >
                          {status}: {count}
                        </span>
                      ))}
                    </div>
                  </div>
                  {reviewCount > 0 && (
                    <div className="bulk-actions">
                      <button onClick={approveAll} className="btn-sm approve">✓ Approve All</button>
                      <button onClick={rejectAll} className="btn-sm reject">✕ Reject All</button>
                    </div>
                  )}
                  <div className="facts-list">
                    {tempFacts.map(fact => (
                      <div key={fact.id} className="fact-item">
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
                                className="fact-badge"
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
                                  {(fact.confidence_score * 100).toFixed(0)}%
                                </span>
                              )}
                              <span className="fact-source">{fact.source}</span>
                            </div>
                            <div className="fact-actions">
                              {(fact.status === 'pending' || fact.status === 'pending_review') && (
                                <>
                                  <button onClick={() => approveFact(fact.id)} className="btn-sm approve">✓</button>
                                  <button onClick={() => rejectFact(fact.id)} className="btn-sm reject">✕</button>
                                </>
                              )}
                              <button
                                onClick={() => { setEditingFact(fact.id); setEditText(fact.text); }}
                                className="btn-sm edit"
                              >✎</button>
                              <button onClick={() => deleteFact(fact.id)} className="btn-sm delete">🗑</button>
                            </div>
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            /* ── Empty state ── */
            <div className="detail-empty">
              <div className="empty-icon">🔄</div>
              <h3>Select a loop</h3>
              <p>Click a loop on the left to view and edit its configuration, or add a custom chain-of-thought loop.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
