import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

/* ── Types ─────────────────────────────────────────── */

interface Example {
  _id: number;
  messages: { role: string; content: string }[];
  metadata?: Record<string, unknown>;
  _has_state?: boolean;
}

interface Template {
  id: number;
  module: string;
  section: string;
  name: string;
  question_template: string;
  answer_template: string;
  enabled: number;
  created_at: string;
  updated_at: string;
}

interface TemplatePreview {
  user: string;
  assistant: string;
  data: Record<string, unknown>;
  error?: string;
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

  /* Template editor */
  templatePanel: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 10, padding: 16, marginBottom: 20,
  } as React.CSSProperties,
  templateHeader: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: 12,
  } as React.CSSProperties,
  templateTitle: {
    fontSize: 14, fontWeight: 700, color: 'var(--text)',
    display: 'flex', alignItems: 'center', gap: 6,
  } as React.CSSProperties,
  templateCard: {
    background: 'rgba(0,0,0,0.05)', border: '1px solid var(--border)',
    borderRadius: 8, padding: 12, marginBottom: 10,
  } as React.CSSProperties,
  templateLabel: {
    fontSize: 11, fontWeight: 700, textTransform: 'uppercase' as const,
    color: 'var(--text-muted)', marginBottom: 4,
  } as React.CSSProperties,
  templateInput: {
    width: '100%', padding: '8px 10px', borderRadius: 6,
    border: '1px solid var(--border)', background: 'var(--surface)',
    color: 'var(--text)', fontSize: 13, fontFamily: 'monospace',
    resize: 'vertical' as const, minHeight: 36,
  } as React.CSSProperties,
  templateActions: {
    display: 'flex', gap: 8, marginTop: 8, alignItems: 'center',
  } as React.CSSProperties,
  saveBtn: {
    padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer',
    fontWeight: 600, fontSize: 12, background: 'var(--primary, #7c3aed)', color: '#fff',
  } as React.CSSProperties,
  previewBtn: {
    padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)',
    cursor: 'pointer', fontWeight: 600, fontSize: 12,
    background: 'var(--surface)', color: 'var(--text)',
  } as React.CSSProperties,
  addBtn: {
    padding: '6px 14px', borderRadius: 6, border: '1px dashed var(--border)',
    cursor: 'pointer', fontWeight: 600, fontSize: 12,
    background: 'transparent', color: 'var(--text-muted)',
  } as React.CSSProperties,
  previewBox: {
    background: 'rgba(124,58,237,0.06)', border: '1px solid rgba(124,58,237,0.2)',
    borderRadius: 6, padding: 10, marginTop: 8, fontSize: 12,
  } as React.CSSProperties,
  stateToggle: {
    fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer',
    background: 'rgba(124,58,237,0.08)', border: '1px solid var(--border)',
    borderRadius: 4, padding: '2px 8px', fontWeight: 600,
  } as React.CSSProperties,
};

/* ── Component ─────────────────────────────────────── */

export interface SectionDetailProps {
  moduleOverride?: string;
  sectionOverride?: string;
  embedded?: boolean;
}

export const SectionDetailPage: React.FC<SectionDetailProps> = ({
  moduleOverride, sectionOverride, embedded = false,
}) => {
  const params = useParams<{ module: string; section: string }>();
  const navigate = useNavigate();
  const module = moduleOverride || params.module;
  const section = sectionOverride || params.section;

  const [examples, setExamples] = useState<Example[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedSystem, setExpandedSystem] = useState<Set<number>>(new Set());
  const [approving, setApproving] = useState(false);
  const [generating, setGenerating] = useState(false);

  // Template state
  const [templates, setTemplates] = useState<Template[]>([]);
  const [editDrafts, setEditDrafts] = useState<Record<number, { q: string; a: string }>>({});
  const [previews, setPreviews] = useState<Record<number, TemplatePreview[]>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTemplate, setNewTemplate] = useState({ name: '', question_template: '', answer_template: '' });

  // On-demand STATE loading
  const [loadedStates, setLoadedStates] = useState<Record<number, string>>({});
  const [loadingState, setLoadingState] = useState<Set<number>>(new Set());

  const isGenerated = section === 'generated';
  const isDataSection = section === 'data';

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

  const fetchTemplates = useCallback(async () => {
    if (!module || !section) return;
    try {
      const res = await fetch(`/api/finetune/templates?module=${encodeURIComponent(module)}&section=${encodeURIComponent(section)}`);
      if (res.ok) {
        const d = await res.json();
        setTemplates(d.templates ?? []);
        // Initialize edit drafts
        const drafts: Record<number, { q: string; a: string }> = {};
        for (const t of d.templates ?? []) {
          drafts[t.id] = { q: t.question_template, a: t.answer_template };
        }
        setEditDrafts(drafts);
      }
    } catch { /* ignore */ }
  }, [module, section]);

  useEffect(() => {
    setPage(1);
    setSelectedIds(new Set());
    setLoadedStates({});
    fetchExamples(1);
    fetchTemplates();
  }, [module, section, fetchExamples, fetchTemplates]);

  useEffect(() => {
    fetchExamples(page);
    setLoadedStates({});
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

  /* ── Template handlers ── */
  const handleSaveTemplate = async (tpl: Template) => {
    const draft = editDrafts[tpl.id];
    if (!draft) return;
    setSavingId(tpl.id);
    try {
      await fetch(`/api/finetune/templates/${tpl.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_template: draft.q,
          answer_template: draft.a,
        }),
      });
      fetchTemplates();
    } catch { /* ignore */ }
    setSavingId(null);
  };

  const handlePreviewTemplate = async (tpl: Template) => {
    try {
      const res = await fetch(`/api/finetune/templates/${tpl.id}/preview`, {
        method: 'POST',
      });
      if (res.ok) {
        const d = await res.json();
        setPreviews(prev => ({ ...prev, [tpl.id]: d.previews ?? [] }));
      }
    } catch { /* ignore */ }
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await fetch(`/api/finetune/templates/${id}`, { method: 'DELETE' });
      fetchTemplates();
    } catch { /* ignore */ }
  };

  const handleCreateTemplate = async () => {
    if (!module || !section || !newTemplate.name) return;
    try {
      await fetch('/api/finetune/templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ module, section, ...newTemplate }),
      });
      setNewTemplate({ name: '', question_template: '', answer_template: '' });
      setShowNewForm(false);
      fetchTemplates();
    } catch { /* ignore */ }
  };

  const handleSeedTemplates = async () => {
    try {
      await fetch('/api/finetune/templates/seed', { method: 'POST' });
      fetchTemplates();
    } catch { /* ignore */ }
  };

  const handleRegenerate = async () => {
    if (!module) return;
    try {
      await fetch(`/api/finetune/modules/${encodeURIComponent(module)}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
      // Refresh after export
      setTimeout(() => fetchExamples(page), 1000);
    } catch { /* ignore */ }
  };

  /* ── On-demand STATE loading ── */
  const handleLoadState = async (exId: number, query: string) => {
    setLoadingState(prev => new Set(prev).add(exId));
    try {
      const res = await fetch('/api/finetune/build-state', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      });
      if (res.ok) {
        const d = await res.json();
        setLoadedStates(prev => ({ ...prev, [exId]: d.state }));
      }
    } catch { /* ignore */ }
    setLoadingState(prev => {
      const next = new Set(prev);
      next.delete(exId);
      return next;
    });
  };

  if (!module || !section) {
    return <div style={S.empty}>Missing module or section parameter.</div>;
  }

  return (
    <div style={{ ...S.page, ...(embedded ? { height: '100%' } : {}) }}>
      {/* Header — standalone mode only */}
      {!embedded && (
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
      )}

      {/* Embedded header — compact title */}
      {embedded && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 28px 12px', flexShrink: 0 }}>
          <span style={{ fontSize: 18 }}>{MODULE_ICONS[module] || '📦'}</span>
          <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text)' }}>{module}</span>
          <span style={{ color: 'var(--text-muted)' }}>/</span>
          <span>{SECTION_ICONS[section] || '📄'}</span>
          <span style={{ fontSize: 16, fontWeight: 600, color: 'var(--text)' }}>{SECTION_LABELS[section] || section}</span>
          <span style={S.badge}>{total.toLocaleString()} examples</span>
        </div>
      )}

      {/* Body */}
      <div style={S.body}>
        {/* ── Template Editor Panel (above cards) ── */}
        {isDataSection && (
          <div style={S.templatePanel}>
            <div style={S.templateHeader}>
              <div style={S.templateTitle}>
                <span>📐</span>
                <span>Format Templates</span>
                <span style={{ ...S.metaBadge, marginLeft: 4 }}>{templates.length}</span>
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {templates.length === 0 && (
                  <button style={S.previewBtn} onClick={handleSeedTemplates}>
                    🌱 Seed Defaults
                  </button>
                )}
                <button style={S.addBtn} onClick={() => setShowNewForm(!showNewForm)}>
                  + New Template
                </button>
                <button style={S.previewBtn} onClick={handleRegenerate}>
                  🔄 Regenerate
                </button>
              </div>
            </div>

            {/* Empty state */}
            {templates.length === 0 && !showNewForm && (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '12px 0' }}>
                No templates defined for {module}/{section}. Seed defaults or create a new template to start generating formatted training data.
              </div>
            )}

            {/* Existing templates */}
            {templates.map(tpl => {
              const draft = editDrafts[tpl.id] || { q: tpl.question_template, a: tpl.answer_template };
              const isDirty = draft.q !== tpl.question_template || draft.a !== tpl.answer_template;
              const tplPreviews = previews[tpl.id];
              return (
                <div key={tpl.id} style={S.templateCard}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>{tpl.name}</span>
                    <button
                      style={{ ...S.rejectBtn, fontSize: 10, padding: '2px 8px' }}
                      onClick={() => handleDeleteTemplate(tpl.id)}
                    >✕</button>
                  </div>
                  <div style={S.templateLabel}>Question Template</div>
                  <textarea
                    style={S.templateInput}
                    value={draft.q}
                    onChange={e => setEditDrafts(prev => ({ ...prev, [tpl.id]: { ...prev[tpl.id], q: e.target.value } }))}
                    rows={2}
                  />
                  <div style={{ ...S.templateLabel, marginTop: 8 }}>Answer Template</div>
                  <textarea
                    style={S.templateInput}
                    value={draft.a}
                    onChange={e => setEditDrafts(prev => ({ ...prev, [tpl.id]: { ...prev[tpl.id], a: e.target.value } }))}
                    rows={3}
                  />
                  <div style={S.templateActions}>
                    <button
                      style={{ ...S.saveBtn, opacity: isDirty ? 1 : 0.5 }}
                      disabled={!isDirty || savingId === tpl.id}
                      onClick={() => handleSaveTemplate(tpl)}
                    >
                      {savingId === tpl.id ? '…' : '💾 Save'}
                    </button>
                    <button style={S.previewBtn} onClick={() => handlePreviewTemplate(tpl)}>
                      👁 Preview
                    </button>
                  </div>
                  {/* Preview results */}
                  {tplPreviews && tplPreviews.length > 0 && (
                    <div style={{ marginTop: 8 }}>
                      {tplPreviews.map((pv, i) => (
                        <div key={i} style={S.previewBox}>
                          {pv.error ? (
                            <div style={{ color: 'var(--error, #ef4444)' }}>Error: {pv.error}</div>
                          ) : (
                            <>
                              <div><strong style={{ color: 'var(--accent, #f59e0b)' }}>User:</strong> {pv.user}</div>
                              <div style={{ marginTop: 4 }}><strong style={{ color: 'var(--primary, #7c3aed)' }}>Assistant:</strong> {pv.assistant}</div>
                            </>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* New template form */}
            {showNewForm && (
              <div style={S.templateCard}>
                <div style={S.templateLabel}>Name</div>
                <input
                  style={{ ...S.templateInput, minHeight: 28 }}
                  placeholder="e.g. hebbian_reasoning"
                  value={newTemplate.name}
                  onChange={e => setNewTemplate(prev => ({ ...prev, name: e.target.value }))}
                />
                <div style={{ ...S.templateLabel, marginTop: 8 }}>Question Template</div>
                <textarea
                  style={S.templateInput}
                  placeholder="Use {concept_a}, {concept_b}, {strength}, {fire_count}..."
                  value={newTemplate.question_template}
                  onChange={e => setNewTemplate(prev => ({ ...prev, question_template: e.target.value }))}
                  rows={2}
                />
                <div style={{ ...S.templateLabel, marginTop: 8 }}>Answer Template</div>
                <textarea
                  style={S.templateInput}
                  placeholder="Use {concept_a}, {concept_b}, {strength:.2f}, {fire_count}..."
                  value={newTemplate.answer_template}
                  onChange={e => setNewTemplate(prev => ({ ...prev, answer_template: e.target.value }))}
                  rows={3}
                />
                <div style={S.templateActions}>
                  <button
                    style={S.saveBtn}
                    disabled={!newTemplate.name}
                    onClick={handleCreateTemplate}
                  >
                    ✓ Create
                  </button>
                  <button style={S.previewBtn} onClick={() => setShowNewForm(false)}>Cancel</button>
                </div>
              </div>
            )}
          </div>
        )}

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
            {isDataSection && templates.length === 0 && ' Create templates above, then click Regenerate.'}
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
          const hasState = ex._has_state === true;
          const stateLoaded = loadedStates[ex._id];
          const stateIsLoading = loadingState.has(ex._id);

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
                  {meta.template ? <span style={{ ...S.metaBadge, background: 'rgba(16,185,129,0.1)', color: 'var(--success, #10b981)' }}>tpl:{String(meta.template)}</span> : null}
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

              {/* System prompt — inline if present, or on-demand toggle */}
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
              {!systemMsg && hasState && (
                <div>
                  {stateLoaded ? (
                    <div>
                      <button
                        style={S.systemToggle}
                        onClick={() => toggleSystem(ex._id)}
                      >
                        {showSystem ? '▾ System Prompt (loaded)' : '▸ System Prompt (loaded, click to expand)'}
                      </button>
                      {showSystem && (
                        <div style={{ ...S.msgContent, color: 'var(--text-muted)', fontSize: 12, marginTop: 4, marginBottom: 8, padding: '8px 10px', background: 'rgba(0,0,0,0.1)', borderRadius: 6 }}>
                          {stateLoaded}
                        </div>
                      )}
                    </div>
                  ) : (
                    <button
                      style={S.stateToggle}
                      disabled={stateIsLoading}
                      onClick={() => {
                        const query = userMsg?.content || 'system state';
                        handleLoadState(ex._id, query);
                      }}
                    >
                      {stateIsLoading ? '⏳ Building STATE…' : '⚡ Build STATE'}
                    </button>
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
