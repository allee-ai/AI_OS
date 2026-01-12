import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import './Dashboard.css';

interface AgentStatus {
  status: string;
  name: string;
  model?: string;
}

interface ThreadHealth {
  name: string;
  status: string;  // "ok", "degraded", "error"
  message: string;
  has_data: boolean;
}

interface IntrospectionData {
  status: string;
  overall_health: string;
  recent_events: { message: string }[];
  identity_facts: { fact: string }[];
}

export const Dashboard = () => {
  const navigate = useNavigate();
  const [agentStatus, setAgentStatus] = useState<AgentStatus | null>(null);
  const [threads, setThreads] = useState<Record<string, ThreadHealth>>({});
  const [introspection, setIntrospection] = useState<IntrospectionData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch agent status
    fetch('http://localhost:8000/api/chat/agent-status')
      .then(res => res.json())
      .then(data => setAgentStatus(data))
      .catch(() => setAgentStatus({ status: 'offline', name: 'Nola' }));

    // Fetch real thread health
    fetch('http://localhost:8000/api/introspection/threads/health')
      .then(res => res.json())
      .then(data => {
        setThreads(data.threads || {});
        setLoading(false);
      })
      .catch(() => setLoading(false));

    // Fetch introspection for recent events
    fetch('http://localhost:8000/api/introspection/')
      .then(res => res.json())
      .then(data => setIntrospection(data))
      .catch(() => {});
  }, []);

  const isAwake = agentStatus?.status === 'awake';
  const statusColor = isAwake ? 'var(--success)' : 'var(--text-muted)';

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="status-indicator" style={{ background: statusColor }} />
        <div className="header-text">
          <h1>Nola</h1>
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
          <span className="nav-desc">Talk to Nola</span>
        </Link>
        
        <Link to="/stimuli" className="nav-card">
          <span className="nav-icon">�</span>
          <span className="nav-label">Stimuli</span>
          <span className="nav-desc">External API sources</span>
        </Link>
        
        <Link to="/threads" className="nav-card">
          <span className="nav-icon">🧵</span>
          <span className="nav-label">Threads</span>
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
        <h2>System Status</h2>
        <div className="thread-grid">
          {loading ? (
            <span className="muted">Connecting...</span>
          ) : Object.keys(threads).length > 0 ? (
            Object.values(threads).map(t => (
              <div key={t.name} className={`thread-chip ${t.status}`} title={t.message}>
                <span className="chip-dot" />
                {t.name}
              </div>
            ))
          ) : (
            <span className="muted">No threads found</span>
          )}
        </div>
        {introspection?.identity_facts?.[0]?.fact && (
          <p className="muted" style={{ marginTop: 12, fontSize: '0.8rem' }}>
            {introspection.identity_facts[0].fact}
          </p>
        )}
      </section>
    </div>
  );
};