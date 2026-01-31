import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Dashboard.css';

// Spiral icon served from public folder
const spiral = '/aios-spiral.png';

interface AgentStatus {
  status: string;
  name: string;
  model?: string;
}

export const Dashboard = () => {
  const navigate = useNavigate();
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);

  useEffect(() => {
    // Fetch agent status
    fetch('http://localhost:8000/api/chat/agent-status')
      .then(res => res.json())
      .then(data => setAgentStatus(data))
      .catch(() => setAgentStatus({ status: 'offline', name: 'Agent' }));
  }, []);

  const isAwake = agentStatus?.status === 'awake';
  const statusColor = isAwake ? 'var(--success)' : 'var(--text-muted)';

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="status-indicator" style={{ background: statusColor }} />
        <div className="header-text">
          <h1>AI_OS</h1>
          <span className="status-label">{agentStatus?.status || 'connecting...'}</span>
        </div>
        {agentStatus?.model && (
          <span className="model-badge">{agentStatus.model}</span>
        )}
        <button 
          className="settings-btn"
          onClick={() => navigate('/settings')}
          title="Settings"
        >
          ⚙️
        </button>
      </header>

      <nav className="dashboard-nav">
        <Link to="/chat" className="nav-card">
          <span className="nav-icon">💬</span>
          <span className="nav-label">Chat</span>
          <span className="nav-desc">Chat</span>
        </Link>
        
        <Link to="/feeds" className="nav-card">
          <span className="nav-icon">📡</span>
          <span className="nav-label">Feeds</span>
          <span className="nav-desc">External API sources</span>
        </Link>
        
        <Link to="/threads" className="nav-card">
          <img src={spiral} className="nav-icon-img" alt="Agent" />
          <span className="nav-label">Agent</span>
          <span className="nav-desc">Identity, Log, Memory...</span>
        </Link>
        
        <Link to="/workspace" className="nav-card">
          <span className="nav-icon">📂</span>
          <span className="nav-label">Workspace</span>
          <span className="nav-desc">Your files</span>
        </Link>

        <Link to="/docs" className="nav-card">
          <span className="nav-icon">📖</span>
          <span className="nav-label">Docs</span>
          <span className="nav-desc">Documentation</span>
        </Link>
        
        <Link to="/contact" className="nav-card">
          <span className="nav-icon">👤</span>
          <span className="nav-label">Contact</span>
          <span className="nav-desc">About & Info</span>
        </Link>
      </nav>

      <section className="dashboard-section">
        <Link to="/dev" className="dev-link">⚙ dev</Link>
      </section>
    </div>
  );
};
