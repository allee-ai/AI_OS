import { useState, useEffect } from 'react';

interface ServiceConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
}

interface PendingFact {
  id: number;
  text: string;
  source: string;
  timestamp: string;
  score?: number;
}

interface ConsolidationDashboardProps {
  config: ServiceConfig | null;
  status: string;
  message?: string;
  onChangesMade: () => void;
  onSave: (config: ServiceConfig) => Promise<void>;
}

export const ConsolidationDashboard = ({ config, status, message, onChangesMade, onSave }: ConsolidationDashboardProps) => {
  const [localConfig, setLocalConfig] = useState<ServiceConfig>({
    enabled: true,
    settings: {
      l2_threshold: 4.0,
      l3_threshold: 3.0,
      discard_threshold: 2.0,
      max_facts_per_run: 50,
      auto_consolidate: true,
      auto_trigger_after_convos: 5,
    }
  });
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [pendingFacts, setPendingFacts] = useState<PendingFact[]>([]);
  const [lastResult, setLastResult] = useState<string | null>(null);

  useEffect(() => {
    if (config) {
      setLocalConfig({
        enabled: config.enabled,
        settings: { ...localConfig.settings, ...config.settings }
      });
    }
    
    // Fetch pending facts
    fetchPendingFacts();
  }, [config]);

  const fetchPendingFacts = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/services/consolidation/pending');
      if (res.ok) {
        const data = await res.json();
        setPendingFacts(data.facts || []);
      }
    } catch (err) {
      console.error('Failed to fetch pending facts:', err);
    }
  };

  const handleChange = (key: string, value: unknown) => {
    setLocalConfig(prev => ({
      ...prev,
      settings: { ...prev.settings, [key]: value }
    }));
    onChangesMade();
  };

  const handleSave = async () => {
    setSaving(true);
    await onSave(localConfig);
    setSaving(false);
  };

  const handleRunNow = async () => {
    setRunning(true);
    setLastResult(null);
    try {
      const res = await fetch('http://localhost:8000/api/services/consolidation/run', {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok) {
        setLastResult(`✅ Processed ${data.facts_processed} facts: ${data.promoted_l2} to L2, ${data.promoted_l3} to L3, ${data.discarded} discarded`);
        fetchPendingFacts();
      } else {
        setLastResult(`❌ Error: ${data.detail}`);
      }
    } catch (err) {
      setLastResult('❌ Failed to run consolidation');
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">📦</span>
        <div>
          <h1>Consolidation Daemon</h1>
          <p className="settings-description">Promotes facts from short-term to long-term memory</p>
        </div>
      </div>

      <section className="settings-section">
        <h3>Status</h3>
        <div className="status-card">
          <div className={`status-indicator-large ${status}`}>
            <span className="status-dot-large" />
            <span className="status-text">{status}</span>
          </div>
          {message && <p className="status-message">{message}</p>}
          <div className="stats-row">
            <span className="stat">
              <strong>{pendingFacts.length}</strong> facts pending
            </span>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <h3>Manual Control</h3>
        <button 
          className="btn-secondary" 
          onClick={handleRunNow}
          disabled={running || pendingFacts.length === 0}
        >
          {running ? 'Running...' : '▶️ Run Consolidation Now'}
        </button>
        {lastResult && (
          <p className={`result-message ${lastResult.includes('Error') ? 'error' : 'success'}`}>
            {lastResult}
          </p>
        )}
      </section>

      <section className="settings-section">
        <h3>Thresholds</h3>
        <p className="setting-hint">
          Facts are scored 1-5 on permanence, relevance, and identity. 
          The total score determines which memory level they're promoted to.
        </p>

        <div className="setting-row">
          <label>L2 threshold (high importance)</label>
          <input 
            type="number" 
            min={1}
            max={5}
            step={0.5}
            value={localConfig.settings.l2_threshold as number}
            onChange={(e) => handleChange('l2_threshold', parseFloat(e.target.value))}
            style={{ width: 80 }}
          />
        </div>

        <div className="setting-row">
          <label>L3 threshold (medium importance)</label>
          <input 
            type="number" 
            min={1}
            max={5}
            step={0.5}
            value={localConfig.settings.l3_threshold as number}
            onChange={(e) => handleChange('l3_threshold', parseFloat(e.target.value))}
            style={{ width: 80 }}
          />
        </div>

        <div className="setting-row">
          <label>Discard threshold (below = delete)</label>
          <input 
            type="number" 
            min={0}
            max={5}
            step={0.5}
            value={localConfig.settings.discard_threshold as number}
            onChange={(e) => handleChange('discard_threshold', parseFloat(e.target.value))}
            style={{ width: 80 }}
          />
        </div>
      </section>

      <section className="settings-section">
        <h3>Automation</h3>

        <div className="setting-row">
          <label>Enabled</label>
          <input 
            type="checkbox" 
            checked={localConfig.enabled}
            onChange={(e) => {
              setLocalConfig(prev => ({ ...prev, enabled: e.target.checked }));
              onChangesMade();
            }}
          />
        </div>

        <div className="setting-row">
          <label>Auto-consolidate</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.auto_consolidate as boolean}
            onChange={(e) => handleChange('auto_consolidate', e.target.checked)}
          />
        </div>

        <div className="setting-row">
          <label>Run after N conversations</label>
          <input 
            type="number" 
            min={1}
            max={50}
            value={localConfig.settings.auto_trigger_after_convos as number}
            onChange={(e) => handleChange('auto_trigger_after_convos', parseInt(e.target.value))}
            style={{ width: 80 }}
          />
        </div>

        <div className="setting-row">
          <label>Max facts per run</label>
          <input 
            type="number" 
            min={10}
            max={200}
            value={localConfig.settings.max_facts_per_run as number}
            onChange={(e) => handleChange('max_facts_per_run', parseInt(e.target.value))}
            style={{ width: 80 }}
          />
        </div>
      </section>

      {pendingFacts.length > 0 && (
        <section className="settings-section">
          <h3>Pending Facts ({pendingFacts.length})</h3>
          <div className="facts-list">
            {pendingFacts.slice(0, 10).map(fact => (
              <div key={fact.id} className="fact-item">
                <span className="fact-text">{fact.text}</span>
                <span className="fact-meta">{fact.source}</span>
              </div>
            ))}
            {pendingFacts.length > 10 && (
              <p className="muted">...and {pendingFacts.length - 10} more</p>
            )}
          </div>
        </section>
      )}

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
