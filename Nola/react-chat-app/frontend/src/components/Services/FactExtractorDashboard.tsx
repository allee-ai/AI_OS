import { useState, useEffect } from 'react';

interface ServiceConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
}

interface FactExtractorDashboardProps {
  config: ServiceConfig | null;
  status: string;
  message?: string;
  onChangesMade: () => void;
  onSave: (config: ServiceConfig) => Promise<void>;
}

export const FactExtractorDashboard = ({ config, status, message, onChangesMade, onSave }: FactExtractorDashboardProps) => {
  const [localConfig, setLocalConfig] = useState<ServiceConfig>({
    enabled: true,
    settings: {
      model: 'llama3.2:3b',
      default_detail_level: 2,
      auto_route_threads: true,
      store_all_levels: true,
    }
  });
  const [saving, setSaving] = useState(false);
  const [testFact, setTestFact] = useState('');
  const [testResult, setTestResult] = useState<Record<string, unknown> | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (config) {
      setLocalConfig({
        enabled: config.enabled,
        settings: { ...localConfig.settings, ...config.settings }
      });
    }
  }, [config]);

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

  const handleTest = async () => {
    if (!testFact.trim()) return;
    
    setTesting(true);
    setTestResult(null);
    try {
      const res = await fetch('http://localhost:8000/api/services/fact-extractor/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fact: testFact })
      });
      const data = await res.json();
      setTestResult(data);
    } catch (err) {
      setTestResult({ error: 'Failed to test extraction' });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">🔍</span>
        <div>
          <h1>Fact Extractor</h1>
          <p className="settings-description">LLM-based fact extraction with detail levels (L1/L2/L3)</p>
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
        </div>
      </section>

      <section className="settings-section">
        <h3>Extraction Settings</h3>

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
          <label>Extraction Model</label>
          <select 
            value={localConfig.settings.model as string}
            onChange={(e) => handleChange('model', e.target.value)}
          >
            <option value="llama3.2:3b">llama3.2:3b (fast, recommended)</option>
            <option value="qwen2.5:7b">qwen2.5:7b (balanced)</option>
            <option value="llama3.2:latest">llama3.2 (quality)</option>
          </select>
        </div>

        <div className="setting-row">
          <label>Default detail level</label>
          <select 
            value={localConfig.settings.default_detail_level as number}
            onChange={(e) => handleChange('default_detail_level', parseInt(e.target.value))}
          >
            <option value={1}>L1 - Minimal (keywords)</option>
            <option value={2}>L2 - Standard (summary)</option>
            <option value={3}>L3 - Full (detailed)</option>
          </select>
        </div>

        <div className="setting-row">
          <label>Auto-route to threads</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.auto_route_threads as boolean}
            onChange={(e) => handleChange('auto_route_threads', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          When enabled, facts are automatically classified and routed to either 
          the Identity thread (facts about people/preferences) or Philosophy thread (beliefs/values).
        </p>

        <div className="setting-row">
          <label>Store all detail levels</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.store_all_levels as boolean}
            onChange={(e) => handleChange('store_all_levels', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          Store L1, L2, and L3 versions of each fact. If disabled, only the default level is stored.
        </p>
      </section>

      <section className="settings-section">
        <h3>Test Extraction</h3>
        <p className="setting-hint">
          Test how a fact would be extracted and structured.
        </p>
        <div className="test-input-row">
          <input 
            type="text"
            className="test-input"
            placeholder="e.g., Sarah mentioned she loves coffee"
            value={testFact}
            onChange={(e) => setTestFact(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleTest()}
          />
          <button 
            className="btn-secondary"
            onClick={handleTest}
            disabled={testing || !testFact.trim()}
          >
            {testing ? 'Testing...' : 'Test'}
          </button>
        </div>
        
        {testResult && (
          <div className="test-result">
            {testResult.error ? (
              <p className="error">{testResult.error as string}</p>
            ) : (
              <>
                <div className="result-row">
                  <span className="result-label">Key:</span>
                  <code>{testResult.key as string}</code>
                </div>
                <div className="result-row">
                  <span className="result-label">Thread:</span>
                  <code>{testResult.thread as string}</code>
                </div>
                <div className="result-row">
                  <span className="result-label">L1:</span>
                  <span>{testResult.l1 as string}</span>
                </div>
                <div className="result-row">
                  <span className="result-label">L2:</span>
                  <span>{testResult.l2 as string}</span>
                </div>
                <div className="result-row">
                  <span className="result-label">L3:</span>
                  <span>{testResult.l3 as string}</span>
                </div>
              </>
            )}
          </div>
        )}
      </section>

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
