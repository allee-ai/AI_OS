import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/* ── Types ───────────────────────────────────────────── */

interface SectionInfo {
  description: string;
  examples: number;
}

interface ModuleStats {
  examples?: number;
  concepts?: number;
  pairs?: number;
  facts?: number;
  tools?: number;
  turns?: number;
  error?: string;
  [key: string]: unknown;
}

interface FTModule {
  name: string;
  enabled: boolean;
  stats: ModuleStats;
}

interface Sample {
  messages: { role: string; content: string }[];
  metadata?: { section?: string; [k: string]: unknown };
}

interface AdapterStatus {
  status: string;
  active_model?: string;
  base_model?: string;
}

/* ── Helpers ─────────────────────────────────────────── */

function statCount(stats: ModuleStats): number {
  if (stats.error) return 0;
  return stats.examples ?? stats.concepts ?? stats.pairs ?? stats.facts ?? stats.tools ?? stats.turns ?? 0;
}

function truncate(s: string, max = 160): string {
  return s.length > max ? s.slice(0, max) + '…' : s;
}

/* ── Section metadata ────────────────────────────────── */
const SECTION_ICONS: Record<string, string> = {
  data: '💾',
  api: '🌐',
  cli: '⌨️',
  schema: '🗃️',
  reasoning: '🧩',
  generated: '🤖',
  approved: '✅',
};

const SECTION_LABELS: Record<string, string> = {
  data: 'Data',
  api: 'API Endpoints',
  cli: 'CLI Commands',
  schema: 'Schema',
  reasoning: 'Reasoning Examples',
  generated: 'Generated',
  approved: 'Approved',
};

const MODULE_ICONS: Record<string, string> = {
  linking_core: '🔗',
  identity: '🪞',
  philosophy: '🧠',
  log: '📝',
  reflex: '⚡',
  form: '🛠️',
  chat: '💬',
  docs: '📚',
};

const MODULE_DESC: Record<string, string> = {
  linking_core: 'Concept links & Hebbian spread activation',
  identity: 'Profile facts, names, self-model',
  philosophy: 'Worldview & reasoning patterns',
  log: 'System events, memory, observations',
  reflex: 'Feed→tool trigger automations',
  form: 'Tool registry & usage patterns',
  chat: 'Chat sessions & conversations',
  docs: 'Documentation & architecture knowledge',
};

/* ── Styles ──────────────────────────────────────────── */
const S = {
  panel: {
    padding: '28px 32px',
    flex: 1,
    minWidth: 0,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
    overflowY: 'auto' as const,
    height: '100vh',
  } as React.CSSProperties,
  empty: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'center',
    justifyContent: 'center',
    height: '70vh',
    color: 'var(--text-muted)',
    gap: 12,
  } as React.CSSProperties,
  emptyIcon: { fontSize: 48, opacity: 0.3 } as React.CSSProperties,
  emptyText: { fontSize: 15 } as React.CSSProperties,

  /* header */
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  } as React.CSSProperties,
  moduleTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--text)',
  } as React.CSSProperties,
  moduleDesc: {
    fontSize: 13,
    color: 'var(--text-muted)',
    marginBottom: 24,
  } as React.CSSProperties,
  enableToggle: (on: boolean) => ({
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 12,
    color: on ? 'var(--success, #10b981)' : 'var(--text-muted)',
    cursor: 'pointer',
    background: 'none',
    border: 'none',
    fontWeight: 600,
  }) as React.CSSProperties,
  toggleTrack: (on: boolean) => ({
    width: 38,
    height: 20,
    borderRadius: 10,
    background: on ? 'var(--success, #10b981)' : 'var(--bg-tertiary, #444)',
    position: 'relative' as const,
    transition: 'background .2s',
  }) as React.CSSProperties,
  toggleDot: (on: boolean) => ({
    position: 'absolute' as const,
    top: 3,
    left: on ? 20 : 3,
    width: 14,
    height: 14,
    borderRadius: '50%',
    background: '#fff',
    transition: 'left .2s',
  }) as React.CSSProperties,

  /* sections grid */
  sGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
    gap: 14,
    marginBottom: 28,
  } as React.CSSProperties,
  sCard: (active: boolean) => ({
    background: 'var(--surface)',
    border: `2px solid ${active ? 'var(--primary, #7c3aed)' : 'var(--border)'}`,
    borderRadius: 10,
    padding: '16px 18px',
    cursor: 'pointer',
    transition: 'border-color .2s, opacity .2s',
    opacity: active ? 1 : 0.6,
  }) as React.CSSProperties,
  sCardTop: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  } as React.CSSProperties,
  sCardLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text)',
  } as React.CSSProperties,
  sCardCount: {
    fontSize: 22,
    fontWeight: 700,
    color: 'var(--primary, #7c3aed)',
    marginBottom: 2,
  } as React.CSSProperties,
  sCardDesc: {
    fontSize: 11,
    color: 'var(--text-muted)',
  } as React.CSSProperties,
  checkbox: (on: boolean) => ({
    width: 18,
    height: 18,
    borderRadius: 4,
    border: `2px solid ${on ? 'var(--primary, #7c3aed)' : 'var(--border)'}`,
    background: on ? 'var(--primary, #7c3aed)' : 'transparent',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 11,
    color: '#fff',
    fontWeight: 700,
    flexShrink: 0,
  }) as React.CSSProperties,

  /* preview area */
  previewBox: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 18,
    marginBottom: 28,
  } as React.CSSProperties,
  previewTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text)',
    marginBottom: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  } as React.CSSProperties,
  previewBtn: {
    fontSize: 11,
    color: 'var(--primary)',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    fontWeight: 600,
  } as React.CSSProperties,
  sampleCard: {
    background: 'var(--bg-secondary, rgba(0,0,0,0.15))',
    borderRadius: 6,
    padding: '10px 12px',
    marginBottom: 8,
    fontSize: 12,
    fontFamily: 'monospace',
    border: '1px solid var(--border)',
  } as React.CSSProperties,
  sampleRole: (role: string) => ({
    fontWeight: 700,
    color: role === 'assistant' ? 'var(--primary)' : role === 'system' ? 'var(--text-muted)' : 'var(--accent)',
    fontSize: 10,
    textTransform: 'uppercase' as const,
    marginTop: 4,
  }) as React.CSSProperties,
  sampleContent: {
    fontSize: 11,
    lineHeight: 1.4,
    color: 'var(--text)',
    marginBottom: 2,
  } as React.CSSProperties,
  sampleSection: {
    display: 'inline-block',
    fontSize: 9,
    fontWeight: 600,
    padding: '1px 6px',
    borderRadius: 3,
    background: 'rgba(124,58,237,0.15)',
    color: 'var(--primary)',
    marginBottom: 4,
  } as React.CSSProperties,

  /* actions bar */
  actionsBar: {
    display: 'flex',
    gap: 10,
    flexWrap: 'wrap' as const,
    alignItems: 'center',
    marginBottom: 20,
  } as React.CSSProperties,
  btn: (variant: 'primary' | 'secondary' | 'danger') => ({
    padding: '8px 18px',
    borderRadius: 8,
    border: 'none',
    cursor: 'pointer',
    fontWeight: 600,
    fontSize: 13,
    transition: 'opacity .2s',
    background:
      variant === 'primary' ? 'var(--primary, #7c3aed)' :
      variant === 'danger' ? 'var(--error, #ef4444)' :
      'var(--bg-tertiary, #333)',
    color: variant === 'secondary' ? 'var(--text)' : '#fff',
  }) as React.CSSProperties,

  /* config panel */
  configGrid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    marginBottom: 24,
  } as React.CSSProperties,
  section: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: 10,
    padding: 16,
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: 'var(--text)',
    marginBottom: 12,
  } as React.CSSProperties,
  controlRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
    fontSize: 13,
    color: 'var(--text)',
  } as React.CSSProperties,
  controlLabel: {
    color: 'var(--text-muted)',
    fontSize: 12,
  } as React.CSSProperties,
  input: {
    width: 80,
    padding: '4px 8px',
    border: '1px solid var(--border)',
    borderRadius: 6,
    background: 'var(--bg)',
    color: 'var(--text)',
    fontSize: 13,
    textAlign: 'right' as const,
  } as React.CSSProperties,

  /* adapter */
  adapterBadge: (loaded: boolean) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '4px 10px',
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    background: loaded ? 'rgba(16,185,129,.12)' : 'var(--bg-secondary, #222)',
    color: loaded ? 'var(--success, #10b981)' : 'var(--text-muted)',
  }) as React.CSSProperties,

  /* logs */
  logsBox: {
    background: '#0a0a0f',
    color: '#4ade80',
    padding: 12,
    fontFamily: '"SF Mono", Menlo, monospace',
    fontSize: 11,
    borderRadius: 8,
    minHeight: 90,
    maxHeight: 180,
    overflowY: 'auto' as const,
    border: '1px solid #27272a',
  } as React.CSSProperties,
};

interface MLXModel {
  id: string;
  label: string;
  size_gb: number;
  ram_gb: number;
  cached: boolean;
}

interface FTRun {
  name: string;
  base_model?: string;
  status?: string;
  started_at?: string;
  has_adapters: boolean;
}

/* ── Component ───────────────────────────────────────── */

interface FinetunePanelProps {
  selectedModule: string | null;
  modules: FTModule[];
  onToggleModule: (name: string, enabled: boolean) => void;
  onRefresh: () => void;
}

export const FinetunePanel: React.FC<FinetunePanelProps> = ({
  selectedModule,
  modules,
  onToggleModule,
  onRefresh,
}) => {
  const navigate = useNavigate();
  const [sections, setSections] = useState<Record<string, SectionInfo>>({});
  const [enabledSections, setEnabledSections] = useState<Record<string, boolean>>({
    data: true, api: true, cli: true, schema: true,
  });
  const [samples, setSamples] = useState<Sample[]>([]);
  const [showPreview, setShowPreview] = useState(false);
  const [adapter, setAdapter] = useState<AdapterStatus>({ status: 'none' });
  const [config, setConfig] = useState({ rank: 8, alpha: 16, scale: 1.0, dropout: 0.05, iters: 200, learning_rate: 1e-5, batch_size: 1, grad_accumulation_steps: 4, warmup: 50, max_seq_length: 1024 });
  const [logs, setLogs] = useState<string[]>([]);
  const [exporting, setExporting] = useState(false);
  const [training, setTraining] = useState(false);

  /* ── Model selection + run naming ──── */
  const [models, setModels] = useState<MLXModel[]>([]);
  const [selectedModel, setSelectedModel] = useState('mlx-community/Qwen2.5-7B-Instruct-4bit');
  const [runName, setRunName] = useState('');
  const [runs, setRuns] = useState<FTRun[]>([]);
  const [resumeAdapter, setResumeAdapter] = useState('');

  const mod = modules.find(m => m.name === selectedModule);

  /* ── Fetch available models + runs on mount ──── */
  useEffect(() => {
    fetch('/api/finetune/models')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.models) setModels(d.models); })
      .catch(() => {});
    fetch('/api/finetune/runs')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.runs) setRuns(d.runs); })
      .catch(() => {});
  }, []);

  /* ── Fetch sections when module changes ──── */
  useEffect(() => {
    if (!selectedModule) return;
    setSections({});
    setSamples([]);
    setShowPreview(false);

    fetch(`/api/finetune/modules/${encodeURIComponent(selectedModule)}/sections`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.sections) setSections(d.sections); })
      .catch(() => {});
  }, [selectedModule]);

  /* ── Fetch adapter on mount ──── */
  useEffect(() => {
    fetch('/api/finetune/load/status')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setAdapter(d); })
      .catch(() => {});
  }, []);

  /* ── Toggle section ──── */
  const toggleSection = (key: string) => {
    setEnabledSections(prev => ({ ...prev, [key]: !prev[key] }));
  };

  /* ── Preview samples ──── */
  const loadPreview = useCallback(async () => {
    if (!selectedModule) return;
    try {
      const res = await fetch(`/api/finetune/modules/${encodeURIComponent(selectedModule)}/preview?limit=5`);
      if (res.ok) {
        const d = await res.json();
        setSamples(d.samples ?? []);
      }
    } catch { /* ignore */ }
    setShowPreview(true);
  }, [selectedModule]);

  /* ── Export module with selected sections ──── */
  const handleExport = async () => {
    if (!selectedModule) return;
    setExporting(true);
    const secs = Object.entries(enabledSections).filter(([, v]) => v).map(([k]) => k);
    setLogs(prev => [...prev, `📦 Exporting ${selectedModule} [${secs.join(', ')}]…`]);
    try {
      const res = await fetch(`/api/finetune/modules/${encodeURIComponent(selectedModule)}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: secs }),
      });
      if (!res.ok) throw new Error('export failed');
      const d = await res.json();
      const n = d.result?.examples ?? '?';
      setLogs(prev => [...prev, `✅ ${selectedModule}: ${n} examples exported`]);
      onRefresh();
    } catch {
      setLogs(prev => [...prev, `❌ Export failed for ${selectedModule}`]);
    }
    setExporting(false);
  };

  /* ── Export ALL modules ──── */
  const handleExportAll = async () => {
    setExporting(true);
    setLogs(prev => [...prev, '📦 Exporting all modules…']);
    try {
      const res = await fetch('/api/finetune/export', { method: 'POST' });
      if (!res.ok) throw new Error('export failed');
      const d = await res.json();
      const total = d.results?.combined?.total_examples ?? '?';
      setLogs(prev => [...prev, `✅ All exported — ${total} examples combined`]);
      onRefresh();
    } catch {
      setLogs(prev => [...prev, '❌ Export all failed']);
    }
    setExporting(false);
  };

  /* ── Train ──── */
  const handleTrain = async () => {
    setTraining(true);
    const label = runName.trim() || undefined;
    setLogs(prev => [...prev, `🚀 Starting training: ${label || 'auto-named'} on ${selectedModel.split('/').pop()}${resumeAdapter ? ' (resuming)' : ''}…`]);
    try {
      const res = await fetch('/api/finetune/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...config, base_model: selectedModel, run_name: label, resume_adapter: resumeAdapter || undefined }),
      });
      if (!res.ok) throw new Error('start failed');
      const d = await res.json();
      setLogs(prev => [...prev, `🌀 Run "${d.run_name}" started — check terminal for progress`]);
      // Refresh runs list
      fetch('/api/finetune/runs').then(r => r.ok ? r.json() : null).then(d => { if (d?.runs) setRuns(d.runs); }).catch(() => {});
    } catch {
      setLogs(prev => [...prev, '❌ Training start failed']);
    }
    setTraining(false);
  };

  /* ── Load adapter ──── */
  const handleLoad = async () => {
    setLogs(prev => [...prev, '🔌 Loading adapter…']);
    try {
      const res = await fetch('/api/finetune/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: '{}',
      });
      if (!res.ok) throw new Error('load failed');
      const d = await res.json();
      setAdapter(d);
      setLogs(prev => [...prev, `✅ Adapter loaded: ${d.model_name}`]);
    } catch {
      setLogs(prev => [...prev, '❌ Adapter load failed']);
    }
  };

  /* ── No module selected ──── */
  if (!selectedModule || !mod) {
    const totalExamples = modules.reduce((s, m) => s + statCount(m.stats), 0);
    return (
      <div style={S.panel}>
        <div style={{ ...S.empty, height: 'auto', alignItems: 'stretch', padding: '32px 0' }}>
          <div style={{ textAlign: 'center', marginBottom: 24 }}>
            <div style={S.emptyIcon}>🔥</div>
            <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text)' }}>Fire-Tuner</div>
            <div style={S.emptyText}>
              {modules.length} modules · {totalExamples.toLocaleString()} total examples
            </div>
          </div>

          {/* ── Model + Run Name ──── */}
          <div style={{ ...S.section, marginBottom: 16 }}>
            <div style={S.sectionTitle}>🧠 Base Model</div>
            <select
              style={{ ...S.input, width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, marginBottom: 10 }}
              value={selectedModel}
              onChange={e => setSelectedModel(e.target.value)}
            >
              {models.map(m => (
                <option key={m.id} value={m.id}>
                  {m.label} — {m.size_gb}GB {m.cached ? '✓ cached' : '(will download)'}
                </option>
              ))}
              {models.length === 0 && <option value={selectedModel}>{selectedModel.split('/').pop()}</option>}
            </select>
            <div style={S.sectionTitle}>🏷️ Run Name</div>
            <input
              style={{ ...S.input, width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13 }}
              type="text"
              placeholder="e.g. 1.5b-test, qwen7b-v1, experiment-3"
              value={runName}
              onChange={e => setRunName(e.target.value)}
            />
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              Leave blank for auto-generated timestamp name
            </div>
            {runs.filter(r => r.has_adapters).length > 0 && (
              <>
                <div style={{ ...S.sectionTitle, marginTop: 12 }}>🔄 Resume From Adapter</div>
                <select
                  style={{ ...S.input, width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13 }}
                  value={resumeAdapter}
                  onChange={e => setResumeAdapter(e.target.value)}
                >
                  <option value="">Fresh training (no resume)</option>
                  {runs.filter(r => r.has_adapters).map(r => (
                    <option key={r.name} value={`runs/${r.name}/adapters`}>
                      {r.name} {r.base_model ? `(${r.base_model.split('/').pop()})` : ''}
                    </option>
                  ))}
                </select>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
                  Continue training from a previous run's adapter weights
                </div>
              </>
            )}
          </div>

          {/* Global actions */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button style={S.btn('secondary')} onClick={handleExportAll} disabled={exporting}>
              {exporting ? '⏳ Exporting…' : '📦 Export All'}
            </button>
            <button style={S.btn('primary')} onClick={handleTrain} disabled={training}>
              {training ? '⏳ Training…' : '🔥 Train'}
            </button>
            <button style={S.btn('secondary')} onClick={handleLoad}>🔌 Load Adapter</button>
          </div>

          <div style={{ textAlign: 'center', marginTop: 12 }}>
            <div style={S.adapterBadge(adapter.status === 'loaded')}>
              {adapter.status === 'loaded' ? `✓ ${adapter.active_model}` : '— No adapter loaded'}
            </div>
          </div>

          {/* ── Previous Runs ──── */}
          {runs.length > 0 && (
            <div style={{ ...S.section, marginTop: 16 }}>
              <div style={S.sectionTitle}>📁 Previous Runs</div>
              {runs.map(r => (
                <div key={r.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
                  <div>
                    <span style={{ fontWeight: 600, color: 'var(--text)' }}>{r.name}</span>
                    {r.base_model && <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 8 }}>{r.base_model.split('/').pop()}</span>}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 11, color: r.status === 'completed' ? 'var(--success, #10b981)' : r.status === 'failed' ? 'var(--error, #ef4444)' : 'var(--text-muted)', fontWeight: 600 }}>
                      {r.status || 'unknown'}
                    </span>
                    {r.has_adapters && <span style={{ fontSize: 10, background: 'rgba(16,185,129,.12)', color: 'var(--success, #10b981)', padding: '1px 6px', borderRadius: 3, fontWeight: 600 }}>adapters</span>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {logs.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <div style={S.logsBox}>
                {logs.map((l, i) => <div key={i}>{l}</div>)}
              </div>
            </div>
          )}

          <div style={S.emptyText}>Select a module from the sidebar to inspect training data</div>
        </div>
      </div>
    );
  }

  /* ── Module selected ──── */
  const sectionKeys = Object.keys(sections);
  const totalSelected = sectionKeys
    .filter(k => enabledSections[k])
    .reduce((s, k) => s + (sections[k]?.examples ?? 0), 0);

  return (
    <div style={S.panel}>
      {/* Header */}
      <div style={S.header}>
        <div style={S.moduleTitle}>
          <span>{MODULE_ICONS[mod.name] || '📦'}</span>
          <span>{mod.name}</span>
        </div>
        <button style={S.enableToggle(mod.enabled)} onClick={() => onToggleModule(mod.name, mod.enabled)}>
          <div style={S.toggleTrack(mod.enabled)}>
            <div style={S.toggleDot(mod.enabled)} />
          </div>
          {mod.enabled ? 'Enabled' : 'Disabled'}
        </button>
      </div>
      <div style={S.moduleDesc}>{MODULE_DESC[mod.name] || ''}</div>

      {/* ── Section Cards ──── */}
      <div style={S.sGrid}>
        {sectionKeys.map(key => {
          const sec = sections[key];
          const on = enabledSections[key] ?? true;
          return (
            <div
              key={key}
              style={S.sCard(on)}
              onClick={() => navigate(`/training/${encodeURIComponent(mod.name)}/${encodeURIComponent(key)}`)}
            >
              <div style={S.sCardTop}>
                <div style={S.sCardLabel}>
                  <span>{SECTION_ICONS[key] || '📄'}</span>
                  <span>{SECTION_LABELS[key] || key}</span>
                </div>
                <div
                  style={S.checkbox(on)}
                  onClick={e => { e.stopPropagation(); toggleSection(key); }}
                >
                  {on ? '✓' : ''}
                </div>
              </div>
              <div style={S.sCardCount}>{sec.examples.toLocaleString()}</div>
              <div style={S.sCardDesc}>{sec.description}</div>
            </div>
          );
        })}
      </div>

      {/* ── Actions Bar ──── */}
      <div style={S.actionsBar}>
        <button style={S.btn('secondary')} onClick={handleExport} disabled={exporting}>
          {exporting ? '⏳…' : `📦 Export ${mod.name}`}
        </button>
        <button style={S.btn('primary')} onClick={handleExportAll} disabled={exporting}>
          📦 Export All
        </button>
        <button style={S.btn('primary')} onClick={handleTrain} disabled={training}>
          {training ? '⏳…' : '🔥 Train'}
        </button>
        <button style={S.btn('secondary')} onClick={handleLoad}>🔌 Load Adapter</button>
        <button style={{ ...S.btn('secondary'), fontSize: 11 }} onClick={onRefresh}>↻ Refresh</button>

        <span style={{ fontSize: 12, color: 'var(--text-muted)', marginLeft: 'auto' }}>
          {totalSelected.toLocaleString()} examples selected
        </span>
      </div>

      {/* ── Preview ──── */}
      <div style={S.previewBox}>
        <div style={S.previewTitle}>
          <span>Sample Training Examples</span>
          <button style={S.previewBtn} onClick={showPreview ? () => setShowPreview(false) : loadPreview}>
            {showPreview ? 'Hide ▴' : 'Load preview ▾'}
          </button>
        </div>
        {showPreview && (
          samples.length === 0
            ? <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No examples yet</div>
            : samples.map((s, i) => (
              <div key={i} style={S.sampleCard}>
                {s.metadata?.section && <div style={S.sampleSection}>{s.metadata.section}</div>}
                {s.messages?.map((msg, mi) => (
                  <div key={mi}>
                    <div style={S.sampleRole(msg.role)}>{msg.role}</div>
                    <div style={S.sampleContent}>{truncate(msg.content, 200)}</div>
                  </div>
                ))}
              </div>
            ))
        )}
      </div>

      {/* ── Config + Logs ──── */}
      <div style={S.configGrid}>
        <div style={S.section}>
          <div style={S.sectionTitle}>🧠 Model & Run</div>
          <div style={S.controlRow}>
            <span style={S.controlLabel}>Base Model</span>
          </div>
          <select
            style={{ ...S.input, width: '100%', textAlign: 'left', padding: '4px 8px', fontSize: 12, marginBottom: 8 }}
            value={selectedModel}
            onChange={e => setSelectedModel(e.target.value)}
          >
            {models.map(m => (
              <option key={m.id} value={m.id}>
                {m.label} {m.cached ? '✓' : ''}
              </option>
            ))}
            {models.length === 0 && <option value={selectedModel}>{selectedModel.split('/').pop()}</option>}
          </select>
          <div style={S.controlRow}>
            <span style={S.controlLabel}>Run Name</span>
          </div>
          <input
            style={{ ...S.input, width: '100%', textAlign: 'left', padding: '4px 8px', fontSize: 12, marginBottom: 8 }}
            type="text"
            placeholder="e.g. 1.5b-test"
            value={runName}
            onChange={e => setRunName(e.target.value)}
          />
          <div style={S.sectionTitle}>⚙️ LoRA Config</div>
          {([
            ['Rank', 'rank', 4, 64, 4],
            ['Alpha', 'alpha', 8, 128, 8],
            ['Scale', 'scale', 0.1, 20, 0.1],
            ['Dropout', 'dropout', 0, 0.5, 0.01],
            ['Iterations', 'iters', 50, 5000, 50],
            ['Warmup Steps', 'warmup', 0, 500, 10],
            ['Batch Size', 'batch_size', 1, 8, 1],
            ['Grad Accum', 'grad_accumulation_steps', 1, 16, 1],
            ['Max Seq Len', 'max_seq_length', 256, 4096, 256],
          ] as const).map(([label, key, min, max, step]) => (
            <div key={key} style={S.controlRow}>
              <span style={S.controlLabel}>{label}</span>
              <input
                style={S.input}
                type="number" min={min} max={max} step={step}
                value={(config as Record<string, number>)[key]}
                onChange={e => setConfig(c => ({ ...c, [key]: +e.target.value }))}
              />
            </div>
          ))}
          <div style={S.controlRow}>
            <span style={S.controlLabel}>Learning Rate</span>
            <input
              style={{ ...S.input, width: 100 }}
              type="text"
              value={config.learning_rate}
              onChange={e => setConfig(c => ({ ...c, learning_rate: parseFloat(e.target.value) || 1e-5 }))}
            />
          </div>
        </div>

        <div style={S.section}>
          <div style={S.sectionTitle}>📋 Log</div>
          <div style={S.logsBox}>
            {logs.length === 0 && <div style={{ opacity: 0.5 }}>Ready…</div>}
            {logs.map((l, i) => <div key={i}>{l}</div>)}
          </div>
          <div style={{ marginTop: 10 }}>
            <div style={S.adapterBadge(adapter.status === 'loaded')}>
              {adapter.status === 'loaded' ? `✓ ${adapter.active_model}` : '— No adapter'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
