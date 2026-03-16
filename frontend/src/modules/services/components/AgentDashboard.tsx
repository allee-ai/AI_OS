import { useState, useEffect } from 'react';
import { ModelDropdown } from '../../../components/ModelDropdown';
import { BASE_URL } from '../../../config/api';

interface ServiceConfig {
  enabled: boolean;
  settings: Record<string, unknown>;
}

interface AgentDashboardProps {
  config: ServiceConfig | null;
  status: string;
  message?: string;
  onChangesMade: () => void;
  onSave: (config: ServiceConfig) => Promise<void>;
}

export const AgentDashboard = ({ config, status, message, onChangesMade, onSave }: AgentDashboardProps) => {
  const [localConfig, setLocalConfig] = useState<ServiceConfig>({
    enabled: true,
    settings: {
      default_model: 'qwen2.5:7b',
      memory_enabled: true,
      kernel_enabled: false,
      default_context_level: 2,
      max_context_tokens: 4000,
      tool_calling_mode: 'text',
    }
  });
  const [saving, setSaving] = useState(false);
  const [agentStatus, setAgentStatus] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    if (config) {
      setLocalConfig({
        enabled: config.enabled,
        settings: { ...localConfig.settings, ...config.settings }
      });
    }
    
    // Fetch agent status
    fetch(`${BASE_URL}/api/chat/agent-status`)
      .then(res => res.ok ? res.json() : null)
      .then(data => setAgentStatus(data))
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
        <span className="service-icon">🤖</span>
        <div>
          <h1>Agent Service</h1>
          <p className="settings-description">Core agent connecting chat to HEA system</p>
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
          {agentStatus && (
            <div className="stats-row">
              <span className="stat">
                Agent: <strong>{agentStatus.name as string || 'Unknown'}</strong>
              </span>
              <span className="stat">
                Model: <strong>{agentStatus.model as string || 'Not set'}</strong>
              </span>
            </div>
          )}
        </div>
      </section>

      <section className="settings-section">
        <h3>Model Settings</h3>

        <div className="setting-row">
          <label>Default Model</label>
          <ModelDropdown
            value={localConfig.settings.default_model as string}
            onChange={(v) => handleChange('default_model', v)}
          />
        </div>
        <p className="setting-hint">
          The model used for generating responses. Can also be set via AIOS_MODEL_NAME env var.
        </p>

        <div className="setting-row">
          <label>Max context tokens</label>
          <input 
            type="number" 
            min={1000}
            max={32000}
            step={1000}
            value={localConfig.settings.max_context_tokens as number}
            onChange={(e) => handleChange('max_context_tokens', parseInt(e.target.value))}
            style={{ width: 100 }}
          />
        </div>
      </section>

      <section className="settings-section">
        <h3>Context Levels (HEA)</h3>
        <p className="setting-hint">
          The Hierarchical Experiential Attention system controls how much context 
          Agent loads based on message complexity.
        </p>

        <div className="setting-row">
          <label>Default context level</label>
          <select 
            value={localConfig.settings.default_context_level as number}
            onChange={(e) => handleChange('default_context_level', parseInt(e.target.value))}
          >
            <option value={1}>L1 - Minimal (~10 tokens) - Greetings, quick exchanges</option>
            <option value={2}>L2 - Standard (~50 tokens) - Normal conversation</option>
            <option value={3}>L3 - Full (~200 tokens) - Complex analysis</option>
          </select>
        </div>

        <div className="level-explainer">
          <div className="level-card">
            <strong>L1 - Realtime</strong>
            <span>Quick reflexes: greetings, acknowledgments</span>
          </div>
          <div className="level-card">
            <strong>L2 - Conversational</strong>
            <span>Normal chat with identity & recent context</span>
          </div>
          <div className="level-card">
            <strong>L3 - Analytical</strong>
            <span>Deep analysis with full memory access</span>
          </div>
        </div>
      </section>

      <section className="settings-section">
        <h3>Tool Calling Mode</h3>
        <p className="setting-hint">
          How the agent invokes tools during a response.
        </p>

        <div className="tool-mode-options">
          <label className={`tool-mode-option ${localConfig.settings.tool_calling_mode === 'text' ? 'selected' : ''}`}>
            <input
              type="radio"
              name="tool_calling_mode"
              value="text"
              checked={localConfig.settings.tool_calling_mode === 'text'}
              onChange={() => handleChange('tool_calling_mode', 'text')}
            />
            <div className="tool-mode-body">
              <strong>Text — <code>:::execute:::</code> blocks</strong>
              <span>Works with any model. Reasoning is visible in the chat. Gracefully degrades if the model writes prose instead of a block.</span>
            </div>
          </label>

          <label className={`tool-mode-option ${localConfig.settings.tool_calling_mode === 'schema' ? 'selected' : ''}`}>
            <input
              type="radio"
              name="tool_calling_mode"
              value="schema"
              checked={localConfig.settings.tool_calling_mode === 'schema'}
              onChange={() => handleChange('tool_calling_mode', 'schema')}
            />
            <div className="tool-mode-body">
              <strong>Schema — Ollama JSON protocol</strong>
              <span>Rigid, deterministic output. Requires a tool-calling compatible model.</span>
            </div>
          </label>
        </div>

        {localConfig.settings.tool_calling_mode === 'schema' && (() => {
          const model = (localConfig.settings.default_model as string) || '';
          const compatible = [
            'llama3.1', 'llama3.2', 'llama3.3',
            'qwen2.5', 'qwen2.5-coder',
            'mistral-nemo', 'command-r',
            'firefunction',
          ];
          const isCompatible = compatible.some(m => model.startsWith(m));
          return !isCompatible ? (
            <div className="tool-mode-warning">
              ⚠️ <strong>{model || 'Selected model'}</strong> may not support Ollama JSON tool calling.
              Compatible models include: llama3.1+, qwen2.5, mistral-nemo.
            </div>
          ) : null;
        })()}
      </section>

      <section className="settings-section">
        <h3>Feature Toggles</h3>

        <div className="setting-row">
          <label>Memory learning enabled</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.memory_enabled as boolean}
            onChange={(e) => handleChange('memory_enabled', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          When enabled, Agent extracts and remembers facts from conversations.
        </p>

        <div className="setting-row">
          <label>Browser automation enabled</label>
          <input 
            type="checkbox" 
            checked={localConfig.settings.kernel_enabled as boolean}
            onChange={(e) => handleChange('kernel_enabled', e.target.checked)}
          />
        </div>
        <p className="setting-hint">
          When enabled, The agent can control a browser for web tasks. Requires Kernel API key.
        </p>
      </section>

      <div className="settings-actions">
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  );
};
