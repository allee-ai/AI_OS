import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import type { SidebarModule } from '../components/Sidebar';
import { FinetunePanel } from '../components/FinetunePanel';
import { GenerationPanel } from '../components/GenerationPanel';
import { ToolCallingPanel } from '../components/ToolCallingPanel';
import { GeneralKnowledgePanel } from '../components/GeneralKnowledgePanel';
import { SectionDetailPage } from './SectionDetailPage';

/* ── Types ────────────────────────────────────────── */

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

type SectionMap = Record<string, { description: string; examples: number }>;

function statCount(stats: ModuleStats): number {
  if (stats.error) return 0;
  return stats.examples ?? stats.concepts ?? stats.pairs ?? stats.facts ?? stats.tools ?? stats.turns ?? 0;
}

/* ── Constants ────────────────────────────────────── */

const MODULE_ICONS: Record<string, string> = {
  linking_core: '🔗', identity: '🪞', philosophy: '🧠', log: '📝',
  reflex: '⚡', form: '🛠️', chat: '💬', docs: '📚',
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

const SECTION_ICONS: Record<string, string> = {
  data: '💾', api: '🌐', cli: '⌨️', schema: '🗃️',
  reasoning: '🧩', generated: '🤖', approved: '✅', curated: '✍️',
};

/* ── Module overview styles ───────────────────────── */

const OS = {
  container: {
    padding: '28px 32px', flex: 1, overflowY: 'auto' as const, height: '100vh',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Inter", sans-serif',
  } as React.CSSProperties,
  header: { display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 } as React.CSSProperties,
  title: { fontSize: 22, fontWeight: 700, color: 'var(--text)', display: 'flex', alignItems: 'center', gap: 10 } as React.CSSProperties,
  desc: { fontSize: 13, color: 'var(--text-muted)', marginBottom: 24 } as React.CSSProperties,
  toggle: (on: boolean) => ({
    display: 'flex', alignItems: 'center', gap: 8, fontSize: 12,
    color: on ? 'var(--success, #10b981)' : 'var(--text-muted)',
    cursor: 'pointer', background: 'none', border: 'none', fontWeight: 600, marginLeft: 'auto',
  }) as React.CSSProperties,
  track: (on: boolean) => ({
    width: 38, height: 20, borderRadius: 10,
    background: on ? 'var(--success, #10b981)' : 'var(--bg-tertiary, #444)',
    position: 'relative' as const, transition: 'background .2s',
  }) as React.CSSProperties,
  dot: (on: boolean) => ({
    position: 'absolute' as const, top: 3, left: on ? 20 : 3,
    width: 14, height: 14, borderRadius: '50%', background: '#fff', transition: 'left .2s',
  }) as React.CSSProperties,
  total: { fontSize: 14, color: 'var(--text-muted)', marginBottom: 20 } as React.CSSProperties,
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 12, marginBottom: 28,
  } as React.CSSProperties,
  card: {
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 10, padding: '14px 16px', cursor: 'pointer', transition: 'border-color .2s',
  } as React.CSSProperties,
  cardLabel: { display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, fontWeight: 600, color: 'var(--text)', marginBottom: 6 } as React.CSSProperties,
  cardCount: { fontSize: 24, fontWeight: 700, color: 'var(--primary, #7c3aed)' } as React.CSSProperties,
  cardDesc: { fontSize: 11, color: 'var(--text-muted)', marginTop: 4 } as React.CSSProperties,
};

/* ── Component ────────────────────────────────────── */

export const DevDashboard: React.FC = () => {
  const [modules, setModules] = useState<FTModule[]>([]);
  const [selected, setSelected] = useState<string | null>('__unified__');
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [expandedModule, setExpandedModule] = useState<string | null>(null);
  const [moduleSections, setModuleSections] = useState<Record<string, SectionMap>>({});

  /* ── Data fetching ── */

  const fetchModules = useCallback(async () => {
    try {
      const res = await fetch('/api/finetune/modules');
      if (res.ok) {
        const d = await res.json();
        setModules(d.modules ?? []);
      }
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchModules(); }, [fetchModules]);

  useEffect(() => {
    const iv = setInterval(fetchModules, 10_000);
    return () => clearInterval(iv);
  }, [fetchModules]);

  const fetchSections = useCallback(async (name: string) => {
    try {
      const res = await fetch(`/api/finetune/modules/${encodeURIComponent(name)}/sections`);
      if (res.ok) {
        const d = await res.json();
        setModuleSections(prev => ({ ...prev, [name]: d.sections ?? {} }));
      }
    } catch { /* ignore */ }
  }, []);

  /* ── Navigation handlers ── */

  const handleSelect = (name: string) => {
    setSelected(name);
    setSelectedSection(null);
  };

  const handleSelectSection = (mod: string, sec: string) => {
    setSelected(mod);
    setSelectedSection(sec);
  };

  const handleToggleExpand = (name: string) => {
    const wasExpanded = expandedModule === name;
    setExpandedModule(wasExpanded ? null : name);
    if (!wasExpanded && !moduleSections[name]) {
      fetchSections(name);
    }
  };

  const toggleModule = async (name: string, enabled: boolean) => {
    await fetch(`/api/finetune/modules/${encodeURIComponent(name)}/enabled?enabled=${!enabled}`, {
      method: 'PUT',
    });
    setModules(prev => prev.map(m => m.name === name ? { ...m, enabled: !enabled } : m));
  };

  /* ── Sidebar data ── */

  const sidebarModules: SidebarModule[] = modules.map(m => ({
    name: m.name,
    enabled: m.enabled,
    count: statCount(m.stats),
    sections: moduleSections[m.name],
  }));

  const isSpecialView = selected?.startsWith('__');
  const mod = modules.find(m => m.name === selected);
  const sections = selected && !isSpecialView ? moduleSections[selected] || {} : {};
  const totalExamples = Object.values(sections).reduce((s, sec) => s + (sec.examples || 0), 0);

  /* ── Module overview ── */

  const renderModuleOverview = () => {
    if (!mod) return null;
    return (
      <div style={OS.container}>
        <div style={OS.header}>
          <div style={OS.title}>
            <span>{MODULE_ICONS[mod.name] || '📦'}</span>
            <span>{mod.name}</span>
          </div>
          <button style={OS.toggle(mod.enabled)} onClick={() => toggleModule(mod.name, mod.enabled)}>
            <div style={OS.track(mod.enabled)}>
              <div style={OS.dot(mod.enabled)} />
            </div>
            {mod.enabled ? 'Enabled' : 'Disabled'}
          </button>
        </div>
        <div style={OS.desc}>{MODULE_DESC[mod.name] || ''}</div>
        <div style={OS.total}>
          {Object.keys(sections).length} sections · {totalExamples.toLocaleString()} total examples
        </div>
        <div style={OS.grid}>
          {Object.entries(sections).map(([key, sec]) => (
            <div
              key={key}
              style={OS.card}
              onClick={() => handleSelectSection(mod.name, key)}
              onMouseEnter={e => (e.currentTarget.style.borderColor = 'var(--primary, #7c3aed)')}
              onMouseLeave={e => (e.currentTarget.style.borderColor = 'var(--border)')}
            >
              <div style={OS.cardLabel}>
                <span>{SECTION_ICONS[key] || '📄'}</span>
                <span>{key}</span>
              </div>
              <div style={OS.cardCount}>{sec.examples.toLocaleString()}</div>
              <div style={OS.cardDesc}>{sec.description}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  /* ── Render ── */

  return (
    <div className="dashboard-container">
      <Sidebar
        modules={sidebarModules}
        selected={selected}
        selectedSection={selectedSection}
        expandedModule={expandedModule}
        onSelect={handleSelect}
        onSelectSection={handleSelectSection}
        onToggleExpand={handleToggleExpand}
      />
      <div className="main-content">
        {selected === '__unified__' || !selected ? (
          <FinetunePanel
            selectedModule={null}
            modules={modules}
            onToggleModule={toggleModule}
            onRefresh={fetchModules}
          />
        ) : selected === '__generator__' ? (
          <GenerationPanel />
        ) : selected === '__tool_eval__' ? (
          <ToolCallingPanel />
        ) : selected === '__general_knowledge__' ? (
          <GeneralKnowledgePanel />
        ) : selected && selectedSection ? (
          <SectionDetailPage
            moduleOverride={selected}
            sectionOverride={selectedSection}
            embedded
          />
        ) : mod ? (
          renderModuleOverview()
        ) : null}
      </div>
    </div>
  );
};
