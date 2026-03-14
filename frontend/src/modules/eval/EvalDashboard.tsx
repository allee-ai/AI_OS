import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './EvalDashboard.css';

// ── Types ──

interface Benchmark {
  id: string;
  name: string;
  type: string;
  description: string;
  prompts?: string[];
  prompts_json?: string;
}

interface EvalResult {
  model: string;
  response: string;
  duration_ms: number;
  with_state?: boolean;
  state_used?: string;
  id?: string;
}

interface JudgeResult {
  winner: string;
  judge_output: string;
}

interface RunResponse {
  results: EvalResult[];
  judge: JudgeResult | null;
  prompt: string;
  benchmark_type: string;
}

interface Comparison {
  id: string;
  prompt: string;
  winner: string;
  summary: string;
  judge_model: string;
  benchmark_type: string;
  created_at: string;
}

interface StructuredEval {
  name: string;
  description: string;
  defaults: Record<string, string | number>;
}

interface EvalCaseDetail {
  prompt?: string;
  query?: string;
  passed: boolean;
  response_preview?: string;
  // state_impact
  category?: string;
  state_markers_found?: string[];
  bare_markers_found?: string[];
  state_wins?: boolean;
  personalized?: boolean;
  response_state_preview?: string;
  response_bare_preview?: string;
  duration_state_ms?: number;
  duration_bare_ms?: number;
  // state_completeness
  thread_coverage?: number;
  threads_present?: string[];
  total_facts?: number;
  noise_ratio?: number;
  composite_score?: number;
  scores?: Record<string, number>;
  state_tokens?: number;
  // scoring_quality
  expected_top?: string;
  actual_top?: string;
  top_hit?: boolean;
  score_range?: number;
}

interface StructuredEvalResult {
  eval_name: string;
  status: string;
  score: number;
  total: number;
  passed: number;
  details: EvalCaseDetail[];
  config: Record<string, string | number>;
  run_id?: string;
  error?: string;
  // state_impact extras
  state_win_rate?: number;
  personalization_rate?: number;
  model_with_state?: string;
  model_bare?: string;
  // state_completeness extras
  avg_coverage?: number;
  avg_density?: number;
  avg_structure?: number;
  thread_fact_totals?: Record<string, number>;
  // scoring_quality extras
  avg_score_range?: number;
}

interface EvalRunRecord {
  id: string;
  eval_name: string;
  status: string;
  score: number;
  total: number;
  passed: number;
  model: string;
  created_at: string;
}

interface ComparisonMatrix {
  [evalName: string]: {
    [model: string]: {
      score: number;
      status: string;
      passed: number;
      total: number;
    };
  };
}

// ── Constants ──

const CATEGORY_META: Record<string, { icon: string; label: string }> = {
  structured:         { icon: '📊', label: 'Structured Evals' },
  state_vs_no_state:  { icon: '🧠', label: 'State vs No State' },
  ai_vs_ai:           { icon: '⚔️',  label: 'AI vs AI' },
  base_vs_finetuned:  { icon: '🔬', label: 'Base vs Finetuned' },
  adversarial:        { icon: '🛡️',  label: 'Adversarial' },
  custom:             { icon: '✏️',  label: 'Custom' },
};

const CATEGORY_ORDER = ['structured', 'state_vs_no_state', 'ai_vs_ai', 'base_vs_finetuned', 'adversarial', 'custom'];

// ── Component ──

export const EvalDashboard = () => {
  // State
  const [benchmarks, setBenchmarks] = useState<Benchmark[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState('structured');
  const [selectedModels, setSelectedModels] = useState<string[]>(['nola']);
  const [prompt, setPrompt] = useState('');
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<RunResponse | null>(null);
  const [comparisons, setComparisons] = useState<Comparison[]>([]);
  const [showEditor, setShowEditor] = useState(false);

  // Structured evals state
  const [structuredEvals, setStructuredEvals] = useState<StructuredEval[]>([]);
  const [structuredResults, setStructuredResults] = useState<StructuredEvalResult[]>([]);
  const [evalRuns, setEvalRuns] = useState<EvalRunRecord[]>([]);
  const [saveResults, setSaveResults] = useState(false);
  const [runningEval, setRunningEval] = useState<string | null>(null);
  const [expandedResult, setExpandedResult] = useState<string | null>(null);

  // Model comparison state
  const [evalModel, setEvalModel] = useState('nola');
  const [compareModels, setCompareModels] = useState<string[]>([]);
  const [comparisonMatrix, setComparisonMatrix] = useState<ComparisonMatrix | null>(null);
  const [runningComparison, setRunningComparison] = useState(false);
  const [showComparison, setShowComparison] = useState(false);

  // New benchmark form
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [newPrompts, setNewPrompts] = useState<string[]>(['']);

  // ── Fetch data ──

  const fetchBenchmarks = useCallback(async () => {
    try {
      const r = await fetch('/api/eval/benchmarks');
      const d = await r.json();
      setBenchmarks(d.benchmarks ?? []);
    } catch { setBenchmarks([]); }
  }, []);

  const fetchModels = useCallback(async () => {
    try {
      const r = await fetch('/api/eval/models');
      const d = await r.json();
      setModels(d.models ?? []);
    } catch { setModels(['nola']); }
  }, []);

  const fetchComparisons = useCallback(async () => {
    try {
      const params = new URLSearchParams({ benchmark_type: selectedCategory, limit: '20' });
      const r = await fetch(`/api/eval/comparisons?${params}`);
      const d = await r.json();
      setComparisons(d.comparisons ?? []);
    } catch { setComparisons([]); }
  }, [selectedCategory]);

  useEffect(() => { fetchBenchmarks(); fetchModels(); }, [fetchBenchmarks, fetchModels]);
  useEffect(() => { fetchComparisons(); }, [fetchComparisons]);

  // Structured evals fetchers
  const fetchStructuredEvals = useCallback(async () => {
    try {
      const r = await fetch('/api/eval/evals');
      const d = await r.json();
      setStructuredEvals(d.evals ?? []);
    } catch { setStructuredEvals([]); }
  }, []);

  const fetchEvalRuns = useCallback(async () => {
    try {
      const r = await fetch('/api/eval/runs?limit=20');
      const d = await r.json();
      setEvalRuns(d.runs ?? []);
    } catch { setEvalRuns([]); }
  }, []);

  useEffect(() => {
    if (selectedCategory === 'structured') {
      fetchStructuredEvals();
      fetchEvalRuns();
    }
  }, [selectedCategory, fetchStructuredEvals, fetchEvalRuns]);

  // Structured eval handlers
  const runStructuredEval = async (name: string) => {
    setRunningEval(name);
    try {
      const overrides: Record<string, string> = {};
      if (evalModel && evalModel !== 'nola') overrides.model = evalModel;
      const r = await fetch(`/api/eval/evals/${encodeURIComponent(name)}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ save: saveResults, overrides }),
      });
      const d: StructuredEvalResult = await r.json();
      setStructuredResults(prev => {
        const filtered = prev.filter(x => x.eval_name !== name);
        return [...filtered, d];
      });
      if (saveResults) fetchEvalRuns();
    } catch (e) {
      console.error(`Eval ${name} failed:`, e);
    } finally {
      setRunningEval(null);
    }
  };

  const runAllStructuredEvals = async () => {
    setRunningEval('all');
    try {
      const overrides: Record<string, string> = {};
      if (evalModel && evalModel !== 'nola') overrides.model = evalModel;
      const r = await fetch('/api/eval/evals/run-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ save: saveResults, overrides }),
      });
      const d = await r.json();
      setStructuredResults(d.results ?? []);
      if (saveResults) fetchEvalRuns();
    } catch (e) {
      console.error('Run all evals failed:', e);
    } finally {
      setRunningEval(null);
    }
  };

  const runModelComparison = async () => {
    if (compareModels.length < 2) return;
    setRunningComparison(true);
    try {
      const r = await fetch('/api/eval/evals/compare-all', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          eval_name: 'all',
          models: compareModels,
          save: saveResults,
        }),
      });
      const d = await r.json();
      setComparisonMatrix(d.matrix ?? null);
      setShowComparison(true);
    } catch (e) {
      console.error('Model comparison failed:', e);
    } finally {
      setRunningComparison(false);
    }
  };

  // ── Derived ──

  const categoryBenchmarks = benchmarks.filter(b => b.type === selectedCategory);
  const currentBenchmark = categoryBenchmarks[0];
  const presetPrompts = currentBenchmark?.prompts ?? [];
  const meta = CATEGORY_META[selectedCategory] ?? { icon: '📊', label: selectedCategory };

  // Group benchmarks count per type
  const countByType: Record<string, number> = {};
  for (const b of benchmarks) {
    countByType[b.type] = (countByType[b.type] ?? 0) + 1;
  }

  // ── Handlers ──

  const toggleModel = (m: string) => {
    setSelectedModels(prev =>
      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
    );
  };

  const runEval = async () => {
    if (!prompt.trim() || selectedModels.length === 0) return;
    setRunning(true);
    setLastRun(null);
    try {
      const r = await fetch('/api/eval/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          models: selectedModels,
          benchmark_type: selectedCategory,
          with_state: true,
          benchmark_id: currentBenchmark?.id ?? '',
        }),
      });
      const d: RunResponse = await r.json();
      setLastRun(d);
      fetchComparisons();
    } catch (e) {
      console.error('Eval run failed:', e);
    } finally {
      setRunning(false);
    }
  };

  const runStateComparison = async () => {
    if (!prompt.trim()) return;
    setRunning(true);
    setLastRun(null);
    try {
      const params = new URLSearchParams({ prompt: prompt.trim() });
      const r = await fetch(`/api/eval/run/state-comparison?${params}`, { method: 'POST' });
      const d = await r.json();
      // Adapt to RunResponse shape
      setLastRun({
        results: [
          { ...d.with_state, model: 'nola (with STATE)' },
          { ...d.without_state, model: 'nola (no STATE)' },
        ],
        judge: d.judge,
        prompt: prompt.trim(),
        benchmark_type: 'state_vs_no_state',
      });
      fetchComparisons();
    } catch (e) {
      console.error('State comparison failed:', e);
    } finally {
      setRunning(false);
    }
  };

  const saveBenchmark = async () => {
    const filtered = newPrompts.filter(p => p.trim());
    if (!newName.trim() || filtered.length === 0) return;
    try {
      await fetch('/api/eval/benchmarks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newName.trim(),
          type: selectedCategory,
          description: newDesc.trim(),
          prompts: filtered,
        }),
      });
      setNewName('');
      setNewDesc('');
      setNewPrompts(['']);
      setShowEditor(false);
      fetchBenchmarks();
    } catch (e) {
      console.error('Save benchmark failed:', e);
    }
  };

  const deleteBenchmark = async (id: string) => {
    try {
      await fetch(`/api/eval/benchmarks/${encodeURIComponent(id)}`, { method: 'DELETE' });
      fetchBenchmarks();
    } catch (e) {
      console.error('Delete benchmark failed:', e);
    }
  };

  // ── Render ──

  return (
    <div className="eval-dashboard">
      {/* Sidebar */}
      <nav className="eval-sidebar">
        <div className="eval-sidebar-header">
          <span className="icon">🎯</span>
          <h2>Eval Harness</h2>
        </div>

        <div className="eval-sidebar-section">Assessment Types</div>
        {CATEGORY_ORDER.map(cat => {
          const m = CATEGORY_META[cat];
          return (
            <button
              key={cat}
              className={`eval-cat-btn ${selectedCategory === cat ? 'active' : ''}`}
              onClick={() => { setSelectedCategory(cat); setLastRun(null); }}
            >
              <span className="icon">{m.icon}</span>
              <span className="name">{m.label}</span>
              {(countByType[cat] ?? 0) > 0 && (
                <span className="count">{countByType[cat]}</span>
              )}
            </button>
          );
        })}

        <div className="eval-sidebar-footer">
          <Link to="/">← Back to App</Link>
        </div>
      </nav>

      {/* Main */}
      <div className="eval-main">
        <h2>{meta.icon} {meta.label}</h2>
        <p className="eval-desc">
          {selectedCategory === 'structured'
            ? 'Run structured evaluations that test specific agent capabilities.'
            : (currentBenchmark?.description ?? `Run ${meta.label.toLowerCase()} evaluations`)}
        </p>

        {/* ── Structured Evals Section ── */}
        {selectedCategory === 'structured' && (
          <>
            {/* Model Selector + Controls */}
            <div className="eval-runner">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>Evaluations</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)' }}>Model:</label>
                    <select
                      value={evalModel}
                      onChange={e => setEvalModel(e.target.value)}
                      style={{
                        background: 'var(--bg)', border: '1px solid var(--border)',
                        borderRadius: '0.4rem', color: 'var(--text)', fontSize: '0.8rem',
                        padding: '0.3rem 0.5rem', cursor: 'pointer',
                      }}
                    >
                      {models.map(m => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={saveResults}
                      onChange={e => setSaveResults(e.target.checked)}
                    />
                    Save
                  </label>
                  <button
                    className="eval-run-btn"
                    style={{ padding: '0.4rem 1rem', fontSize: '0.8rem' }}
                    onClick={runAllStructuredEvals}
                    disabled={runningEval !== null}
                  >
                    {runningEval === 'all' ? 'Running All...' : 'Run All'}
                  </button>
                </div>
              </div>

              {/* Eval cards */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {structuredEvals.map(ev => {
                  const result = structuredResults.find(r => r.eval_name === ev.name);
                  const isRunning = runningEval === ev.name || runningEval === 'all';
                  const isExpanded = expandedResult === ev.name;
                  const scorePct = result ? Math.round(result.score * 100) : 0;
                  return (
                    <div key={ev.name} className="eval-structured-card">
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{ev.name.replace(/_/g, ' ')}</div>
                          <div style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{ev.description}</div>
                        </div>
                        {result && (
                          <div
                            style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', flexShrink: 0 }}
                            onClick={() => setExpandedResult(isExpanded ? null : ev.name)}
                          >
                            {/* Score bar */}
                            <div className="eval-score-bar-container">
                              <div
                                className={`eval-score-bar-fill ${result.status === 'passed' ? 'pass' : result.status === 'error' ? 'error' : 'fail'}`}
                                style={{ width: `${scorePct}%` }}
                              />
                              <span className="eval-score-bar-label">{scorePct}%</span>
                            </div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                              {result.passed}/{result.total}
                            </span>
                          </div>
                        )}
                        <button
                          className="eval-run-btn"
                          style={{ padding: '0.4rem 1rem', fontSize: '0.8rem', flexShrink: 0 }}
                          onClick={() => runStructuredEval(ev.name)}
                          disabled={isRunning}
                        >
                          {isRunning ? '...' : 'Run'}
                        </button>
                      </div>

                      {/* Extra metrics for specific evals */}
                      {isExpanded && result && (
                        <div className="eval-expanded-section">
                          {/* state_impact extras */}
                          {result.state_win_rate !== undefined && (
                            <div className="eval-extra-metrics">
                              <div className="eval-metric-pill">
                                <span className="label">STATE wins</span>
                                <span className="value">{Math.round(result.state_win_rate * 100)}%</span>
                              </div>
                              <div className="eval-metric-pill">
                                <span className="label">Personalized</span>
                                <span className="value">{Math.round((result.personalization_rate ?? 0) * 100)}%</span>
                              </div>
                              <div className="eval-metric-pill">
                                <span className="label">vs</span>
                                <span className="value" style={{ fontSize: '0.7rem' }}>{result.model_bare}</span>
                              </div>
                            </div>
                          )}
                          {/* state_completeness extras */}
                          {result.avg_coverage !== undefined && (
                            <div className="eval-extra-metrics">
                              <div className="eval-metric-pill">
                                <span className="label">Coverage</span>
                                <span className="value">{Math.round(result.avg_coverage * 100)}%</span>
                              </div>
                              <div className="eval-metric-pill">
                                <span className="label">Density</span>
                                <span className="value">{Math.round((result.avg_density ?? 0) * 100)}%</span>
                              </div>
                              <div className="eval-metric-pill">
                                <span className="label">Structure</span>
                                <span className="value">{Math.round((result.avg_structure ?? 0) * 100)}%</span>
                              </div>
                              {result.thread_fact_totals && (
                                <div style={{ width: '100%', marginTop: '0.5rem' }}>
                                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Facts by thread:</div>
                                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                    {Object.entries(result.thread_fact_totals).sort((a, b) => b[1] - a[1]).map(([t, c]) => (
                                      <span key={t} className="eval-thread-fact-chip">{t}: {c}</span>
                                    ))}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                          {/* scoring_quality extras */}
                          {result.avg_score_range !== undefined && (
                            <div className="eval-extra-metrics">
                              <div className="eval-metric-pill">
                                <span className="label">Avg range</span>
                                <span className="value">{result.avg_score_range}</span>
                              </div>
                            </div>
                          )}
                          {/* Detail rows */}
                          {result.details?.map((d, i) => (
                            <div key={i} className="eval-detail-row">
                              <span className={`eval-detail-status ${d.passed ? 'pass' : 'fail'}`}>
                                {d.passed ? '✓' : '✗'}
                              </span>
                              <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ fontSize: '0.8rem' }}>{d.prompt || d.query}</div>
                                {/* scoring_quality: show score breakdown */}
                                {d.scores && (
                                  <div className="eval-detail-scores">
                                    {Object.entries(d.scores).sort((a, b) => b[1] - a[1]).map(([t, s]) => (
                                      <span key={t} className={`eval-score-chip ${t === d.expected_top ? 'expected' : ''} ${t === d.actual_top ? 'actual' : ''}`}>
                                        {t}: {s}
                                      </span>
                                    ))}
                                  </div>
                                )}
                                {/* state_impact: show A/B preview */}
                                {d.response_state_preview && (
                                  <div className="eval-ab-preview">
                                    <div className="eval-ab-col">
                                      <div className="eval-ab-label">With STATE {d.state_wins ? '✓' : ''}</div>
                                      <div className="eval-ab-text">{d.response_state_preview?.slice(0, 150)}</div>
                                      {d.state_markers_found && d.state_markers_found.length > 0 && (
                                        <div className="eval-ab-markers">
                                          {d.state_markers_found.map((m, j) => <span key={j} className="eval-marker-chip pass">{m}</span>)}
                                        </div>
                                      )}
                                    </div>
                                    <div className="eval-ab-col">
                                      <div className="eval-ab-label">Bare model</div>
                                      <div className="eval-ab-text">{d.response_bare_preview?.slice(0, 150)}</div>
                                      {d.bare_markers_found && d.bare_markers_found.length > 0 && (
                                        <div className="eval-ab-markers">
                                          {d.bare_markers_found.map((m, j) => <span key={j} className="eval-marker-chip">{m}</span>)}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                {/* state_completeness: show thread coverage */}
                                {d.thread_coverage !== undefined && (
                                  <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.3rem', flexWrap: 'wrap', fontSize: '0.7rem' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>
                                      {d.total_facts} facts · {Math.round(d.thread_coverage * 100)}% coverage · {d.state_tokens} tokens
                                    </span>
                                    {d.threads_present?.map(t => (
                                      <span key={t} className="eval-thread-fact-chip">{t}</span>
                                    ))}
                                  </div>
                                )}
                                {/* Default: show response preview */}
                                {!d.response_state_preview && !d.scores && d.thread_coverage === undefined && d.response_preview && (
                                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginTop: '0.2rem' }}>
                                    {d.response_preview.slice(0, 120)}
                                  </div>
                                )}
                              </div>
                              {d.category && (
                                <span className="eval-category-chip">{d.category}</span>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Aggregate summary with visual bars */}
            {structuredResults.length > 0 && (
              <div className="eval-results" style={{ marginTop: '1rem' }}>
                <h3>Summary — {evalModel}</h3>
                <div className="eval-summary-grid">
                  {structuredResults.map(r => (
                    <div key={r.eval_name} className="eval-summary-card">
                      <div className="eval-summary-name">{r.eval_name.replace(/_/g, ' ')}</div>
                      <div className={`eval-summary-score ${r.status === 'passed' ? 'pass' : r.status === 'error' ? 'error' : 'fail'}`}>
                        {Math.round(r.score * 100)}%
                      </div>
                      <div className="eval-score-bar-container" style={{ width: '100%', height: '6px' }}>
                        <div
                          className={`eval-score-bar-fill ${r.status === 'passed' ? 'pass' : r.status === 'error' ? 'error' : 'fail'}`}
                          style={{ width: `${Math.round(r.score * 100)}%` }}
                        />
                      </div>
                      <div className="eval-summary-detail">{r.passed}/{r.total}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Multi-model comparison section */}
            <div className="eval-runner" style={{ marginTop: '1rem' }}>
              <h3 style={{ margin: '0 0 0.75rem' }}>Multi-Model Comparison</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', margin: '0 0 0.75rem' }}>
                Run all evals across multiple models to compare capabilities.
              </p>
              <div className="eval-model-select" style={{ marginBottom: '0.75rem' }}>
                <label>Models:</label>
                {models.filter(m => m.endsWith('-cloud') || m.startsWith('nola')).map(m => (
                  <button
                    key={m}
                    className={`eval-model-chip ${compareModels.includes(m) ? 'selected' : ''}`}
                    onClick={() => setCompareModels(prev =>
                      prev.includes(m) ? prev.filter(x => x !== m) : [...prev, m]
                    )}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <button
                className="eval-run-btn"
                style={{ padding: '0.5rem 1.25rem' }}
                onClick={runModelComparison}
                disabled={runningComparison || compareModels.length < 2}
              >
                {runningComparison ? 'Running comparison...' : `Compare ${compareModels.length} Models`}
              </button>

              {/* Comparison Matrix */}
              {showComparison && comparisonMatrix && (
                <div style={{ marginTop: '1rem', overflowX: 'auto' }}>
                  <table className="eval-matrix-table">
                    <thead>
                      <tr>
                        <th>Eval</th>
                        {compareModels.map(m => <th key={m}>{m.replace('nola+', '')}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(comparisonMatrix).map(([evalName, modelResults]) => (
                        <tr key={evalName}>
                          <td style={{ fontWeight: 600, fontSize: '0.8rem' }}>{evalName.replace(/_/g, ' ')}</td>
                          {compareModels.map(model => {
                            const cell = modelResults[model];
                            if (!cell) return <td key={model}>—</td>;
                            const pct = Math.round(cell.score * 100);
                            return (
                              <td key={model}>
                                <div className="eval-matrix-cell">
                                  <div className="eval-score-bar-container" style={{ width: '60px', height: '8px' }}>
                                    <div
                                      className={`eval-score-bar-fill ${cell.status === 'passed' ? 'pass' : cell.status === 'error' ? 'error' : 'fail'}`}
                                      style={{ width: `${pct}%` }}
                                    />
                                  </div>
                                  <span className={`eval-matrix-score ${cell.status === 'passed' ? 'pass' : 'fail'}`}>
                                    {pct}%
                                  </span>
                                </div>
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                      {/* Averages row */}
                      <tr className="eval-matrix-avg-row">
                        <td style={{ fontWeight: 700, fontSize: '0.8rem' }}>Average</td>
                        {compareModels.map(model => {
                          const scores = Object.values(comparisonMatrix).map(er => er[model]?.score ?? 0);
                          const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
                          return (
                            <td key={model}>
                              <span className="eval-matrix-avg">{Math.round(avg * 100)}%</span>
                            </td>
                          );
                        })}
                      </tr>
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            {/* Run history */}
            {evalRuns.length > 0 && (
              <div className="eval-history" style={{ marginTop: '1rem' }}>
                <h3>Saved Runs</h3>
                <table className="eval-history-table">
                  <thead>
                    <tr>
                      <th>Eval</th>
                      <th>Status</th>
                      <th>Score</th>
                      <th>Model</th>
                      <th>Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {evalRuns.map(run => (
                      <tr key={run.id}>
                        <td>{run.eval_name}</td>
                        <td>
                          <span className={`eval-response-badge ${run.status === 'pass' ? 'state' : run.status === 'fail' ? 'winner-badge' : 'time'}`}>
                            {run.status}
                          </span>
                        </td>
                        <td>{run.passed}/{run.total} ({Math.round((run.score || 0) * 100)}%)</td>
                        <td>{run.model}</td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                          {new Date(run.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {structuredEvals.length === 0 && structuredResults.length === 0 && (
              <div className="eval-empty">
                <div className="icon">📊</div>
                <p>Loading structured evaluations...</p>
              </div>
            )}
          </>
        )}

        {/* ── Ad-hoc Prompt Runner (non-structured categories) ── */}
        {selectedCategory !== 'structured' && (
        <>
        <div className="eval-runner">
          <h3>Run Evaluation</h3>

          <div className="eval-prompt-area">
            <textarea
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
              placeholder="Enter a prompt to evaluate..."
            />
            {presetPrompts.length > 0 && (
              <div className="eval-preset-prompts">
                {presetPrompts.map((p, i) => (
                  <button key={i} className="eval-preset-btn" onClick={() => setPrompt(p)} title={p}>
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Model chips — hide for state_vs_no_state (auto-selects Nola) */}
          {selectedCategory !== 'state_vs_no_state' && (
            <div className="eval-model-select">
              <label>Models:</label>
              {models.map(m => (
                <button
                  key={m}
                  className={`eval-model-chip ${selectedModels.includes(m) ? 'selected' : ''}`}
                  onClick={() => toggleModel(m)}
                >
                  {m}
                </button>
              ))}
            </div>
          )}

          <div className="eval-run-row">
            {selectedCategory === 'state_vs_no_state' ? (
              <button
                className="eval-run-btn"
                onClick={runStateComparison}
                disabled={running || !prompt.trim()}
              >
                {running ? 'Running...' : 'Compare State vs No State'}
              </button>
            ) : (
              <button
                className="eval-run-btn"
                onClick={runEval}
                disabled={running || !prompt.trim() || selectedModels.length === 0}
              >
                {running ? 'Running...' : `Run Against ${selectedModels.length} Model${selectedModels.length !== 1 ? 's' : ''}`}
              </button>
            )}
            {running && <span className="eval-running">⏳ Generating responses and running judge...</span>}
          </div>
        </div>

        {/* ── Last Run Results ── */}
        {lastRun && (
          <div className="eval-results">
            <h3>Results — "{lastRun.prompt.slice(0, 80)}{lastRun.prompt.length > 80 ? '...' : ''}"</h3>

            <div className="eval-comparison-grid">
              {lastRun.results.map((r, i) => {
                const isWinner = lastRun.judge?.winner === r.model;
                return (
                  <div key={i} className={`eval-response-card ${isWinner ? 'winner' : ''}`}>
                    <div className="eval-response-header">
                      <span className="eval-response-model">{r.model}</span>
                      <div className="eval-response-meta">
                        {r.with_state && <span className="eval-response-badge state">STATE</span>}
                        {isWinner && <span className="eval-response-badge winner-badge">WINNER</span>}
                        <span className="eval-response-badge time">{r.duration_ms}ms</span>
                      </div>
                    </div>
                    <div className="eval-response-body">{r.response}</div>
                  </div>
                );
              })}
            </div>

            {lastRun.judge && (
              <div className="eval-judge">
                <h4>🧑‍⚖️ Judge Output ({lastRun.judge.winner && `Winner: ${lastRun.judge.winner}`})</h4>
                <pre>{lastRun.judge.judge_output}</pre>
              </div>
            )}
          </div>
        )}

        {/* ── Benchmark Editor (for custom category or any) ── */}
        {showEditor ? (
          <div className="eval-benchmark-editor">
            <h3>Add Benchmark</h3>
            <div className="eval-benchmark-form">
              <input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="Benchmark name"
              />
              <input
                value={newDesc}
                onChange={e => setNewDesc(e.target.value)}
                placeholder="Description (optional)"
              />
              <div className="eval-prompt-list">
                {newPrompts.map((p, i) => (
                  <div key={i} className="eval-prompt-row">
                    <input
                      value={p}
                      onChange={e => {
                        const next = [...newPrompts];
                        next[i] = e.target.value;
                        setNewPrompts(next);
                      }}
                      placeholder={`Prompt ${i + 1}`}
                    />
                    {newPrompts.length > 1 && (
                      <button className="eval-remove-btn" onClick={() => setNewPrompts(newPrompts.filter((_, j) => j !== i))}>×</button>
                    )}
                  </div>
                ))}
                <button className="eval-add-prompt-btn" onClick={() => setNewPrompts([...newPrompts, ''])}>
                  + Add Prompt
                </button>
              </div>
              <div className="eval-benchmark-actions">
                <button className="eval-save-btn" onClick={saveBenchmark}>Save Benchmark</button>
                <button className="eval-delete-btn" onClick={() => setShowEditor(false)}>Cancel</button>
              </div>
            </div>
          </div>
        ) : (
          <button className="eval-add-prompt-btn" onClick={() => setShowEditor(true)} style={{ marginBottom: '1.5rem' }}>
            + Add Custom Benchmark
          </button>
        )}

        {/* ── Existing Benchmarks ── */}
        {categoryBenchmarks.length > 0 && (
          <div className="eval-benchmark-editor" style={{ marginBottom: '1.5rem' }}>
            <h3>Benchmarks in {meta.label}</h3>
            {categoryBenchmarks.map(b => (
              <div key={b.id} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
                <strong style={{ flex: 1, fontSize: '0.85rem' }}>{b.name}</strong>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{b.prompts?.length ?? 0} prompts</span>
                <button className="eval-delete-btn" onClick={() => deleteBenchmark(b.id)}>Delete</button>
              </div>
            ))}
          </div>
        )}

        {/* ── History ── */}
        {comparisons.length > 0 ? (
          <div className="eval-history">
            <h3>Past Comparisons</h3>
            <table className="eval-history-table">
              <thead>
                <tr>
                  <th>Prompt</th>
                  <th>Winner</th>
                  <th>Judge</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {comparisons.map(c => (
                  <tr key={c.id}>
                    <td className="eval-prompt-cell" title={c.prompt}>{c.prompt}</td>
                    <td className="eval-winner-cell">{c.winner || '—'}</td>
                    <td>{c.judge_model}</td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                      {new Date(c.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="eval-empty">
            <div className="icon">🎯</div>
            <p>No comparisons yet. Run an evaluation above to get started.</p>
          </div>
        )}
        </>
        )}
      </div>
    </div>
  );
};
