import React, { useState, useEffect, useCallback } from 'react';
import { Sidebar } from '../components/Sidebar';
import type { SidebarModule } from '../components/Sidebar';
import { FinetunePanel } from '../components/FinetunePanel';
import { UnifiedView } from '../components/UnifiedView';
import { GenerationPanel } from '../components/GenerationPanel';
import { ToolCallingPanel } from '../components/ToolCallingPanel';

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

function statCount(stats: ModuleStats): number {
  if (stats.error) return 0;
  return stats.examples ?? stats.concepts ?? stats.pairs ?? stats.facts ?? stats.tools ?? stats.turns ?? 0;
}

export const DevDashboard: React.FC = () => {
  const [modules, setModules] = useState<FTModule[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

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

  const toggleModule = async (name: string, enabled: boolean) => {
    await fetch(`/api/finetune/modules/${encodeURIComponent(name)}/enabled?enabled=${!enabled}`, {
      method: 'PUT',
    });
    setModules(prev => prev.map(m => m.name === name ? { ...m, enabled: !enabled } : m));
  };

  const sidebarModules: SidebarModule[] = modules.map(m => ({
    name: m.name,
    enabled: m.enabled,
    count: statCount(m.stats),
  }));

  return (
    <div className="dashboard-container">
      <Sidebar modules={sidebarModules} selected={selected} onSelect={setSelected} />
      <div className="main-content">
        {selected === '__unified__' ? (
          <UnifiedView />
        ) : selected === '__generator__' ? (
          <GenerationPanel />
        ) : selected === '__tool_eval__' ? (
          <ToolCallingPanel />
        ) : (
          <FinetunePanel
            selectedModule={selected}
            modules={modules}
            onToggleModule={toggleModule}
            onRefresh={fetchModules}
          />
        )}
      </div>
    </div>
  );
};
