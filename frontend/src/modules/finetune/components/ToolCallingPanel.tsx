import React, { useState, useEffect, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────── */
interface ToolCallInfo {
  tool: string;
  action: string;
  params?: Record<string, string>;
}

interface CaseDetail {
  label: string;
  prompt: string;
  passed: boolean;
  mode: string;
  response?: string;
  blocks_found?: number;
  tools_called?: ToolCallInfo[];
  tool_match?: boolean;
  action_match?: boolean;
  all_valid?: boolean;
  expected_no_tools?: boolean;
  duration_ms?: number;
  // loop fields
  rounds?: { round: number; response?: string; blocks_found?: number; tools?: ToolCallInfo[] }[];
  total_rounds?: number;
  total_tool_calls?: number;
  finished_naturally?: boolean;
  error?: string;
}

interface EvalResult {
  eval_name: string;
  status: string;
  score: number;
  total: number;
  passed: number;
  mode: string;
  model: string;
  details: CaseDetail[];
  error?: string;
}

/* ── Styles ────────────────────────────────────────── */
const S = {
  panel: {
    padding: '24px 28px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
    overflowY: 'auto' as const,
    flex: 1,
    minWidth: 0,
  } as React.CSSProperties,

  header: {
    display: 'flex', alignItems: 'center', gap: 16,
    marginBottom: 20, flexWrap: 'wrap' as const,
  } as React.CSSProperties,

  title: { fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em' } as React.CSSProperties,

  controls: {
    display: 'flex', gap: 12, alignItems: 'center',
    marginBottom: 20, flexWrap: 'wrap' as const,
  } as React.CSSProperties,

  select: {
    background: 'var(--bg-secondary, #1a1a2e)',
    color: 'var(--text-primary, #e0e0e0)',
    border: '1px solid var(--border, #333)',
    borderRadius: 8, padding: '8px 12px', fontSize: 14,
    minWidth: 200,
  } as React.CSSProperties,

  btn: {
    background: 'var(--accent, #6c63ff)',
    color: '#fff', border: 'none', borderRadius: 8,
    padding: '8px 20px', fontSize: 14, fontWeight: 600,
    cursor: 'pointer',
  } as React.CSSProperties,

  btnDisabled: {
    opacity: 0.5, cursor: 'not-allowed',
  } as React.CSSProperties,

  modeToggle: {
    display: 'flex', gap: 0, borderRadius: 8, overflow: 'hidden',
    border: '1px solid var(--border, #333)',
  } as React.CSSProperties,

  modeBtn: (active: boolean) => ({
    background: active ? 'var(--accent, #6c63ff)' : 'var(--bg-secondary, #1a1a2e)',
    color: active ? '#fff' : 'var(--text-muted, #888)',
    border: 'none', padding: '8px 16px', fontSize: 13, fontWeight: 600,
    cursor: 'pointer',
  }) as React.CSSProperties,

  scoreBar: {
    display: 'flex', alignItems: 'center', gap: 16,
    marginBottom: 20, padding: '16px 20px',
    background: 'var(--bg-secondary, #1a1a2e)',
    borderRadius: 12,
  } as React.CSSProperties,

  bigScore: { fontSize: 36, fontWeight: 800 } as React.CSSProperties,

  progressOuter: {
    flex: 1, height: 10, borderRadius: 6,
    background: 'var(--bg-tertiary, #111)',
    overflow: 'hidden',
  } as React.CSSProperties,

  progressInner: (pct: number, color: string) => ({
    height: '100%', width: `${pct}%`,
    background: color, borderRadius: 6,
    transition: 'width 0.4s ease',
  }) as React.CSSProperties,

  card: (passed: boolean) => ({
    background: 'var(--bg-secondary, #1a1a2e)',
    borderRadius: 12, padding: '16px 20px',
    marginBottom: 12,
    borderLeft: `4px solid ${passed ? '#4caf50' : '#f44336'}`,
  }) as React.CSSProperties,

  cardHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    marginBottom: 8,
  } as React.CSSProperties,

  label: { fontSize: 15, fontWeight: 700 } as React.CSSProperties,

  badge: (passed: boolean) => ({
    fontSize: 11, fontWeight: 700, padding: '3px 10px',
    borderRadius: 20,
    background: passed ? 'rgba(76,175,80,0.15)' : 'rgba(244,67,54,0.15)',
    color: passed ? '#4caf50' : '#f44336',
  }) as React.CSSProperties,

  prompt: {
    fontSize: 13, color: 'var(--text-muted, #aaa)',
    marginBottom: 8, fontStyle: 'italic',
  } as React.CSSProperties,

  meta: {
    display: 'flex', gap: 16, flexWrap: 'wrap' as const,
    fontSize: 12, color: 'var(--text-muted, #888)',
    marginBottom: 8,
  } as React.CSSProperties,

  toolPill: {
    display: 'inline-block', fontSize: 12, fontWeight: 600,
    background: 'rgba(108,99,255,0.15)', color: 'var(--accent, #6c63ff)',
    borderRadius: 6, padding: '2px 8px', marginRight: 6, marginBottom: 4,
  } as React.CSSProperties,

  response: {
    fontSize: 12, color: 'var(--text-secondary, #ccc)',
    background: 'var(--bg-tertiary, #111)',
    borderRadius: 8, padding: '10px 12px',
    whiteSpace: 'pre-wrap' as const,
    maxHeight: 200, overflowY: 'auto' as const,
    fontFamily: '"SF Mono", Monaco, "Cascadia Mono", monospace',
  } as React.CSSProperties,

  roundTag: {
    display: 'inline-block', fontSize: 11, fontWeight: 700,
    background: 'rgba(255,193,7,0.15)', color: '#ffc107',
    borderRadius: 6, padding: '2px 8px', marginRight: 6,
  } as React.CSSProperties,

  statRow: {
    display: 'flex', gap: 16, flexWrap: 'wrap' as const,
    marginBottom: 16,
  } as React.CSSProperties,

  stat: {
    background: 'var(--bg-secondary, #1a1a2e)',
    borderRadius: 10, padding: '12px 18px',
    display: 'flex', flexDirection: 'column' as const, gap: 2,
    minWidth: 110,
  } as React.CSSProperties,

  statLabel: { fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' as const, letterSpacing: '0.04em' } as React.CSSProperties,
  statValue: { fontSize: 20, fontWeight: 700 } as React.CSSProperties,
};


/* ── Component ─────────────────────────────────────── */
export const ToolCallingPanel: React.FC = () => {
  const [models, setModels] = useState<string[]>([]);
  const [model, setModel] = useState('kimi-k2:1t-cloud');
  const [mode, setMode] = useState<'single_pass' | 'loop'>('single_pass');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<EvalResult | null>(null);

  // Fetch available models
  useEffect(() => {
    fetch('/api/eval/models')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.models) setModels(d.models); })
      .catch(() => {});
  }, []);

  const runEval = useCallback(async () => {
    setRunning(true);
    setResult(null);
    try {
      const res = await fetch('/api/eval/evals/tool_calling_direct/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ save: false, overrides: { model, mode } }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
      }
    } catch { /* ignore */ } finally {
      setRunning(false);
    }
  }, [model, mode]);

  const scoreColor = (s: number) =>
    s >= 0.8 ? '#4caf50' : s >= 0.5 ? '#ffc107' : '#f44336';

  return (
    <div style={S.panel}>
      {/* Header */}
      <div style={S.header}>
        <span style={{ fontSize: 28 }}>🔧</span>
        <span style={S.title}>Tool Calling Eval</span>
      </div>

      {/* Controls */}
      <div style={S.controls}>
        <select
          style={S.select}
          value={model}
          onChange={e => setModel(e.target.value)}
        >
          {models.length > 0 ? models.map(m => (
            <option key={m} value={m}>{m}</option>
          )) : (
            <option value="kimi-k2:1t-cloud">kimi-k2:1t-cloud</option>
          )}
        </select>

        <div style={S.modeToggle}>
          <button
            style={S.modeBtn(mode === 'single_pass')}
            onClick={() => setMode('single_pass')}
          >
            Single Pass
          </button>
          <button
            style={S.modeBtn(mode === 'loop')}
            onClick={() => setMode('loop')}
          >
            Loop (multi-round)
          </button>
        </div>

        <button
          style={{ ...S.btn, ...(running ? S.btnDisabled : {}) }}
          disabled={running}
          onClick={runEval}
        >
          {running ? 'Running...' : 'Run Eval'}
        </button>
      </div>

      {/* Description */}
      <p style={{ fontSize: 13, color: 'var(--text-muted, #888)', marginBottom: 20 }}>
        {mode === 'single_pass'
          ? 'Single pass: model gets one shot to produce valid :::execute blocks.'
          : 'Loop: simulates tool→result→continue rounds (up to 3). Tests if the model adapts to results.'}
      </p>

      {/* Score bar */}
      {result && !result.error && (
        <>
          <div style={S.scoreBar}>
            <span style={{ ...S.bigScore, color: scoreColor(result.score) }}>
              {Math.round(result.score * 100)}%
            </span>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, marginBottom: 6, color: 'var(--text-muted)' }}>
                {result.passed}/{result.total} passed · {result.model} · {result.mode}
              </div>
              <div style={S.progressOuter}>
                <div style={S.progressInner(result.score * 100, scoreColor(result.score))} />
              </div>
            </div>
            <span style={{
              ...S.badge(result.status === 'passed'),
              fontSize: 14, padding: '6px 16px',
            }}>
              {result.status.toUpperCase()}
            </span>
          </div>

          {/* Stats */}
          <div style={S.statRow}>
            <div style={S.stat}>
              <span style={S.statLabel}>Score</span>
              <span style={S.statValue}>{result.score}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Passed</span>
              <span style={{ ...S.statValue, color: '#4caf50' }}>{result.passed}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Failed</span>
              <span style={{ ...S.statValue, color: '#f44336' }}>{result.total - result.passed}</span>
            </div>
            <div style={S.stat}>
              <span style={S.statLabel}>Mode</span>
              <span style={S.statValue}>{result.mode === 'single_pass' ? 'Single' : 'Loop'}</span>
            </div>
          </div>

          {/* Test case cards */}
          {result.details.map((d, i) => (
            <TestCaseCard key={i} detail={d} />
          ))}
        </>
      )}

      {result?.error && (
        <div style={{ ...S.card(false), color: '#f44336' }}>
          Error: {result.error}
        </div>
      )}
    </div>
  );
};


/* ── Test Case Card ────────────────────────────────── */
const TestCaseCard: React.FC<{ detail: CaseDetail }> = ({ detail: d }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div style={S.card(d.passed)}>
      <div style={S.cardHeader}>
        <div>
          <span style={S.label}>{d.label}</span>
          {d.duration_ms != null && (
            <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 12 }}>
              {d.duration_ms}ms
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={S.badge(d.passed)}>{d.passed ? 'PASS' : 'FAIL'}</span>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none', border: 'none', color: 'var(--text-muted)',
              cursor: 'pointer', fontSize: 16,
            }}
          >
            {expanded ? '▾' : '▸'}
          </button>
        </div>
      </div>

      <div style={S.prompt}>"{d.prompt}"</div>

      {/* Meta info */}
      <div style={S.meta}>
        {d.expected_no_tools && <span>No tools expected</span>}
        {d.blocks_found != null && <span>{d.blocks_found} block(s)</span>}
        {d.tool_match != null && (
          <span style={{ color: d.tool_match ? '#4caf50' : '#f44336' }}>
            tool: {d.tool_match ? '✓' : '✗'}
          </span>
        )}
        {d.action_match != null && (
          <span style={{ color: d.action_match ? '#4caf50' : '#f44336' }}>
            action: {d.action_match ? '✓' : '✗'}
          </span>
        )}
        {d.total_rounds != null && <span>{d.total_rounds} round(s)</span>}
        {d.finished_naturally != null && (
          <span style={{ color: d.finished_naturally ? '#4caf50' : '#ffc107' }}>
            {d.finished_naturally ? 'finished naturally' : 'hit round limit'}
          </span>
        )}
      </div>

      {/* Tool pills */}
      {d.tools_called && d.tools_called.length > 0 && (
        <div style={{ marginBottom: 8 }}>
          {d.tools_called.map((t, j) => (
            <span key={j} style={S.toolPill}>{t.tool}.{t.action}</span>
          ))}
        </div>
      )}

      {/* Expanded: rounds (loop) or response (single) */}
      {expanded && (
        <div>
          {d.rounds ? (
            d.rounds.map((r, j) => (
              <div key={j} style={{ marginBottom: 8 }}>
                <span style={S.roundTag}>Round {r.round}</span>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                  {r.blocks_found ?? 0} block(s)
                </span>
                {r.tools && r.tools.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    {r.tools.map((t, k) => (
                      <span key={k} style={S.toolPill}>{t.tool}.{t.action}</span>
                    ))}
                  </div>
                )}
                {r.response && <div style={{ ...S.response, marginTop: 6 }}>{r.response}</div>}
              </div>
            ))
          ) : d.response ? (
            <div style={S.response}>{d.response}</div>
          ) : null}
        </div>
      )}
    </div>
  );
};
