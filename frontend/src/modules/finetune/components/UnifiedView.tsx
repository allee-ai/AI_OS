import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';

/* ── Types ─────────────────────────────────────────── */

interface Example {
  _id: number;
  messages: { role: string; content: string }[];
  metadata?: Record<string, unknown>;
}

/* ── Constants ─────────────────────────────────────── */

const ALL_MODULES = ['linking_core', 'identity', 'philosophy', 'log', 'reflex', 'form', 'chat', 'docs'];
const ALL_SECTIONS = ['data', 'api', 'cli', 'schema', 'reasoning', 'generated', 'approved'];

const MODULE_ICONS: Record<string, string> = {
  linking_core: '🔗', identity: '🪞', philosophy: '🧠', log: '📝',
  reflex: '⚡', form: '🛠️', chat: '💬', docs: '📚',
};

const SECTION_ICONS: Record<string, string> = {
  data: '💾', api: '🌐', cli: '⌨️', schema: '🗃️',
  reasoning: '🧩', generated: '🤖', approved: '✅',
};

/* ── Styles ────────────────────────────────────────── */

const S = {
  container: {
    padding: '28px 32px', flex: 1, minWidth: 0, overflowY: 'auto' as const, height: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
  } as React.CSSProperties,
  header: {
    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20,
  } as React.CSSProperties,
  title: { fontSize: 22, fontWeight: 700, color: 'var(--text)' } as React.CSSProperties,
  badge: {
    fontSize: 12, fontWeight: 600, padding: '3px 10px', borderRadius: 6,
    background: 'rgba(124,58,237,0.12)', color: 'var(--primary, #7c3aed)',
  } as React.CSSProperties,
  filters: {
    display: 'flex', gap: 10, marginBottom: 20, flexWrap: 'wrap' as const,
    alignItems: 'center',
  } as React.CSSProperties,
  select: {
    padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text)', fontSize: 13,
    cursor: 'pointer',
  } as React.CSSProperties,
  searchInput: {
    padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)',
    background: 'var(--surface)', color: 'var(--text)', fontSize: 13,
    flex: 1, minWidth: 200,
  } as React.CSSProperties,
  card: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 10, padding: 14, marginBottom: 10,
  } as React.CSSProperties,
  cardHeader: {
    display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6,
  } as React.CSSProperties,
  metaBadge: {
    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
    background: 'rgba(124,58,237,0.1)', color: 'var(--primary, #7c3aed)',
  } as React.CSSProperties,
  moduleBadge: {
    fontSize: 10, fontWeight: 600, padding: '2px 6px', borderRadius: 4,
    background: 'rgba(16,185,129,0.12)', color: 'var(--success, #10b981)',
  } as React.CSSProperties,
  roleLabel: (role: string) => ({
    fontSize: 10, fontWeight: 700, textTransform: 'uppercase' as const,
    marginTop: 6, marginBottom: 2,
    color: role === 'assistant' ? 'var(--primary, #7c3aed)'
         : role === 'system' ? 'var(--text-muted)'
         : 'var(--accent, #f59e0b)',
  }) as React.CSSProperties,
  msgContent: {
    fontSize: 13, lineHeight: 1.5, color: 'var(--text)',
    whiteSpace: 'pre-wrap' as const,
  } as React.CSSProperties,
  systemToggle: {
    fontSize: 11, color: 'var(--text-muted)', cursor: 'pointer',
    background: 'none', border: 'none', fontWeight: 600, padding: 0,
  } as React.CSSProperties,
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
  empty: {
    textAlign: 'center' as const, padding: 40, color: 'var(--text-muted)', fontSize: 14,
  } as React.CSSProperties,
};

/* ── Component ─────────────────────────────────────── */

export const UnifiedView: React.FC = () => {
  const navigate = useNavigate();
  const [examples, setExamples] = useState<Example[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [moduleFilter, setModuleFilter] = useState('');
  const [sectionFilter, setSectionFilter] = useState('');
  const [search, setSearch] = useState('');
  const [expandedSystem, setExpandedSystem] = useState<Set<number>>(new Set());

  const fetchExamples = useCallback(async (p: number) => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(p), per_page: '50' });
    if (moduleFilter) params.set('module', moduleFilter);
    if (sectionFilter) params.set('section', sectionFilter);
    try {
      const res = await fetch(`/api/finetune/unified?${params}`);
      if (res.ok) {
        const d = await res.json();
        let items = d.examples ?? [];
        // Client-side text search
        if (search.trim()) {
          const q = search.toLowerCase();
          items = items.filter((ex: Example) =>
            ex.messages?.some(m => m.content.toLowerCase().includes(q))
          );
        }
        setExamples(items);
        setTotal(d.total ?? 0);
        setPages(d.pages ?? 0);
      }
    } catch { /* ignore */ }
    setLoading(false);
  }, [moduleFilter, sectionFilter, search]);

  useEffect(() => { setPage(1); }, [moduleFilter, sectionFilter, search]);
  useEffect(() => { fetchExamples(page); }, [page, fetchExamples]);

  const toggleSystem = (id: number) => {
    setExpandedSystem(prev => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  return (
    <div style={S.container}>
      <div style={S.header}>
        <span style={{ fontSize: 28 }}>🔥</span>
        <span style={S.title}>Unified Training Data</span>
        <span style={S.badge}>{total.toLocaleString()} total</span>
      </div>

      {/* Filters */}
      <div style={S.filters}>
        <select style={S.select} value={moduleFilter} onChange={e => setModuleFilter(e.target.value)}>
          <option value="">All Modules</option>
          {ALL_MODULES.map(m => (
            <option key={m} value={m}>{MODULE_ICONS[m] || '📦'} {m}</option>
          ))}
        </select>
        <select style={S.select} value={sectionFilter} onChange={e => setSectionFilter(e.target.value)}>
          <option value="">All Sections</option>
          {ALL_SECTIONS.map(s => (
            <option key={s} value={s}>{SECTION_ICONS[s] || '📄'} {s}</option>
          ))}
        </select>
        <input
          style={S.searchInput}
          type="text"
          placeholder="Search examples…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      {loading && <div style={S.empty}>Loading…</div>}
      {!loading && examples.length === 0 && <div style={S.empty}>No examples match filters.</div>}

      {/* Example cards */}
      {examples.map(ex => {
        const meta = ex.metadata || {};
        const systemMsg = ex.messages?.find(m => m.role === 'system');
        const userMsg = ex.messages?.find(m => m.role === 'user');
        const assistantMsg = ex.messages?.find(m => m.role === 'assistant');
        const showSystem = expandedSystem.has(ex._id);
        const source = String(meta.source || '');
        const section = String(meta.section || '');

        return (
          <div
            key={ex._id}
            style={{ ...S.card, cursor: 'pointer' }}
            onClick={() => {
              if (source && section) navigate(`/dev/${source}/${section}`);
            }}
          >
            <div style={S.cardHeader}>
              {source && <span style={S.moduleBadge}>{MODULE_ICONS[source] || '📦'} {source}</span>}
              {section && <span style={S.metaBadge}>{SECTION_ICONS[section] || '📄'} {section}</span>}
              {meta.type ? <span style={S.metaBadge}>{String(meta.type)}</span> : null}
            </div>

            {systemMsg && (
              <div>
                <button style={S.systemToggle} onClick={e => { e.stopPropagation(); toggleSystem(ex._id); }}>
                  {showSystem ? '▾ System' : '▸ System'}
                </button>
                {showSystem && (
                  <div style={{ ...S.msgContent, color: 'var(--text-muted)', fontSize: 12, marginTop: 4, marginBottom: 8, padding: '8px 10px', background: 'rgba(0,0,0,0.1)', borderRadius: 6 }}>
                    {systemMsg.content}
                  </div>
                )}
              </div>
            )}

            {userMsg && (
              <div>
                <div style={S.roleLabel('user')}>User</div>
                <div style={S.msgContent}>{userMsg.content}</div>
              </div>
            )}

            {assistantMsg && (
              <div>
                <div style={S.roleLabel('assistant')}>Assistant</div>
                <div style={{ ...S.msgContent, maxHeight: 200, overflow: 'hidden' }}>
                  {assistantMsg.content}
                </div>
              </div>
            )}
          </div>
        );
      })}

      {/* Pagination */}
      {pages > 1 && (
        <div style={S.pagination}>
          <button style={S.navBtn} disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
            ← Prev
          </button>
          {Array.from({ length: Math.min(pages, 7) }, (_, i) => {
            const p = pages <= 7 ? i + 1 : Math.max(1, Math.min(page - 3 + i, pages));
            return (
              <button key={p} style={S.pageBtn(p === page)} onClick={() => setPage(p)}>{p}</button>
            );
          })}
          <button style={S.navBtn} disabled={page >= pages} onClick={() => setPage(p => Math.min(pages, p + 1))}>
            Next →
          </button>
        </div>
      )}
    </div>
  );
};
