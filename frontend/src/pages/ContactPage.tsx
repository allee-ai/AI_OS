import { Link } from 'react-router-dom';
import './ContactPage.css';

export const ContactPage = () => {
  return (
    <div className="page-wrapper contact-page">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>👤 Contact & About</h1>
      </div>

      <div className="contact-content">
        <section className="contact-card">
          <h2>AI OS</h2>
          <p className="tagline">Adaptive Assistive Learning Agent</p>
          
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">Version</span>
              <span className="info-value">0.9.0</span>
            </div>
            <div className="info-item">
              <span className="info-label">Status</span>
              <span className="info-value status-active">Active Development</span>
            </div>
            <div className="info-item">
              <span className="info-label">Architecture</span>
              <span className="info-value">HEA (Hierarchical Episodic Attention)</span>
            </div>
            <div className="info-item">
              <span className="info-label">Runtime</span>
              <span className="info-value">Ollama + FastAPI + React</span>
            </div>
          </div>
        </section>

        <section className="contact-card">
          <h2>Project</h2>
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">Repository</span>
              <span className="info-value">
                <a href="https://github.com/your-repo/ai-os" target="_blank" rel="noopener">
                  github.com/ai-os
                </a>
              </span>
            </div>
            <div className="info-item">
              <span className="info-label">License</span>
              <span className="info-value">MIT</span>
            </div>
          </div>
        </section>

        <section className="contact-card">
          <h2>Core Concepts</h2>
          <div className="concepts-list">
            <div className="concept">
              <span className="concept-icon">🧵</span>
              <div>
                <strong>5 Data Threads</strong>
                <p>Identity, Log, Form, Philosophy, Reflex — modeled after brain regions</p>
              </div>
            </div>
            <div className="concept">
              <span className="concept-icon">📊</span>
              <div>
                <strong>HEA Context Levels</strong>
                <p>L1 (quick), L2 (standard), L3 (full) — attention-based context assembly</p>
              </div>
            </div>
            <div className="concept">
              <span className="concept-icon">🔗</span>
              <div>
                <strong>Linking Core</strong>
                <p>Hebbian learning: "neurons that fire together, wire together"</p>
              </div>
            </div>
            <div className="concept">
              <span className="concept-icon">🤖</span>
              <div>
                <strong>Agent Autonomy</strong>
                <p>Assistive, not autonomous — always defers to user decisions</p>
              </div>
            </div>
          </div>
        </section>

        <section className="contact-card">
          <h2>Support</h2>
          <p className="muted">
            For issues, feature requests, or contributions, please open an issue on GitHub
            or check the documentation.
          </p>
          <div className="button-row">
            <Link to="/docs" className="btn-secondary">View Docs</Link>
          </div>
        </section>
      </div>
    </div>
  );
};
