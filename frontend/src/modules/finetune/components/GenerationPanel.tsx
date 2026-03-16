import React, { useState, useEffect, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────── */
interface FileTarget {
  path: string;
  name: string;
  generated: number;
}

interface ModuleTarget {
  module: string;
  label: string;
  source_dir: string;
  files: FileTarget[];
  file_count: number;
  generated_total: number;
}

interface TargetsResponse {
  targets: ModuleTarget[];
  total_modules: number;
  total_files: number;
  total_generated: number;
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
    marginBottom: 24, flexWrap: 'wrap' as const,
  } as React.CSSProperties,

  title: {
    fontSize: 22, fontWeight: 700, letterSpacing: '-0.02em',
  } as React.CSSProperties,

  statRow: {
    display: 'flex', gap: 16, flexWrap: 'wrap' as const,
    marginBottom: 20,
  } as React.CSSProperties,

  stat: {
    background: 'var(--bg-secondary, #1a1a2e)',
    borderRadius: 10, padding: '12px 18px',
    display: 'flex', flexDirection: 'column' as const, gap: 2,
    minWidth: 120,
  } as React.CSSProperties,

  statLabel: { fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase' as const, letterSpacing: '0.04em' } as React.CSSProperties,
  statValue: { fontSize: 22, fontWeight: 700 } as React.CSSProperties,

  actions: {
    display: 'flex', gap: 10, marginBottom: 24, flexWrap: 'wrap' as const,
  } as React.CSSProperties,

  btn: {
    padding: '8px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 13,
    background: 'var(--primary, #7c3aed)', color: '#fff',
    transition: 'opacity 0.15s',
  } as React.CSSProperties,

  btnSecondary: {
    padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border, #333)',
    cursor: 'pointer', fontWeight: 600, fontSize: 13,
    background: 'transparent', color: 'var(--text, #e0e0e0)',
  } as React.CSSProperties,

  moduleCard: {
    background: 'var(--bg-secondary, #1a1a2e)',
    borderRadius: 12, border: '1px solid var(--border, #2a2a3e)',
    marginBottom: 12, overflow: 'hidden',
  } as React.CSSProperties,

  moduleHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '14px 18px', cursor: 'pointer',
    transition: 'background 0.15s',
  } as React.CSSProperties,

  moduleLeft: {
    display: 'flex', alignItems: 'center', gap: 12,
  } as React.CSSProperties,

  moduleName: { fontWeight: 700, fontSize: 14 } as React.CSSProperties,
  moduleLabel: { fontSize: 12, color: 'var(--text-muted)', marginLeft: 4 } as React.CSSProperties,
  moduleDir: { fontSize: 11, color: 'var(--text-muted)', fontFamily: 'monospace' } as React.CSSProperties,

  moduleRight: {
    display: 'flex', alignItems: 'center', gap: 12,
  } as React.CSSProperties,

  badge: {
    fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
    background: 'rgba(124,58,237,0.15)', color: 'var(--primary, #7c3aed)',
  } as React.CSSProperties,

  countBadge: {
    fontSize: 11, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
    background: 'rgba(34,197,94,0.15)', color: '#22c55e',
  } as React.CSSProperties,

  fileBadge: {
    fontSize: 11, fontWeight: 600, padding: '3px 8px', borderRadius: 6,
    background: 'rgba(100,116,139,0.15)', color: 'var(--text-muted)',
  } as React.CSSProperties,

  fileList: {
    borderTop: '1px solid var(--border, #2a2a3e)',
    padding: '8px 0',
  } as React.CSSProperties,

  fileRow: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '6px 18px 6px 36px', fontSize: 13,
    transition: 'background 0.12s',
  } as React.CSSProperties,

  fileLeft: {
    display: 'flex', alignItems: 'center', gap: 8,
    fontFamily: 'monospace', fontSize: 12, color: 'var(--text)',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const,
    flex: 1, minWidth: 0,
  } as React.CSSProperties,

  fileRight: {
    display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0,
  } as React.CSSProperties,

  fileBtn: {
    padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 11,
    background: 'rgba(124,58,237,0.15)', color: 'var(--primary, #7c3aed)',
    transition: 'opacity 0.15s',
  } as React.CSSProperties,

  spinner: {
    display: 'inline-block', width: 14, height: 14,
    border: '2px solid var(--text-muted)', borderTopColor: 'var(--primary, #7c3aed)',
    borderRadius: '50%', animation: 'spin 0.6s linear infinite',
  } as React.CSSProperties,
};

/* ── Component ─────────────────────────────────────── */

export const GenerationPanel: React.FC = () => {
  const [targets, setTargets] = useState<ModuleTarget[]>([]);
  const [totalFiles, setTotalFiles] = useState(0);
  const [totalGenerated, setTotalGenerated] = useState(0);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [running, setRunning] = useState<Set<string>>(new Set()); // "module" or "module:file"
  const [runAllActive, setRunAllActive] = useState(false);

  const fetchTargets = useCallback(async () => {
    try {
      const res = await fetch('/api/finetune/generate/targets');
      if (res.ok) {
        const d: TargetsResponse = await res.json();
        setTargets(d.targets ?? []);
        setTotalFiles(d.total_files ?? 0);
        setTotalGenerated(d.total_generated ?? 0);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, []);

  useEffect(() => { fetchTargets(); }, [fetchTargets]);

  // Auto-refresh when things are running
  useEffect(() => {
    if (running.size === 0 && !runAllActive) return;
    const iv = setInterval(fetchTargets, 8000);
    return () => clearInterval(iv);
  }, [running, runAllActive, fetchTargets]);

  const toggleExpand = (module: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(module) ? next.delete(module) : next.add(module);
      return next;
    });
  };

  const generateModule = async (module: string) => {
    const key = module;
    setRunning(prev => new Set(prev).add(key));
    try {
      await fetch('/api/finetune/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module }),
      });
      // Poll until done
      setTimeout(() => {
        fetchTargets();
        setRunning(prev => { const n = new Set(prev); n.delete(key); return n; });
      }, 15000);
    } catch {
      setRunning(prev => { const n = new Set(prev); n.delete(key); return n; });
    }
  };

  const generateFile = async (module: string, filePath: string) => {
    const key = `${module}:${filePath}`;
    setRunning(prev => new Set(prev).add(key));
    try {
      await fetch('/api/finetune/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module, file: filePath }),
      });
      setTimeout(() => {
        fetchTargets();
        setRunning(prev => { const n = new Set(prev); n.delete(key); return n; });
      }, 15000);
    } catch {
      setRunning(prev => { const n = new Set(prev); n.delete(key); return n; });
    }
  };

  const generateAllFiles = async (module?: string) => {
    setRunAllActive(true);
    try {
      const url = module
        ? `/api/finetune/generate/all-files?module=${encodeURIComponent(module)}`
        : '/api/finetune/generate/all-files';
      await fetch(url, { method: 'POST' });
      // This is a long-running background task; poll for updates
      const interval = setInterval(fetchTargets, 10000);
      // Clear after a reasonable max time (10 min)
      setTimeout(() => {
        clearInterval(interval);
        setRunAllActive(false);
        fetchTargets();
      }, 600000);
    } catch {
      setRunAllActive(false);
    }
  };

  if (loading) {
    return <div style={S.panel}><div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>Loading generation targets…</div></div>;
  }

  return (
    <div style={S.panel}>
      {/* Spin animation */}
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Header */}
      <div style={S.header}>
        <span style={S.title}>🤖 Training Generator</span>
      </div>

      {/* Stats */}
      <div style={S.statRow}>
        <div style={S.stat}>
          <span style={S.statLabel}>Modules</span>
          <span style={S.statValue}>{targets.length}</span>
        </div>
        <div style={S.stat}>
          <span style={S.statLabel}>Source Files</span>
          <span style={S.statValue}>{totalFiles}</span>
        </div>
        <div style={S.stat}>
          <span style={S.statLabel}>Generated</span>
          <span style={S.statValue}>{totalGenerated}</span>
        </div>
        <div style={S.stat}>
          <span style={S.statLabel}>Model</span>
          <span style={{ ...S.statValue, fontSize: 14 }}>kimi-k2</span>
        </div>
      </div>

      {/* Global actions */}
      <div style={S.actions}>
        <button
          style={{ ...S.btn, opacity: runAllActive ? 0.6 : 1 }}
          disabled={runAllActive}
          onClick={() => generateAllFiles()}
        >
          {runAllActive ? '⏳ Running…' : '🚀 Generate All Files'}
        </button>
        <button style={S.btnSecondary} onClick={fetchTargets}>
          ↻ Refresh
        </button>
      </div>

      {/* Module cards */}
      {targets.map(target => {
        const isExpanded = expanded.has(target.module);
        const isModuleRunning = running.has(target.module);

        return (
          <div key={target.module} style={S.moduleCard}>
            {/* Module header */}
            <div
              style={S.moduleHeader}
              onClick={() => toggleExpand(target.module)}
            >
              <div style={S.moduleLeft}>
                <span style={{ fontSize: 14, opacity: 0.5 }}>
                  {isExpanded ? '▾' : '▸'}
                </span>
                <span style={S.moduleName}>{target.module}</span>
                <span style={S.moduleLabel}>{target.label}</span>
                <span style={S.moduleDir}>{target.source_dir}/</span>
              </div>
              <div style={S.moduleRight}>
                <span style={S.fileBadge}>{target.file_count} files</span>
                {target.generated_total > 0 && (
                  <span style={S.countBadge}>{target.generated_total} generated</span>
                )}
                <button
                  style={{ ...S.fileBtn, opacity: isModuleRunning ? 0.6 : 1 }}
                  disabled={isModuleRunning}
                  onClick={(e) => { e.stopPropagation(); generateModule(target.module); }}
                >
                  {isModuleRunning ? '⏳' : '▶'}  Module
                </button>
                <button
                  style={{ ...S.fileBtn, background: 'rgba(34,197,94,0.15)', color: '#22c55e' }}
                  onClick={(e) => { e.stopPropagation(); generateAllFiles(target.module); }}
                >
                  🚀 All Files
                </button>
              </div>
            </div>

            {/* File list (expanded) */}
            {isExpanded && (
              <div style={S.fileList}>
                {target.files.length === 0 && (
                  <div style={{ padding: '12px 36px', color: 'var(--text-muted)', fontSize: 13 }}>
                    No Python files found
                  </div>
                )}
                {target.files.map(file => {
                  const fileKey = `${target.module}:${file.path}`;
                  const isFileRunning = running.has(fileKey);

                  return (
                    <div
                      key={file.path}
                      style={S.fileRow}
                      onMouseEnter={e => (e.currentTarget.style.background = 'rgba(124,58,237,0.05)')}
                      onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                      <div style={S.fileLeft}>
                        <span>📄</span>
                        <span title={file.path}>{file.path}</span>
                      </div>
                      <div style={S.fileRight}>
                        {file.generated > 0 && (
                          <span style={S.countBadge}>{file.generated}</span>
                        )}
                        {isFileRunning ? (
                          <div style={S.spinner} />
                        ) : (
                          <button
                            style={S.fileBtn}
                            onClick={() => generateFile(target.module, file.path)}
                          >
                            ▶ Generate
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};
