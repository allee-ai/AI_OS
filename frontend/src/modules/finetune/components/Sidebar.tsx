import React from 'react';
import { NavLink } from 'react-router-dom';
import './Sidebar.css';

export interface SidebarModule {
  name: string;
  enabled: boolean;
  count: number;
}

interface SidebarProps {
  modules: SidebarModule[];
  selected: string | null;
  onSelect: (name: string) => void;
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

export const Sidebar: React.FC<SidebarProps> = ({ modules, selected, onSelect }) => {
  return (
    <nav className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">🔥</div>
        <h3>Training</h3>
      </div>

      <div className="sidebar-links">
        <button
          className={`module-btn ${selected === '__unified__' ? 'active' : ''}`}
          onClick={() => onSelect('__unified__')}
          style={{ borderBottom: '1px solid var(--border)', marginBottom: 4 }}
        >
          <span className="module-icon">🔥</span>
          <span className="module-name">Unified</span>
          <span className="module-count">all</span>
        </button>
        {modules.map(m => (
          <button
            key={m.name}
            className={`module-btn ${selected === m.name ? 'active' : ''} ${!m.enabled ? 'disabled' : ''}`}
            onClick={() => onSelect(m.name)}
          >
            <span className="module-icon">{MODULE_ICONS[m.name] || '📦'}</span>
            <span className="module-name">{m.name}</span>
            <span className="module-count">{m.count.toLocaleString()}</span>
          </button>
        ))}
      </div>

      <div className="sidebar-footer">
        <NavLink to="/" className="nav-link">← Back to App</NavLink>
      </div>
    </nav>
  );
};
