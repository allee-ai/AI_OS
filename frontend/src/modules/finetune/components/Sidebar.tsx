import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export interface SidebarModule {
  name: string;
  enabled: boolean;
  count: number;
  sections?: Record<string, { description: string; examples: number }>;
}

interface SidebarProps {
  modules: SidebarModule[];
  selected: string | null;
  selectedSection: string | null;
  expandedModule: string | null;
  onSelect: (name: string) => void;
  onSelectSection: (module: string, section: string) => void;
  onToggleExpand: (name: string) => void;
}

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

const SECTION_ICONS: Record<string, string> = {
  data: '💾', api: '🌐', cli: '⌨️', schema: '🗃️',
  templates: '📐', reasoning: '🧩', generated: '🤖',
  approved: '✅', curated: '✍️',
};

export const Sidebar: React.FC<SidebarProps> = ({
  modules, selected, selectedSection, expandedModule,
  onSelect, onSelectSection, onToggleExpand,
}) => {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">🔥</div>
        <h3>Training</h3>
      </div>

      <div className="sidebar-links">
        {/* Global views */}
        <button
          className={`module-btn ${selected === '__unified__' ? 'active' : ''}`}
          onClick={() => onSelect('__unified__')}
          style={{ borderBottom: '1px solid var(--border)', marginBottom: 2 }}
        >
          <span className="module-icon">🔥</span>
          <span className="module-name">Unified</span>
          <span className="module-count">all</span>
        </button>
        <button
          className={`module-btn ${selected === '__generator__' ? 'active' : ''}`}
          onClick={() => onSelect('__generator__')}
          style={{ borderBottom: '1px solid var(--border)', marginBottom: 2 }}
        >
          <span className="module-icon">🤖</span>
          <span className="module-name">Generator</span>
          <span className="module-count">kimi</span>
        </button>
        <button
          className={`module-btn ${selected === '__tool_eval__' ? 'active' : ''}`}
          onClick={() => onSelect('__tool_eval__')}
          style={{ borderBottom: '1px solid var(--border)', marginBottom: 6 }}
        >
          <span className="module-icon">🔧</span>
          <span className="module-name">Tool Eval</span>
          <span className="module-count">eval</span>
        </button>

        {/* Module list with expandable sections */}
        {modules.map(m => {
          const isExpanded = expandedModule === m.name;
          const isModuleSelected = selected === m.name && !selectedSection;
          const sectionKeys = m.sections ? Object.keys(m.sections) : [];

          return (
            <div key={m.name}>
              <button
                className={`module-btn ${isModuleSelected ? 'active' : ''} ${!m.enabled ? 'disabled' : ''}`}
                onClick={() => {
                  onToggleExpand(m.name);
                  onSelect(m.name);
                }}
              >
                <span className="module-icon">{isExpanded ? '▾' : '▸'}</span>
                <span className="module-icon">{MODULE_ICONS[m.name] || '📦'}</span>
                <span className="module-name">{m.name}</span>
                <span className="module-count">{m.count.toLocaleString()}</span>
              </button>

              {/* Nested sections */}
              {isExpanded && (
                <div className="section-list">
                  {sectionKeys.map(sec => {
                    const info = m.sections?.[sec];
                    const isActive = selected === m.name && selectedSection === sec;
                    return (
                      <button
                        key={sec}
                        className={`section-btn ${isActive ? 'active' : ''}`}
                        onClick={() => onSelectSection(m.name, sec)}
                      >
                        <span className="section-icon">{SECTION_ICONS[sec] || '📄'}</span>
                        <span className="section-name">{sec}</span>
                        {info && <span className="section-count">{info.examples}</span>}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="sidebar-footer">
        <NavLink to="/" className="nav-link">← Back to App</NavLink>
      </div>
    </nav>
  );
};
