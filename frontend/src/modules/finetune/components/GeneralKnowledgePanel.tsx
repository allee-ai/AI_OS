import React, { useState, useEffect, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────── */

interface TopicSummary {
  id: string;
  name: string;
  icon: string;
  description: string;
  aios_framing: string;
  example_count: number;
  // present after scan:
  match_count?: number;
  file_count?: number;
  top_files?: { file: string; matches: number }[];
}

interface Example {
  messages: { role: string; content: string }[];
  _index: number;
}

/* ── Styles ────────────────────────────────────────── */

const S = {
  panel: {
    display: 'flex', flex: 1, minWidth: 0, height: '100vh', overflow: 'hidden',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
  } as React.CSSProperties,

  /* Left column — topic list */
  topicList: {
    width: 280, minWidth: 280, borderRight: '1px solid var(--border, #333)',
    overflowY: 'auto' as const, padding: '16px 0',
    background: 'var(--bg-secondary, #111)',
  } as React.CSSProperties,

  topicListHeader: {
    padding: '0 16px 12px', fontSize: 13, fontWeight: 700,
    color: 'var(--text-muted, #888)', textTransform: 'uppercase' as const,
    letterSpacing: '0.05em', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  } as React.CSSProperties,

  scanBtn: {
    fontSize: 11, background: 'var(--accent, #6c63ff)', color: '#fff',
    border: 'none', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontWeight: 600,
  } as React.CSSProperties,

  topicItem: (active: boolean) => ({
    display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px',
    cursor: 'pointer', transition: 'background .15s',
    background: active ? 'var(--surface, #1a1a2e)' : 'transparent',
    borderLeft: active ? '3px solid var(--accent, #6c63ff)' : '3px solid transparent',
  }) as React.CSSProperties,

  topicIcon: { fontSize: 18, width: 24, textAlign: 'center' as const } as React.CSSProperties,

  topicInfo: { flex: 1, minWidth: 0 } as React.CSSProperties,

  topicName: { fontSize: 13, fontWeight: 600, color: 'var(--text, #e0e0e0)' } as React.CSSProperties,

  topicMeta: { fontSize: 11, color: 'var(--text-muted, #888)', marginTop: 2 } as React.CSSProperties,

  badge: (n: number) => ({
    fontSize: 11, fontWeight: 700, borderRadius: 10, padding: '2px 8px',
    background: n > 0 ? 'var(--accent, #6c63ff)' : 'var(--bg-tertiary, #333)',
    color: n > 0 ? '#fff' : 'var(--text-muted, #888)',
  }) as React.CSSProperties,

  /* Coverage bar */
  bar: {
    height: 4, borderRadius: 2, background: 'var(--bg-tertiary, #333)',
    marginTop: 4, overflow: 'hidden',
  } as React.CSSProperties,

  barFill: (pct: number) => ({
    height: '100%', borderRadius: 2, width: `${Math.min(pct, 100)}%`,
    background: 'var(--accent, #6c63ff)', transition: 'width .3s',
  }) as React.CSSProperties,

  /* Right column — detail */
  detail: {
    flex: 1, overflowY: 'auto' as const, padding: '24px 28px',
  } as React.CSSProperties,

  detailEmpty: {
    flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: 'var(--text-muted, #888)', fontSize: 15, fontStyle: 'italic' as const,
  } as React.CSSProperties,

  detailHeader: {
    display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8,
  } as React.CSSProperties,

  detailTitle: { fontSize: 22, fontWeight: 700, color: 'var(--text, #e0e0e0)' } as React.CSSProperties,

  framing: {
    fontSize: 13, color: 'var(--text-muted, #aaa)', marginBottom: 20,
    padding: '10px 14px', background: 'var(--surface, #1a1a2e)',
    borderRadius: 8, borderLeft: '3px solid var(--accent, #6c63ff)',
    lineHeight: 1.5,
  } as React.CSSProperties,

  sectionLabel: {
    fontSize: 13, fontWeight: 700, color: 'var(--text-muted, #888)',
    textTransform: 'uppercase' as const, letterSpacing: '0.05em',
    marginBottom: 10, marginTop: 24,
  } as React.CSSProperties,

  fileRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
    padding: '6px 12px', fontSize: 12, fontFamily: 'monospace',
    color: 'var(--text, #e0e0e0)', borderBottom: '1px solid var(--border, #222)',
  } as React.CSSProperties,

  fileCount: {
    fontSize: 11, color: 'var(--text-muted, #888)', fontFamily: 'sans-serif',
  } as React.CSSProperties,

  /* Examples */
  exampleCard: {
    background: 'var(--surface, #1a1a2e)', border: '1px solid var(--border, #333)',
    borderRadius: 10, padding: '14px 16px', marginBottom: 10,
  } as React.CSSProperties,

  exRole: {
    fontSize: 11, fontWeight: 700, color: 'var(--accent, #6c63ff)',
    textTransform: 'uppercase' as const, marginBottom: 4,
  } as React.CSSProperties,

  exContent: {
    fontSize: 13, color: 'var(--text, #e0e0e0)', whiteSpace: 'pre-wrap' as const,
    lineHeight: 1.5, marginBottom: 10,
  } as React.CSSProperties,

  exActions: { display: 'flex', gap: 8, justifyContent: 'flex-end' } as React.CSSProperties,

  btnSmall: (variant: 'primary' | 'danger' | 'ghost') => ({
    fontSize: 12, fontWeight: 600, border: 'none', borderRadius: 6,
    padding: '5px 14px', cursor: 'pointer',
    background: variant === 'primary' ? 'var(--accent, #6c63ff)'
      : variant === 'danger' ? '#e74c3c'
      : 'var(--bg-tertiary, #333)',
    color: variant === 'ghost' ? 'var(--text-muted, #888)' : '#fff',
  }) as React.CSSProperties,

  addBtn: {
    background: 'var(--accent, #6c63ff)', color: '#fff', border: 'none',
    borderRadius: 8, padding: '10px 20px', fontSize: 14, fontWeight: 600,
    cursor: 'pointer', marginTop: 12,
  } as React.CSSProperties,

  /* Editor */
  editorOverlay: {
    position: 'fixed' as const, inset: 0, background: 'rgba(0,0,0,.6)',
    display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
  } as React.CSSProperties,

  editor: {
    background: 'var(--bg, #0d0d1a)', border: '1px solid var(--border, #333)',
    borderRadius: 12, padding: 24, width: 600, maxHeight: '80vh',
    overflowY: 'auto' as const,
  } as React.CSSProperties,

  textarea: {
    width: '100%', minHeight: 80, background: 'var(--bg-secondary, #111)',
    color: 'var(--text, #e0e0e0)', border: '1px solid var(--border, #333)',
    borderRadius: 8, padding: 10, fontSize: 13, fontFamily: 'monospace',
    resize: 'vertical' as const, marginBottom: 10,
  } as React.CSSProperties,

  editorActions: {
    display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 16,
  } as React.CSSProperties,
};

/* ── Component ─────────────────────────────────────── */

export const GeneralKnowledgePanel: React.FC = () => {
  const [topics, setTopics] = useState<TopicSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [examples, setExamples] = useState<Example[]>([]);
  const [scanning, setScanning] = useState(false);
  const [maxMatches, setMaxMatches] = useState(1);
  const [editing, setEditing] = useState<{ index: number; messages: { role: string; content: string }[] } | null>(null);

  /* ── Fetch topics (fast path) ── */
  const fetchTopics = useCallback(async () => {
    try {
      const res = await fetch('/api/finetune/general-knowledge/topics');
      if (res.ok) {
        const d = await res.json();
        setTopics(d.topics ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchTopics(); }, [fetchTopics]);

  /* ── Scan codebase ── */
  const doScan = async () => {
    setScanning(true);
    try {
      const res = await fetch('/api/finetune/general-knowledge/scan');
      if (res.ok) {
        const d = await res.json();
        const scanned: TopicSummary[] = d.topics ?? [];
        setTopics(scanned);
        const mx = Math.max(1, ...scanned.map(t => t.match_count ?? 0));
        setMaxMatches(mx);
      }
    } catch { /* ignore */ }
    setScanning(false);
  };

  /* ── Fetch examples for selected topic ── */
  const fetchExamples = useCallback(async (topicId: string) => {
    try {
      const res = await fetch(`/api/finetune/general-knowledge/topics/${topicId}/examples`);
      if (res.ok) {
        const d = await res.json();
        setExamples(d.examples ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  const selectTopic = (id: string) => {
    setSelected(id);
    fetchExamples(id);
  };

  /* ── CRUD ── */
  const addExample = async (messages: { role: string; content: string }[]) => {
    if (!selected) return;
    await fetch(`/api/finetune/general-knowledge/topics/${selected}/examples`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });
    fetchExamples(selected);
    fetchTopics();
    setEditing(null);
  };

  const updateExample = async (index: number, messages: { role: string; content: string }[]) => {
    if (!selected) return;
    await fetch(`/api/finetune/general-knowledge/topics/${selected}/examples/${index}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });
    fetchExamples(selected);
    setEditing(null);
  };

  const deleteExample = async (index: number) => {
    if (!selected) return;
    await fetch(`/api/finetune/general-knowledge/topics/${selected}/examples/${index}`, {
      method: 'DELETE',
    });
    fetchExamples(selected);
    fetchTopics();
  };

  /* ── Derived ── */
  const topic = topics.find(t => t.id === selected);
  const totalExamples = topics.reduce((s, t) => s + t.example_count, 0);

  /* ── Render ── */
  return (
    <div style={S.panel}>
      {/* Left: topic list */}
      <div style={S.topicList}>
        <div style={S.topicListHeader}>
          <span>Topics ({topics.length}) · {totalExamples} examples</span>
          <button style={S.scanBtn} onClick={doScan} disabled={scanning}>
            {scanning ? '⏳' : '🔍'} Scan
          </button>
        </div>
        {topics.map(t => (
          <div
            key={t.id}
            style={S.topicItem(selected === t.id)}
            onClick={() => selectTopic(t.id)}
          >
            <span style={S.topicIcon}>{t.icon}</span>
            <div style={S.topicInfo}>
              <div style={S.topicName}>{t.name}</div>
              <div style={S.topicMeta}>
                {t.match_count != null ? `${t.match_count} matches · ${t.file_count} files` : t.description}
              </div>
              {t.match_count != null && (
                <div style={S.bar}>
                  <div style={S.barFill((t.match_count / maxMatches) * 100)} />
                </div>
              )}
            </div>
            <span style={S.badge(t.example_count)}>{t.example_count}</span>
          </div>
        ))}
      </div>

      {/* Right: detail */}
      {!topic ? (
        <div style={S.detailEmpty}>Select a topic to view coverage and training data</div>
      ) : (
        <div style={S.detail}>
          <div style={S.detailHeader}>
            <span style={{ fontSize: 28 }}>{topic.icon}</span>
            <span style={S.detailTitle}>{topic.name}</span>
          </div>
          <div style={S.framing}>{topic.aios_framing}</div>

          {/* File matches (if scanned) */}
          {topic.top_files && topic.top_files.length > 0 && (
            <>
              <div style={S.sectionLabel}>Top Files ({topic.file_count} total)</div>
              {topic.top_files.map(f => (
                <div key={f.file} style={S.fileRow}>
                  <span>{f.file}</span>
                  <span style={S.fileCount}>{f.matches} matches</span>
                </div>
              ))}
            </>
          )}

          {/* Training examples */}
          <div style={S.sectionLabel}>Training Examples ({examples.length})</div>
          {examples.map(ex => (
            <div key={ex._index} style={S.exampleCard}>
              {ex.messages.map((m, i) => (
                <div key={i}>
                  <div style={S.exRole}>{m.role}</div>
                  <div style={S.exContent}>{m.content}</div>
                </div>
              ))}
              <div style={S.exActions}>
                <button style={S.btnSmall('ghost')} onClick={() => setEditing({ index: ex._index, messages: [...ex.messages] })}>
                  Edit
                </button>
                <button style={S.btnSmall('danger')} onClick={() => deleteExample(ex._index)}>
                  Delete
                </button>
              </div>
            </div>
          ))}
          <button
            style={S.addBtn}
            onClick={() => setEditing({
              index: -1,
              messages: [
                { role: 'system', content: `You are Nola, a personal AI. ${topic.aios_framing}` },
                { role: 'user', content: '' },
                { role: 'assistant', content: '' },
              ],
            })}
          >
            + Add Example
          </button>
        </div>
      )}

      {/* Editor modal */}
      {editing && (
        <div style={S.editorOverlay} onClick={() => setEditing(null)}>
          <div style={S.editor} onClick={e => e.stopPropagation()}>
            <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 16, color: 'var(--text, #e0e0e0)' }}>
              {editing.index === -1 ? 'New Example' : 'Edit Example'}
            </div>
            {editing.messages.map((m, i) => (
              <div key={i}>
                <div style={S.exRole}>{m.role}</div>
                <textarea
                  style={S.textarea}
                  value={m.content}
                  onChange={e => {
                    const msgs = [...editing.messages];
                    msgs[i] = { ...msgs[i], content: e.target.value };
                    setEditing({ ...editing, messages: msgs });
                  }}
                />
              </div>
            ))}
            <div style={S.editorActions}>
              <button style={S.btnSmall('ghost')} onClick={() => setEditing(null)}>Cancel</button>
              <button
                style={S.btnSmall('primary')}
                onClick={() => {
                  if (editing.index === -1) {
                    addExample(editing.messages);
                  } else {
                    updateExample(editing.index, editing.messages);
                  }
                }}
              >
                {editing.index === -1 ? 'Add' : 'Save'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
