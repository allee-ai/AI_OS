import { useState, useEffect } from 'react';
import { ModelDropdown } from '../../../components/ModelDropdown';
import { BASE_URL } from '../../../config/api';

interface ServiceConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
}

interface MemoryDashboardProps {
  config: ServiceConfig | null;
  status: string;
  message?: string;
  onChangesMade: () => void;
  onSave: (config: ServiceConfig) => Promise<void>;
}

export const MemoryDashboard = ({ config, status, message, onChangesMade, onSave }: MemoryDashboardProps) => {
  const [localConfig, setLocalConfig] = useState<ServiceConfig>({
    enabled: true,
    settings: {
      extraction_model: 'qwen2.5:7b',
      auto_extract: true,
      min_message_length: 10,
      ignored_patterns: ['hi', 'hello', 'thanks', 'bye', 'ok'],
    }
  });
  const [saving, setSaving] = useState(false);
  const [stats, setStats] = useState<{ pending: number; total: number } | null>(null);

  useEffect(() => {
    if (config) {
      setLocalConfig({
        enabled: config.enabled,
        settings: { ...localConfig.settings, ...config.settings }
      });
    }
    
    // Fetch memory stats
    fetch(`${BASE_URL}/api/services/memory/stats`)
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setStats(data))
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
        <span className="service-icon">🧠</span>
        <div>
          <h1>Memory Service</h1>
          <p className="settings-description">Extracts and manages facts from conversations</p>
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
          {stats && (
            <div className="stats-row">
              <span className="stat">
                <strong>{stats.pending}</strong> pending facts
              </span>
              <span className="stat">
                <strong>{stats.total}</strong> total extracted
              </span>
            </div>
          )}
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
          <label>Auto-extract from conversations</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.auto_extract as boolean}
            onChange={(e) => handleChange('auto_extract', e.target.checked)}
          />
        </div>

        <div className="setting-row">
          <label>Extraction Model</label>
          <ModelDropdown
            value={localConfig.settings.extraction_model as string}
            onChange={(v) => handleChange('extraction_model', v)}
          />
        </div>

        <div className="setting-row">
          <label>Min message length</label>
          <input 
            type="number" 
            min={0}
            max={100}
            value={localConfig.settings.min_message_length as number}
            onChange={(e) => handleChange('min_message_length', parseInt(e.target.value))}
            style={{ width: 80 }}
          />
        </div>
      </section>

      <section className="settings-section">
        <h3>Ignored Patterns</h3>
        <p className="setting-hint">
          Messages matching these patterns won't trigger fact extraction.
          One pattern per line (case-insensitive).
        </p>
        <textarea 
          className="patterns-input"
          value={(localConfig.settings.ignored_patterns as string[]).join('\n')}
          onChange={(e) => handleChange('ignored_patterns', e.target.value.split('\n').filter(p => p.trim()))}
          rows={5}
          placeholder="hi&#10;hello&#10;thanks"
        />
      </section>

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
