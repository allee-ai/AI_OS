import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './StartupPage.css';

export const StartupPage = () => {
  const [mode, setMode] = useState<'personal' | 'demo'>('personal');
  const [devMode, setDevMode] = useState(false);
  const [buildMethod, setBuildMethod] = useState<'local' | 'docker'>('local');
  const [starting, setStarting] = useState(false);
  const navigate = useNavigate();

  const handleStart = async () => {
    setStarting(true);
    
    try {
      // Set mode for this session
      await fetch('/api/services/mode', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          mode, 
          dev_mode: devMode,
          build_method: buildMethod 
        })
      });

      navigate('/');
    } catch (err) {
      console.error('Failed to set mode:', err);
      setStarting(false);
    }
  };

  return (
    <div className="startup-page">
      <div className="startup-container">
        <div className="startup-header">
          <div className="startup-logo">🧠</div>
          <h1>Nola</h1>
          <p className="startup-subtitle">AI Operating System</p>
        </div>

        <div className="startup-form">
          <div className="setting-group">
            <label className="setting-label">Data Mode</label>
            <div className="toggle-group">
              <button 
                className={`toggle-option ${mode === 'personal' ? 'active' : ''}`}
                onClick={() => setMode('personal')}
              >
                <span className="option-icon">👤</span>
                <div>
                  <div className="option-name">Personal</div>
                  <div className="option-desc">Your private data & conversations</div>
                </div>
              </button>
              <button 
                className={`toggle-option ${mode === 'demo' ? 'active' : ''}`}
                onClick={() => setMode('demo')}
              >
                <span className="option-icon">🎭</span>
                <div>
                  <div className="option-name">Demo</div>
                  <div className="option-desc">Sample data for showcasing</div>
                </div>
              </button>
            </div>
          </div>

          <div className="setting-group">
            <label className="setting-label">Build Method</label>
            <div className="toggle-group">
              <button 
                className={`toggle-option ${buildMethod === 'local' ? 'active' : ''}`}
                onClick={() => setBuildMethod('local')}
              >
                <span className="option-icon">💻</span>
                <div>
                  <div className="option-name">Local</div>
                  <div className="option-desc">Direct Python/Node execution</div>
                </div>
              </button>
              <button 
                className={`toggle-option ${buildMethod === 'docker' ? 'active' : ''}`}
                onClick={() => setBuildMethod('docker')}
              >
                <span className="option-icon">🐳</span>
                <div>
                  <div className="option-name">Docker</div>
                  <div className="option-desc">Containerized with Ollama</div>
                </div>
              </button>
            </div>
          </div>

          <div className="setting-group">
            <label className="setting-label">Features</label>
            <div className="toggle-row">
              <div className="toggle-info">
                <span className="toggle-icon">⚙️</span>
                <div>
                  <div className="toggle-name">Developer Mode</div>
                  <div className="toggle-desc">Enable advanced tools and debugging</div>
                </div>
              </div>
              <label className="switch">
                <input 
                  type="checkbox" 
                  checked={devMode}
                  onChange={(e) => setDevMode(e.target.checked)}
                />
                <span className="slider"></span>
              </label>
            </div>
          </div>

          <button 
            className="start-btn"
            onClick={handleStart}
            disabled={starting}
          >
            {starting ? 'Starting...' : 'Start Nola'}
          </button>
        </div>

        <div className="startup-footer">
          <div className="mode-preview">
            {mode === 'personal' ? '👤' : '🎭'} {mode.toUpperCase()}
            {devMode && ' + ⚙️ DEV'}
            <span className="build-indicator">
              {buildMethod === 'docker' ? '🐳' : '💻'} {buildMethod}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};