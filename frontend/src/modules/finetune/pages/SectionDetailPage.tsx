import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

/* ── Types ─────────────────────────────────────────── */

interface Example {
  _id: number;
  messages: { role: string; content: string }[];
  metadata?: Record<string, unknown>;
}

/* ── Constants ─────────────────────────────────────── */

const MODULE_ICONS: Record<string, string> = {
  linking_core: '🔗', identity: '🪞', philosophy: '🧠', log: '📝',
  reflex: '⚡', form: '🛠️', chat: '💬', docs: '📚',
};

const SECTION_ICONS: Record<string, string> = {
  data: '💾', api: '🌐', cli: '⌨️', schema: '🗃️',
  reasoning: '🧩', generated: '🤖', approved: '✅',
};

const SECTION_LABELS: Record<string, string> = {
  data: 'Data', api: 'API Endpoints', cli: 'CLI Commands', schema: 'Schema',
  reasoning: 'Reasoning (Curated)', generated: 'Generated (Synthetic)', approved: 'Approved',
};

/* ── Styles ────────────────────────────────────────── */

const S = {
  page: {
    display: 'flex', flexDirection: 'column' as const, height: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
  } as React.CSSProperties,
  header: {
    display: 'flex', alignItems: 'center', gap: 12, padding: '20px 28px',
    borderBottom: '1px solid var(--border)', background: 'var(--surface)',
    flexShrink: 0,
  } as React.CSSProperties,
  backBtn: {
    background: 'none', border: '1px solid var(--border)', borderRadius: 8,
    padding: '6px 14px', cursor: 'pointer', fontSize: 13, fontWeight: 600,
    color: 'var(--text-muted)', transition: 'all .2s',
  } as React.CSSProperties,
  title: {
    display: 'flex', alignItems: 'center', gap: 8, fontSize: 20, fontWeight: 700,
    color: 'var(--text)', flex: 1,
  } as React.CSSProperties,
  badge: {
    fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
    background: 'rgba(124,58,237,0.12)', color: 'var(--primary, #7c3aed)',
  } as React.CSSProperties,
  body: {
    flex: 1, overflowY: 'auto' as const, padding: '20px 28px',
  } as React.CSSProperties,

  /* Approval bar for generated section */
  approvalBar: {
    display: 'flex', alignItems: 'center', gap: 10, padding: '12px 0',
    marginBottom: 16, borderBottom: '1px solid var(--border)',
  } as React.CSSProperties,
  selectAll: {
    display: 'flex', alignItems: 'center', gap: 6, fontSize: 13,
    color: 'var(--text-muted)', cursor: 'pointer',
  } as React.CSSProperties,
  approveBtn: {
    padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 12, background: 'var(--success, #10b981)', color: '#fff',
  } as React.CSSProperties,
  rejectBtn: {
    padding: '6px 16px', borderRadius: 8, border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 12, background: 'var(--error, #ef4444)', color: '#fff',
  } as React.CSSProperties,

  /* Example card */
  card: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 10, padding: 16, marginBottom: 12,
  } as React.CSSProperties,
  cardHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 8,
  } as React.CSSProperties,
  cardMeta: {
    display: 'flex', gap: 6, flexWrap: 'wrap' as const,
  } as React.CSSProperties,
  metaBadge: {
    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
    background: 'rgba(124,58,237,0.1)', color: 'var(--primary, #7c3aed)',
  } as React.CSSProperties,
  roleLabel: (role: string) => ({
    fontSize: 10, fontWeight: 700, textTransform: 'uppercase' as const,
    marginTop: 8, marginBottom: 2,
    color: role === 'assistant' ? 'var(--primary, #7c3aed)'
         : role === 'system' ? 'var(--text-muted)'
         : 'var(--accent, #f59e0b)',
  }) as React.CSSProperties,
  msgContent: {
    fontSize: 13, lineHeight: 1.55, color: 'var(--text)',
    whiteSpace: 'pre-wrap' as const, fontFamily: 'inherit',
  } as React.CSSProperties,
  systemToggle: {
    fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer',
    background: 'none', border: 'none', fontWeight: 600, padding: 0,
  } as React.CSSProperties,

  /* Pagination */
  pagination: {
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    gap: 8, padding: '16px 0',
  } as React.CSSProperties,
  pageBtn: (active: boolean) => ({
    padding: '6px 12px', borderRadius: 6,
    border: active ? 'none' : '1px solid var(--border)',
    background: active ? 'var(--primary, #7c3aed)' : 'var(--surface)',
    color: active ? '#fff' : 'var(--text)',
    cursor: 'pointer', fontSize: 13, fontWeight: 600,
  }) as React.CSSProperties,
  navBtn: {
    padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text-muted)',
    cursor: 'pointer', fontSize: 13,
  } as React.CSSProperties,

  /* Checkbox */
  checkbox: (on: boolean) => ({
    width: 18, height: 18, borderRadius: 4,
    border: `2px solid ${on ? 'var(--primary, #7c3aed)' : 'var(--border)'}`,
    background: on ? 'var(--primary, #7c3aed)' : 'transparent',
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
    fontSize: 11, color: '#fff', fontWeight: 700, cursor: 'pointer', flexShrink: 0,
  }) as React.CSSProperties,

  /* Action badges for approve/reject */
  approvedBadge: {
    fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(16,185,129,0.15)', color: 'var(--success, #10b981)',
  } as React.CSSProperties,
  rejectedBadge: {
    fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 4,
    background: 'rgba(239,68,68,0.15)', color: 'var(--error, #ef4444)',
  } as React.CSSProperties,

  empty: {
    textAlign: 'center' as const, padding: 40, color: 'var(--text-muted)', fontSize: 14,
  } as React.CSSProperties,
};

/* ── Component ─────────────────────────────────────── */

export const SectionDetailPage: React.FC = () => {
  const { module, section } = useParams<{ module: string; section: string }>();
  const navigate = useNavigate();

  const [examples, setExamples] = useState<Example[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedSystem, setExpandedSystem] = useState<Set<number>>(new Set());
  const [approving, setApproving] = useState(false);
  const [generating, setGenerating] = useState(false);

  const isGenerated = section === 'generated';

  const fetchExamples = useCallback(async (p: number) => {
    if (!module || !section) return;
    setLoading(true);
    try {
      const res = await fetch(
        `/api/finetune/modules/${encodeURIComponent(module)}/sections/${encodeURIComponent(section)}?page=${p}&per_page=50`
      );
      if (res.ok) {
        const d = await res.json();
        setExamples(d.examples ?? []);
        setTotal(d.total ?? 0);
        setPages(d.pages ?? 0);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [module, section]);

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
    fetchExamples(1);
  }, [module, section, fetchExamples]);

  useEffect(() => {
    fetchExamples(page);
  }, [page, fetchExamples]);

  /* ── Selection helpers ── */
  const toggleSelect = (id: number) => {
    setSelectedIds(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedIds.size === examples.length) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(examples.map(e => e._id)));
    }
  };

  const toggleSystem = (id: number) => {
    setExpandedSystem(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  /* ── Approve/Reject ── */
  const handleApproval = async (action: 'approve' | 'reject') => {
    if (!module || selectedIds.size === 0) return;
    setApproving(true);
    try {
      await fetch(`/api/finetune/modules/${encodeURIComponent(module)}/sections/generated/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ example_ids: [...selectedIds], action }),
      });
      setSelectedIds(new Set());
      fetchExamples(page);
    } catch { /* ignore */ }
    setApproving(false);
  };

  /* ── On-demand generation ── */
  const handleGenerate = async () => {
    if (!module) return;
    setGenerating(true);
    try {
      await fetch('/api/finetune/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module }),
      });
      // Give the background task a moment, then refresh
      setTimeout(() => {
        fetchExamples(page);
        setGenerating(false);
      }, 5000);
    } catch {
      setGenerating(false);
    }
  };

  if (!module || !section) {
    return <div style={S.empty}>Missing module or section parameter.</div>;
  }

  return (
    <div style={S.page}>
      {/* Header */}
      <div style={S.header}>
        <button style={S.backBtn} onClick={() => navigate('/training')}>← Back</button>
        <div style={S.title}>
          <span>{MODULE_ICONS[module] || '📦'}</span>
          <span>{module}</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>/</span>
          <span>{SECTION_ICONS[section] || '📄'}</span>
          <span>{SECTION_LABELS[section] || section}</span>
        </div>
        <span style={S.badge}>{total.toLocaleString()} examples</span>
        {isGenerated && (
          <button
            style={{
              ...S.approveBtn,
              opacity: generating ? 0.6 : 1,
              cursor: generating ? 'wait' : 'pointer',
            }}
            disabled={generating}
            onClick={handleGenerate}
          >
            {generating ? '⏳ Generating…' : '🤖 Generate'}
          </button>
        )}
      </div>

      {/* Body */}
      <div style={S.body}>
        {/* Approval bar for generated section */}
        {isGenerated && examples.length > 0 && (
          <div style={S.approvalBar}>
            <div style={S.selectAll} onClick={toggleSelectAll}>
              <div style={S.checkbox(selectedIds.size === examples.length && examples.length > 0)}>
                {selectedIds.size === examples.length && examples.length > 0 ? '✓' : ''}
              </div>
              <span>Select all ({selectedIds.size}/{examples.length})</span>
            </div>
            <button
              style={S.approveBtn}
              disabled={selectedIds.size === 0 || approving}
              onClick={() => handleApproval('approve')}
            >
              ✓ Approve ({selectedIds.size})
            </button>
            <button
              style={S.rejectBtn}
              disabled={selectedIds.size === 0 || approving}
              onClick={() => handleApproval('reject')}
            >
              ✗ Reject ({selectedIds.size})
            </button>
          </div>
        )}

        {loading && <div style={S.empty}>Loading…</div>}

        {!loading && examples.length === 0 && (
          <div style={S.empty}>
            No examples in {module}/{section} yet.
            {isGenerated && ' The training generator loop will populate these automatically.'}
          </div>
        )}

        {/* Example cards */}
        {examples.map(ex => {
          const meta = ex.metadata || {};
          const systemMsg = ex.messages?.find(m => m.role === 'system');
          const userMsg = ex.messages?.find(m => m.role === 'user');
          const assistantMsg = ex.messages?.find(m => m.role === 'assistant');
          const showSystem = expandedSystem.has(ex._id);
          const isSelected = selectedIds.has(ex._id);
          const isApproved = meta.approved === true;
          const isRejected = meta.rejected === true;

          return (
            <div
              key={ex._id}
              style={{
                ...S.card,
                ...(isSelected ? { borderColor: 'var(--primary, #7c3aed)' } : {}),
                ...(isRejected ? { opacity: 0.5 } : {}),
              }}
            >
              <div style={S.cardHeader}>
                <div style={S.cardMeta}>
                  {meta.section ? <span style={S.metaBadge}>{String(meta.section)}</span> : null}
                  {meta.type ? <span style={S.metaBadge}>{String(meta.type)}</span> : null}
                  {meta.topic ? <span style={S.metaBadge}>{String(meta.topic)}</span> : null}
                  {isApproved && <span style={S.approvedBadge}>✓ Approved</span>}
                  {isRejected && <span style={S.rejectedBadge}>✗ Rejected</span>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {isGenerated && (
                    <div style={S.checkbox(isSelected)} onClick={() => toggleSelect(ex._id)}>
                      {isSelected ? '✓' : ''}
                    </div>
                  )}
                </div>
              </div>

              {/* System prompt — collapsed by default */}
              {systemMsg && (
                <div>
                  <button
                    style={S.systemToggle}
                    onClick={() => toggleSystem(ex._id)}
                  >
                    {showSystem ? '▾ System Prompt' : '▸ System Prompt (click to expand)'}
                  </button>
                  {showSystem && (
                    <div style={{ ...S.msgContent, color: 'var(--text-muted)', fontSize: 12, marginTop: 4, marginBottom: 8, padding: '8px 10px', background: 'rgba(0,0,0,0.1)', borderRadius: 6 }}>
                      {systemMsg.content}
                    </div>
                  )}
                </div>
              )}

              {/* User message */}
              {userMsg && (
                <div>
                  <div style={S.roleLabel('user')}>User</div>
                  <div style={S.msgContent}>{userMsg.content}</div>
                </div>
              )}

              {/* Assistant message */}
              {assistantMsg && (
                <div>
                  <div style={S.roleLabel('assistant')}>Assistant</div>
                  <div style={S.msgContent}>{assistantMsg.content}</div>
                </div>
              )}
            </div>
          );
        })}

        {/* Pagination */}
        {pages > 1 && (
          <div style={S.pagination}>
            <button
              style={S.navBtn}
              disabled={page <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
            >
              ← Prev
            </button>
            {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
              const p = pages <= 7 ? i + 1 : Math.max(1, Math.min(page - 3 + i, pages));
              return (
                <button
                  key={p}
                  style={S.pageBtn(p === page)}
                  onClick={() => setPage(p)}
                >
                  {p}
                </button>
              );
            })}
            <button
              style={S.navBtn}
              disabled={page >= pages}
              onClick={() => setPage(p => Math.min(pages, p + 1))}
            >
              Next →
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
