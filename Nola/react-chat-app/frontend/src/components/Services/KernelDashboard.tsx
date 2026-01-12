import { useState, useEffect } from 'react';

interface ServiceConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
}

interface KernelDashboardProps {
  config: ServiceConfig | null;
  status: string;
  message?: string;
  onChangesMade: () => void;
  onSave: (config: ServiceConfig) => Promise<void>;
}

export const KernelDashboard = ({ config, status, message, onChangesMade, onSave }: KernelDashboardProps) => {
  const [localConfig, setLocalConfig] = useState<ServiceConfig>({
    enabled: false,
    settings: {
      profile_name: 'nola_identity',
      default_timeout: 3600,
      headless: false,
      stealth: true,
      human_delay_min: 50,
      human_delay_max: 150,
    }
  });
  const [saving, setSaving] = useState(false);
  const [apiKeySet, setApiKeySet] = useState(false);

  useEffect(() => {
    if (config) {
      setLocalConfig({
        enabled: config.enabled,
        settings: { ...localConfig.settings, ...config.settings }
      });
    }
    
    // Check if API key is configured
    fetch('http://localhost:8000/api/services/kernel/status')
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setApiKeySet(data.api_key_set))
      .catch(() => {});
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

  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">🌐</span>
        <div>
          <h1>Kernel Service</h1>
          <p className="settings-description">Browser automation through Kernel API</p>
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
            <span className={`stat ${apiKeySet ? 'success' : 'warning'}`}>
              API Key: {apiKeySet ? '✓ Configured' : '✗ Not set'}
            </span>
          </div>
        </div>
      </section>

      {!apiKeySet && (
        <section className="settings-section">
          <div className="warning-box">
            <h4>⚠️ API Key Required</h4>
            <p>
              Kernel browser automation requires an API key. 
              Set the <code>KERNEL_API_KEY</code> environment variable to enable this service.
            </p>
            <a 
              href="https://www.kernel.dev/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="external-link"
            >
              Get a Kernel API key →
            </a>
          </div>
        </section>
      )}

      <section className="settings-section">
        <h3>Browser Settings</h3>

        <div className="setting-row">
          <label>Enabled</label>
          <input 
            type="checkbox" 
            checked={localConfig.enabled}
            onChange={(e) => {
              setLocalConfig(prev => ({ ...prev, enabled: e.target.checked }));
              onChangesMade();
            }}
            disabled={!apiKeySet}
          />
        </div>

        <div className="setting-row">
          <label>Profile name</label>
          <input 
            type="text"
            value={localConfig.settings.profile_name as string}
            onChange={(e) => handleChange('profile_name', e.target.value)}
            style={{ width: 200 }}
          />
        </div>

        <div className="setting-row">
          <label>Session timeout (seconds)</label>
          <input 
            type="number" 
            min={300}
            max={86400}
            value={localConfig.settings.default_timeout as number}
            onChange={(e) => handleChange('default_timeout', parseInt(e.target.value))}
            style={{ width: 100 }}
          />
        </div>

        <div className="setting-row">
          <label>Headless mode</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.headless as boolean}
            onChange={(e) => handleChange('headless', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          Headless mode runs the browser without a GUI. Disable for demos or debugging.
        </p>

        <div className="setting-row">
          <label>Stealth mode</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.stealth as boolean}
            onChange={(e) => handleChange('stealth', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          Stealth mode helps avoid bot detection on websites.
        </p>
      </section>

      <section className="settings-section">
        <h3>Human-like Behavior</h3>
        <p className="setting-hint">
          Add random delays to typing and mouse movements to appear more human.
        </p>

        <div className="setting-row">
          <label>Min delay (ms)</label>
          <input 
            type="number" 
            min={0}
            max={500}
            value={localConfig.settings.human_delay_min as number}
            onChange={(e) => handleChange('human_delay_min', parseInt(e.target.value))}
            style={{ width: 80 }}
          />
        </div>

        <div className="setting-row">
          <label>Max delay (ms)</label>
          <input 
            type="number" 
            min={0}
            max={1000}
            value={localConfig.settings.human_delay_max as number}
            onChange={(e) => handleChange('human_delay_max', parseInt(e.target.value))}
            style={{ width: 80 }}
          />
        </div>
      </section>

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
