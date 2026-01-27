import React, { useState, useEffect } from 'react';
import './SystemPromptSidebar.css';

const API_BASE = 'http://localhost:8000';

interface StateData {
  state: string;
  char_count: number;
  query?: string;
}

interface SystemPromptSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  lastQuery?: string;
}

export const SystemPromptSidebar: React.FC<SystemPromptSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  lastQuery
}) => {
  const [data, setData] = useState<StateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchState = async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = query ? `?query=${encodeURIComponent(query)}` : '';
      const response = await fetch(`${API_BASE}/api/subconscious/build_state${params}`);
      if (!response.ok) throw new Error('Failed to fetch');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError('Could not load state');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isCollapsed) {
      fetchState(lastQuery);
    }
  }, [isCollapsed, lastQuery]);

  // Poll every 5 seconds when not collapsed
  useEffect(() => {
    if (isCollapsed) return;
    
    const interval = setInterval(() => fetchState(lastQuery), 5000);
    return () => clearInterval(interval);
  }, [isCollapsed]);

  if (isCollapsed) {
    return (
      <div className="system-prompt-sidebar collapsed">
        <button className="toggle-btn" onClick={onToggleCollapse} title="Show State">
          🧠
        </button>
      </div>
    );
  }

  return (
    <div className="system-prompt-sidebar">
      <div className="sidebar-header">
        <h3>State</h3>
        <div className="header-actions">
          <button className="refresh-btn" onClick={fetchState} title="Refresh">
            🔄
          </button>
          <button className="toggle-btn" onClick={onToggleCollapse} title="Hide">
            ✕
          </button>
        </div>
      </div>

      {loading && !data && (
        <div className="loading">Loading...</div>
      )}

      {error && (
        <div className="error">{error}</div>
      )}

      {data && (
        <div className="prompt-content">
          <div className="stats">
            <span className="stat">{data.char_count.toLocaleString()} chars</span>
          </div>

          <div className="prompt-text">
            <pre>{data.state}</pre>
          </div>
        </div>
      )}
    </div>
  );
};
