import React, { useState, useEffect } from 'react';
import './SystemPromptSidebar.css';

const API_BASE = 'http://localhost:8000';

interface SystemPromptData {
  level: number;
  system_prompt: string;
  consciousness_context: string;
  char_count: number;
  timestamp: string;
}

interface SystemPromptSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
}

export const SystemPromptSidebar: React.FC<SystemPromptSidebarProps> = ({
  isCollapsed,
  onToggleCollapse
}) => {
  const [data, setData] = useState<SystemPromptData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState(2);
  const [showFull, setShowFull] = useState(false);

  const fetchSystemPrompt = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/subconscious/context?level=${level}`);
      if (!response.ok) throw new Error('Failed to fetch');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError('Could not load system prompt');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!isCollapsed) {
      fetchSystemPrompt();
    }
  }, [level, isCollapsed]);

  // Poll every 5 seconds when not collapsed
  useEffect(() => {
    if (isCollapsed) return;
    
    const interval = setInterval(fetchSystemPrompt, 5000);
    return () => clearInterval(interval);
  }, [level, isCollapsed]);

  if (isCollapsed) {
    return (
      <div className="system-prompt-sidebar collapsed">
        <button className="toggle-btn" onClick={onToggleCollapse} title="Show System Prompt">
          📋
        </button>
      </div>
    );
  }

  return (
    <div className="system-prompt-sidebar">
      <div className="sidebar-header">
        <h3>System Prompt</h3>
        <button className="toggle-btn" onClick={onToggleCollapse} title="Hide">
          ✕
        </button>
      </div>

      <div className="level-selector">
        <span className="level-label">Context Level:</span>
        <div className="level-buttons">
          {[1, 2, 3].map(l => (
            <button
              key={l}
              className={`level-btn ${level === l ? 'active' : ''}`}
              onClick={() => setLevel(l)}
            >
              L{l}
            </button>
          ))}
        </div>
        <button className="refresh-btn" onClick={fetchSystemPrompt} title="Refresh">
          🔄
        </button>
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
            <span className="stat">L{data.level}</span>
          </div>

          <div className="view-toggle">
            <button
              className={`view-btn ${!showFull ? 'active' : ''}`}
              onClick={() => setShowFull(false)}
            >
              Context Only
            </button>
            <button
              className={`view-btn ${showFull ? 'active' : ''}`}
              onClick={() => setShowFull(true)}
            >
              Full Prompt
            </button>
          </div>

          <div className="prompt-text">
            <pre>{showFull ? data.system_prompt : data.consciousness_context}</pre>
          </div>
        </div>
      )}
    </div>
  );
};
