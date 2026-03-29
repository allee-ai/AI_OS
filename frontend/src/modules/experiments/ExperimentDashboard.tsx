import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import { BASE_URL } from '../../config/api';
import './ExperimentDashboard.css';

// ── Types ──

interface PhaseInfo {
  id: string;
  name: string;
  description: string;
  status: string;
  detail?: string;
  current_iter?: number;
  chunks?: number;
  loss_curve?: Array<{ iter: number; train_loss: number; val_loss?: number }>;
}

interface EvalModelResult {
  score: number;
  passed: number;
  total: number;
  status: string;
  details?: Array<{
    prompt: string;
    passed: boolean;
    keyword_hits?: number;
    min_required?: number;
    semantic_score?: number;
    keyword_score?: number;
    combined_score?: number;
    response_preview?: string;
  }>;
}

interface Improvement {
  base_score: number;
  final_score: number;
  delta: number;
  improved: boolean;
}

interface RunResults {
  models: {
    base: Record<string, EvalModelResult>;
    final: Record<string, EvalModelResult>;
  };
  improvement: Record<string, Improvement>;
}

interface RunStatus {
  run_id: string;
  status: string;
  config: Record<string, string | number>;
  current_phase: string | null;
  phases: PhaseInfo[];
  created_at: string;
  completed_at?: string;
  updated_at?: string;
  results?: RunResults;
  error?: string;
}

interface RunSummary {
  run_id: string;
  status: string;
  current_phase: string | null;
  created_at: string;
  completed_at?: string;
  has_results: boolean;
}

interface LossCurves {
  pretrain?: Array<{ iter: number; train_loss: number; val_loss?: number }>;
  sft?: Array<{ iter: number; train_loss: number; val_loss?: number }>;
}

interface Defaults {
  config: Record<string, string | number>;
  phases: Array<{ id: string; name: string; description: string }>;
}

// ── Phase Icons ──

const PHASE_ICONS: Record<string, Record<string, string>> = {
  pending:   { icon: '○', },
  running:   { icon: '◉', },
  completed: { icon: '✓', },
  failed:    { icon: '✗', },
};

function phaseIcon(status: string) {
  return PHASE_ICONS[status]?.icon ?? '○';
}

// ── Loss Chart SVG ──

function LossChart({ data, label }: { data: Array<{ iter: number; train_loss: number }>; label: string }) {
  if (!data || data.length < 2) return <div className="exp-chart-canvas" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>No data yet</div>;

  const maxIter = Math.max(...data.map(d => d.iter));
  const maxLoss = Math.max(...data.map(d => d.train_loss));
  const minLoss = Math.min(...data.map(d => d.train_loss));
  const range = maxLoss - minLoss || 1;
  const pad = 40;
  const w = 600;
  const h = 200;

  const points = data.map(d => {
    const x = pad + ((d.iter / maxIter) * (w - pad * 2));
    const y = h - pad - (((d.train_loss - minLoss) / range) * (h - pad * 2));
    return `${x},${y}`;
  }).join(' ');

  return (
    <div className="exp-chart-canvas">
      <svg className="exp-chart-svg" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <text x={pad} y={16} className="exp-chart-label" fontSize="11">{label} — Loss: {minLoss.toFixed(3)} → {data[data.length - 1].train_loss.toFixed(3)}</text>
        {/* Axis labels */}
        <text x={pad} y={h - 8} className="exp-chart-label" fontSize="10">0</text>
        <text x={w - pad} y={h - 8} className="exp-chart-label" fontSize="10" textAnchor="end">{maxIter}</text>
        <text x={pad - 4} y={h - pad} className="exp-chart-label" fontSize="10" textAnchor="end">{minLoss.toFixed(2)}</text>
        <text x={pad - 4} y={pad} className="exp-chart-label" fontSize="10" textAnchor="end">{maxLoss.toFixed(2)}</text>
        {/* Grid lines */}
        <line x1={pad} y1={pad} x2={pad} y2={h - pad} stroke="var(--border)" strokeWidth="0.5" />
        <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="var(--border)" strokeWidth="0.5" />
        {/* Loss curve */}
        <polyline points={points} className="exp-chart-line" />
      </svg>
    </div>
  );
}

// ── Component ──

export const ExperimentDashboard = () => {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [runStatus, setRunStatus] = useState<RunStatus | null>(null);
  const [lossCurves, setLossCurves] = useState<LossCurves>({});
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [launching, setLaunching] = useState(false);
  const [expandedEval, setExpandedEval] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Config overrides
  const [configOverrides, setConfigOverrides] = useState<Record<string, string>>({});

  // ── Fetch runs list ──
  const fetchRuns = useCallback(async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/experiments/t3/runs`);
      if (res.ok) {
        const data = await res.json();
        setRuns(data.runs || []);
      }
    } catch { /* ignore */ }
  }, []);

  // ── Fetch defaults ──
  useEffect(() => {
    fetch(`${BASE_URL}/api/experiments/t3/defaults`)
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setDefaults(data))
      .catch(() => {});
    fetchRuns();
  }, [fetchRuns]);

  // ── Fetch run status ──
  const fetchRunStatus = useCallback(async (runId: string) => {
    try {
      const res = await fetch(`${BASE_URL}/api/experiments/t3/status/${runId}`);
      if (res.ok) {
        const data: RunStatus = await res.json();
        setRunStatus(data);

        // Fetch loss curves if in training or completed
        if (['running', 'completed'].includes(data.status)) {
          const cRes = await fetch(`${BASE_URL}/api/experiments/t3/curves/${runId}`);
          if (cRes.ok) {
            setLossCurves(await cRes.json());
          }
        }
      }
    } catch { /* ignore */ }
  }, []);

  // ── Select run ──
  useEffect(() => {
    if (!selectedRun) {
      setRunStatus(null);
      setLossCurves({});
      return;
    }
    fetchRunStatus(selectedRun);
  }, [selectedRun, fetchRunStatus]);

  // ── Polling for active runs ──
  useEffect(() => {
    if (pollRef.current) clearInterval(pollRef.current);

    const hasActiveRun = runs.some(r => r.status === 'running');
    if (hasActiveRun || (runStatus && runStatus.status === 'running')) {
      pollRef.current = setInterval(() => {
        fetchRuns();
        if (selectedRun) fetchRunStatus(selectedRun);
      }, 5000);
    }

    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [runs, runStatus, selectedRun, fetchRuns, fetchRunStatus]);

  // ── Auto-select most recent run ──
  useEffect(() => {
    if (!selectedRun && runs.length > 0) {
      setSelectedRun(runs[0].run_id);
    }
  }, [runs, selectedRun]);

  // ── Launch ──
  const handleLaunch = async () => {
    setLaunching(true);
    try {
      const body: Record<string, string | number> = {};
      for (const [k, v] of Object.entries(configOverrides)) {
        if (v.trim()) {
          // Parse numeric values
          const num = Number(v);
          body[k] = isNaN(num) ? v : num;
        }
      }
      const res = await fetch(`${BASE_URL}/api/experiments/t3/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        await fetchRuns();
        setSelectedRun(data.run_id);
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to launch experiment');
      }
    } catch (e) {
      alert(`Error: ${e}`);
    } finally {
      setLaunching(false);
    }
  };

  // ── Config field helper ──
  const configField = (key: string, label: string) => {
    const defaultVal = defaults?.config?.[key] ?? '';
    return (
      <div className="exp-config-field" key={key}>
        <label>{label}</label>
        <input
          type="text"
          placeholder={String(defaultVal)}
          value={configOverrides[key] || ''}
          onChange={e => setConfigOverrides(prev => ({ ...prev, [key]: e.target.value }))}
        />
      </div>
    );
  };

  return (
    <div className="experiment-dashboard">
      {/* Sidebar */}
      <aside className="exp-sidebar">
        <div className="exp-sidebar-header">
          <span className="icon">🧪</span>
          <h2>Experiments</h2>
        </div>

        <Link to="/" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.8rem', marginBottom: '0.5rem' }}>
          ← Dashboard
        </Link>

        <div className="exp-sidebar-section">T3 Runs</div>

        {runs.length === 0 && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', padding: '0.5rem' }}>
            No experiments yet
          </div>
        )}

        {runs.map(r => (
          <button
            key={r.run_id}
            className={`exp-run-btn ${selectedRun === r.run_id ? 'active' : ''}`}
            onClick={() => setSelectedRun(r.run_id)}
          >
            <span className={`exp-status ${r.status}`}>{r.status}</span>
            <span className="run-id">{r.run_id}</span>
          </button>
        ))}

        <div className="exp-sidebar-footer">
          <Link to="/eval" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.8rem' }}>
            🎯 Eval Dashboard
          </Link>
          <br />
          <Link to="/training" style={{ color: 'var(--text-muted)', textDecoration: 'none', fontSize: '0.8rem' }}>
            🔥 Training Data
          </Link>
        </div>
      </aside>

      {/* Main */}
      <main className="exp-main">
        <h2>T3 — Continued Pretraining Experiment</h2>
        <p className="exp-desc">
          Train SmolLM2-135M on the full AI_OS codebase, then evaluate knowledge retention.
          Does a model that reads its own architecture learn to describe itself?
        </p>

        {/* Launch Panel */}
        <div className="exp-launch-panel">
          <h3>🚀 Launch New Experiment</h3>
          <div className="exp-config-grid">
            {configField('pretrain_iters', 'Pretrain Iters')}
            {configField('pretrain_batch_size', 'Pretrain Batch')}
            {configField('pretrain_lr', 'Pretrain LR')}
            {configField('sft_iters', 'SFT Iters')}
            {configField('sft_batch_size', 'SFT Batch')}
            {configField('sft_lr', 'SFT LR')}
          </div>
          <button
            className="exp-launch-btn"
            onClick={handleLaunch}
            disabled={launching || runs.some(r => r.status === 'running')}
          >
            {launching ? 'Launching...' : runs.some(r => r.status === 'running') ? 'Experiment Running...' : 'Start T3 Pipeline'}
          </button>
        </div>

        {/* No run selected */}
        {!runStatus && (
          <div className="exp-empty">
            <span className="icon">🧪</span>
            <p>Launch an experiment or select a previous run from the sidebar.</p>
          </div>
        )}

        {/* Run Detail */}
        {runStatus && (
          <>
            {/* Status Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
              <span className={`exp-status ${runStatus.status}`}>{runStatus.status}</span>
              <span style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                {runStatus.run_id}
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: 'auto' }}>
                {runStatus.created_at}
              </span>
            </div>

            {runStatus.error && (
              <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid var(--error, #ef4444)', borderRadius: '0.5rem', padding: '0.75rem', marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--error, #ef4444)' }}>
                Error: {runStatus.error}
              </div>
            )}

            {/* Phase Progress */}
            <div className="exp-phases">
              <h3>Pipeline Progress</h3>
              <div className="exp-phase-list">
                {runStatus.phases.map(p => (
                  <div key={p.id} className={`exp-phase ${p.status}`}>
                    <span className="exp-phase-icon">{phaseIcon(p.status)}</span>
                    <div className="exp-phase-info">
                      <div className="exp-phase-name">{p.name}</div>
                      <div className="exp-phase-detail">
                        {p.detail || p.description}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Loss Curves */}
            {(lossCurves.pretrain && lossCurves.pretrain.length > 1) && (
              <div className="exp-chart">
                <h3>Pretraining Loss</h3>
                <LossChart data={lossCurves.pretrain} label="Continued Pretraining" />
              </div>
            )}

            {(lossCurves.sft && lossCurves.sft.length > 1) && (
              <div className="exp-chart">
                <h3>SFT Loss</h3>
                <LossChart data={lossCurves.sft} label="Supervised Fine-Tuning" />
              </div>
            )}

            {/* Results */}
            {runStatus.results && (
              <div className="exp-results">
                <h3>Eval Results — Base vs Final</h3>

                {/* Summary Cards */}
                <div className="exp-results-grid">
                  {Object.entries(runStatus.results.improvement).map(([evalName, imp]) => (
                    <div className="exp-result-card" key={evalName}>
                      <h4>{evalName.replace(/_/g, ' ')}</h4>
                      <div className="exp-score-row">
                        <span className="exp-score-label">Base</span>
                        <span className="exp-score-value">{(imp.base_score * 100).toFixed(0)}%</span>
                      </div>
                      <div className="exp-score-row">
                        <span className="exp-score-label">Final</span>
                        <span className="exp-score-value">{(imp.final_score * 100).toFixed(0)}%</span>
                      </div>
                      <span className={`exp-delta ${imp.delta >= 0 ? 'positive' : 'negative'}`}>
                        {imp.delta >= 0 ? '+' : ''}{(imp.delta * 100).toFixed(1)}%
                      </span>

                      <button
                        onClick={() => setExpandedEval(expandedEval === evalName ? null : evalName)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem', marginTop: '0.5rem', padding: 0 }}
                      >
                        {expandedEval === evalName ? '▾ Hide details' : '▸ Show details'}
                      </button>

                      {/* Expanded details */}
                      {expandedEval === evalName && runStatus.results?.models && (
                        <div style={{ marginTop: '0.5rem' }}>
                          {['base', 'final'].map(modelKey => {
                            const modelData = runStatus.results!.models[modelKey as 'base' | 'final']?.[evalName];
                            if (!modelData?.details) return null;
                            return (
                              <div key={modelKey}>
                                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', margin: '0.5rem 0 0.25rem', textTransform: 'uppercase' }}>
                                  {modelKey} model
                                </div>
                                <table className="exp-eval-details">
                                  <thead>
                                    <tr>
                                      <th>Prompt</th>
                                      <th>Result</th>
                                      <th>Semantic</th>
                                      <th>Keywords</th>
                                      <th>Combined</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {modelData.details.map((d, i) => (
                                      <tr key={i}>
                                        <td style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                          {d.prompt}
                                        </td>
                                        <td className={d.passed ? 'pass' : 'fail'}>
                                          {d.passed ? '✓' : '✗'}
                                        </td>
                                        <td>{d.semantic_score != null ? d.semantic_score.toFixed(2) : '-'}</td>
                                        <td>{d.keyword_hits ?? '-'}/{d.min_required ?? '-'}</td>
                                        <td style={{ fontWeight: 600 }}>{d.combined_score != null ? d.combined_score.toFixed(2) : '-'}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
};
