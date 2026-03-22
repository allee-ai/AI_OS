import React, { useState, useEffect } from 'react';
import './SetupWizard.css';

interface Provider {
  id: string;
  name: string;
  description: string;
  requires_key: boolean;
  requires_endpoint: boolean;
  connected: boolean;
  setup_url: string | null;
}

interface ModelOption {
  id: string;
  name: string;
  provider: string;
  description?: string;
}

interface LibraryModel {
  id: string;
  name: string;
  parameters: string;
  size: string;
  description: string;
  installed: boolean;
}

interface SetupWizardProps {
  onComplete: () => void;
}

type Step = 'choose' | 'configure' | 'test' | 'feeds';

const OPENAI_MODELS: ModelOption[] = [
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai', description: 'Fast, affordable' },
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai', description: 'Flagship' },
  { id: 'gpt-4.1-mini', name: 'GPT-4.1 Mini', provider: 'openai', description: 'Latest mini' },
  { id: 'gpt-4.1', name: 'GPT-4.1', provider: 'openai', description: 'Latest flagship' },
  { id: 'gpt-4.1-nano', name: 'GPT-4.1 Nano', provider: 'openai', description: 'Fastest, cheapest' },
  { id: 'o3-mini', name: 'o3 Mini', provider: 'openai', description: 'Reasoning' },
];

const OLLAMA_FALLBACK_MODELS: ModelOption[] = [
  { id: 'qwen2.5:7b', name: 'Qwen 2.5 7B', provider: 'ollama', description: 'Recommended' },
  { id: 'llama3.2:3b', name: 'Llama 3.2 3B', provider: 'ollama', description: 'Fast, lightweight' },
  { id: 'mistral:7b', name: 'Mistral 7B', provider: 'ollama', description: 'General purpose' },
  { id: 'gemma2:9b', name: 'Gemma 2 9B', provider: 'ollama', description: 'Google' },
  { id: 'phi3:mini', name: 'Phi-3 Mini', provider: 'ollama', description: 'Microsoft, fast' },
];

export const SetupWizard: React.FC<SetupWizardProps> = ({ onComplete }) => {
  const [step, setStep] = useState<Step>('choose');
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [apiKey, setApiKey] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [model, setModel] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [ollamaModels, setOllamaModels] = useState<ModelOption[]>(OLLAMA_FALLBACK_MODELS);
  const [showLibrary, setShowLibrary] = useState(false);
  const [library, setLibrary] = useState<LibraryModel[]>([]);
  const [pulling, setPulling] = useState<string | null>(null);
  const [pullProgress, setPullProgress] = useState<{ status: string; percent: number }>({ status: '', percent: 0 });

  // Feeds onboarding state
  const [feedStatuses, setFeedStatuses] = useState<Record<string, boolean>>({});
  const [protonUser, setProtonUser] = useState('');
  const [protonPass, setProtonPass] = useState('');
  const [feedConnecting, setFeedConnecting] = useState<string | null>(null);

  const refreshOllamaModels = () => {
    fetch('/api/models')
      .then(res => res.json())
      .then(data => {
        const installed = (data.models || []).filter((m: ModelOption) => m.provider === 'ollama');
        if (installed.length > 0) setOllamaModels(installed);
      })
      .catch(() => {});
  };

  const refreshLibrary = () => {
    fetch('/api/models/library')
      .then(res => res.json())
      .then(data => setLibrary(data.models || []))
      .catch(() => {});
  };

  useEffect(() => {
    fetch('/api/models/providers')
      .then(res => res.json())
      .then(data => setProviders(data.providers || []))
      .catch(() => {});
    refreshOllamaModels();
    refreshLibrary();
  }, []);

  const refreshFeedStatuses = () => {
    fetch('/api/feeds/email/providers/status')
      .then(res => res.json())
      .then(data => {
        const statuses: Record<string, boolean> = {};
        for (const [k, v] of Object.entries(data)) {
          statuses[k] = (v as any).connected;
        }
        setFeedStatuses(statuses);
      })
      .catch(() => {});
  };

  const handleConnectGmail = () => {
    // Save current wizard state, redirect to OAuth
    window.location.href = '/api/feeds/email/oauth/start?provider=gmail';
  };

  const handleConnectProtonBridge = async () => {
    if (!protonUser || !protonPass) return;
    setFeedConnecting('proton');
    try {
      const res = await fetch('/api/feeds/email/proton/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ imap_user: protonUser, imap_password: protonPass }),
      });
      if (res.ok) {
        refreshFeedStatuses();
        setProtonUser('');
        setProtonPass('');
      }
    } catch (e) {
      console.error('Failed to connect Proton:', e);
    } finally {
      setFeedConnecting(null);
    }
  };

  const handlePull = async (modelId: string) => {
    setPulling(modelId);
    setPullProgress({ status: 'starting', percent: 0 });
    try {
      const res = await fetch('/api/models/pull', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model: modelId }),
      });
      if (!res.body) throw new Error('No response stream');
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.trim()) continue;
          try {
            const event = JSON.parse(line);
            if (event.status === 'error') {
              setPullProgress({ status: `Error: ${event.error}`, percent: 0 });
              setPulling(null);
              return;
            }
            if (event.status === 'success') {
              setPullProgress({ status: 'Download complete!', percent: 100 });
              // Refresh installed models and library
              refreshOllamaModels();
              refreshLibrary();
              setModel(modelId);
              setTimeout(() => { setPulling(null); setPullProgress({ status: '', percent: 0 }); }, 2000);
              return;
            }
            const pct = event.total > 0 ? Math.round((event.completed / event.total) * 100) : 0;
            setPullProgress({ status: event.status || 'downloading', percent: pct });
          } catch { /* skip malformed lines */ }
        }
      }
    } catch (e: any) {
      setPullProgress({ status: `Error: ${e.message}`, percent: 0 });
    } finally {
      // If we didn't already clear it in the success handler
      setTimeout(() => setPulling(null), 3000);
    }
  };

  const providerDefaults: Record<string, string> = {
    ollama: 'qwen2.5:7b',
    openai: 'gpt-4o-mini',
    http: '',
  };

  const selectProvider = (id: string) => {
    setSelectedProvider(id);
    setModel(providerDefaults[id] || '');
    setApiKey('');
    setEndpoint('');
    setTestResult(null);
    setError('');
    setStep('configure');
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError('');

    try {
      const res = await fetch('/api/models/setup/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          model: model || providerDefaults[selectedProvider],
          api_key: apiKey || undefined,
          endpoint: endpoint || undefined,
        }),
      });
      const data = await res.json();
      if (data.success) {
        setTestResult({ success: true, message: data.response || 'Connected successfully' });
        setStep('test');
      } else {
        setTestResult({ success: false, message: data.error || 'Connection failed' });
      }
    } catch (e: any) {
      setTestResult({ success: false, message: e.message || 'Network error' });
    } finally {
      setTesting(false);
    }
  };

  const selected = providers.find(p => p.id === selectedProvider);

  return (
    <div className="setup-wizard">
      <div className="setup-card">
        <div className="setup-header">
          <div className="setup-logo">🧠</div>
          <h1>Welcome to AI OS</h1>
          <p className="setup-subtitle">Choose how your agent connects to an AI model</p>
        </div>

        {step === 'choose' && (
          <div className="setup-providers">
            {providers.map(p => (
              <button
                key={p.id}
                className={`provider-card ${p.connected ? 'connected' : ''}`}
                onClick={() => selectProvider(p.id)}
              >
                <div className="provider-card-icon">
                  {p.id === 'ollama' ? '💻' : p.id === 'openai' ? '🔑' : '🌐'}
                </div>
                <div className="provider-card-info">
                  <span className="provider-card-name">{p.name}</span>
                  <span className="provider-card-desc">{p.description}</span>
                </div>
                {p.connected && <span className="provider-card-status">● Connected</span>}
                <span className="provider-card-arrow">→</span>
              </button>
            ))}
          </div>
        )}

        {step === 'configure' && selected && (
          <div className="setup-configure">
            <button className="setup-back" onClick={() => setStep('choose')}>← Back</button>

            <div className="config-provider-label">
              {selected.id === 'ollama' ? '💻' : selected.id === 'openai' ? '🔑' : '🌐'}
              {' '}{selected.name}
            </div>

            {selected.id === 'ollama' && (
              <div className="config-section">
                <p className="config-hint">
                  Make sure Ollama is running on your machine.{' '}
                  <a href="https://ollama.com" target="_blank" rel="noopener noreferrer">Download Ollama</a>
                </p>
                <label className="config-label">
                  Model
                  <select
                    className="config-select"
                    value={model}
                    onChange={e => setModel(e.target.value)}
                  >
                    {ollamaModels.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.name}{m.description ? ` — ${m.description}` : ''}
                      </option>
                    ))}
                  </select>
                </label>

                <button
                  className="library-toggle"
                  onClick={() => setShowLibrary(!showLibrary)}
                  type="button"
                >
                  {showLibrary ? '▾ Hide model library' : '▸ Browse & download models'}
                </button>

                {showLibrary && (
                  <div className="model-library">
                    <p className="library-warning">
                      ⚠️ Models are large files (1–10 GB). Downloads may take several minutes depending on your connection.
                    </p>
                    <div className="library-list">
                      {library.map(m => (
                        <div key={m.id} className={`library-item ${m.installed ? 'installed' : ''}`}>
                          <div className="library-item-info">
                            <span className="library-item-name">{m.name}</span>
                            <span className="library-item-meta">{m.parameters} · {m.size}</span>
                            <span className="library-item-desc">{m.description}</span>
                          </div>
                          <div className="library-item-action">
                            {m.installed ? (
                              <span className="library-badge-installed">Installed</span>
                            ) : pulling === m.id ? (
                              <div className="library-pull-progress">
                                <div className="pull-bar-track">
                                  <div className="pull-bar-fill" style={{ width: `${pullProgress.percent}%` }} />
                                </div>
                                <span className="pull-status">{pullProgress.percent}%</span>
                              </div>
                            ) : pulling ? (
                              <button className="btn-pull" disabled>Pull</button>
                            ) : (
                              <button className="btn-pull" onClick={() => handlePull(m.id)}>Pull</button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {selected.id === 'openai' && (
              <div className="config-section">
                <label className="config-label">
                  API Key
                  <input
                    type="password"
                    className="config-input"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="sk-..."
                  />
                </label>
                <label className="config-label">
                  Model
                  <select
                    className="config-select"
                    value={model}
                    onChange={e => setModel(e.target.value)}
                  >
                    {OPENAI_MODELS.map(m => (
                      <option key={m.id} value={m.id}>
                        {m.name}{m.description ? ` — ${m.description}` : ''}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="config-label">
                  Custom Base URL <span className="config-optional">(optional — for Together, Groq, etc.)</span>
                  <input
                    type="text"
                    className="config-input"
                    value={endpoint}
                    onChange={e => setEndpoint(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                  />
                </label>
              </div>
            )}

            {selected.id === 'http' && (
              <div className="config-section">
                <label className="config-label">
                  Endpoint URL
                  <input
                    type="text"
                    className="config-input"
                    value={endpoint}
                    onChange={e => setEndpoint(e.target.value)}
                    placeholder="http://localhost:1234/v1/chat/completions"
                  />
                </label>
                <label className="config-label">
                  Model name <span className="config-optional">(optional)</span>
                  <input
                    type="text"
                    className="config-input"
                    value={model}
                    onChange={e => setModel(e.target.value)}
                    placeholder="model-name"
                  />
                </label>
              </div>
            )}

            {testResult && (
              <div className={`config-result ${testResult.success ? 'success' : 'error'}`}>
                {testResult.success ? '✓' : '✗'} {testResult.message}
              </div>
            )}

            {error && <div className="config-result error">✗ {error}</div>}

            <div className="config-actions">
              <button
                className="btn-test"
                onClick={handleTest}
                disabled={testing}
              >
                {testing ? 'Testing…' : 'Test Connection'}
              </button>
            </div>
          </div>
        )}

        {step === 'test' && testResult?.success && (
          <div className="setup-success">
            <button className="setup-back" onClick={() => setStep('configure')}>← Back</button>
            <div className="success-icon">✓</div>
            <h2>Connection Successful</h2>
            <p className="success-detail">
              {selected?.name} is ready with model <strong>{model || providerDefaults[selectedProvider]}</strong>
            </p>
            <button
              className="btn-save"
              onClick={async () => {
                setSaving(true);
                setError('');
                try {
                  const res = await fetch('/api/models/setup/configure', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      provider: selectedProvider,
                      model: model || providerDefaults[selectedProvider],
                      api_key: apiKey || undefined,
                      endpoint: endpoint || undefined,
                    }),
                  });
                  const data = await res.json();
                  if (data.success) {
                    refreshFeedStatuses();
                    setStep('feeds');
                  } else {
                    setError(data.detail || 'Failed to save configuration');
                  }
                } catch (e: any) {
                  setError(e.message || 'Network error');
                } finally {
                  setSaving(false);
                }
              }}
              disabled={saving}
            >
              {saving ? 'Saving…' : 'Next: Connect Feeds →'}
            </button>
          </div>
        )}

        {step === 'feeds' && (
          <div className="setup-feeds">
            <h2>Connect Your Accounts</h2>
            <p className="setup-subtitle">Optional — connect email and other feeds so your agent can help you.</p>

            <div className="feed-cards">
              {/* Gmail */}
              <div className={`feed-card ${feedStatuses['gmail'] ? 'connected' : ''}`}>
                <div className="feed-card-header">
                  <span className="feed-card-icon">📧</span>
                  <span className="feed-card-name">Gmail</span>
                  {feedStatuses['gmail'] && <span className="feed-card-status">● Connected</span>}
                </div>
                {feedStatuses['gmail'] ? (
                  <p className="feed-card-desc">Your Gmail inbox is connected.</p>
                ) : (
                  <>
                    <p className="feed-card-desc">Read inbox, send emails, manage drafts via Google OAuth.</p>
                    <button className="connect-btn" onClick={handleConnectGmail}>Connect Gmail</button>
                  </>
                )}
              </div>

              {/* Proton */}
              <div className={`feed-card ${feedStatuses['proton'] ? 'connected' : ''}`}>
                <div className="feed-card-header">
                  <span className="feed-card-icon">🔒</span>
                  <span className="feed-card-name">Proton Mail</span>
                  {feedStatuses['proton'] && <span className="feed-card-status">● Connected</span>}
                </div>
                {feedStatuses['proton'] ? (
                  <p className="feed-card-desc">Proton Bridge is connected.</p>
                ) : (
                  <>
                    <p className="feed-card-desc">
                      Connects via <a href="https://proton.me/mail/bridge" target="_blank" rel="noopener noreferrer">Proton Bridge</a> on your machine.
                    </p>
                    <input type="text" className="config-input" placeholder="Proton email" value={protonUser} onChange={e => setProtonUser(e.target.value)} />
                    <input type="password" className="config-input" placeholder="Bridge password" value={protonPass} onChange={e => setProtonPass(e.target.value)} />
                    <p className="config-hint">Open Proton Bridge → click your account → copy the password shown.</p>
                    <button className="connect-btn" onClick={handleConnectProtonBridge} disabled={feedConnecting === 'proton' || !protonUser || !protonPass}>
                      {feedConnecting === 'proton' ? 'Connecting…' : 'Connect Proton Bridge'}
                    </button>
                  </>
                )}
              </div>

              {/* Outlook */}
              <div className={`feed-card ${feedStatuses['outlook'] ? 'connected' : ''}`}>
                <div className="feed-card-header">
                  <span className="feed-card-icon">📬</span>
                  <span className="feed-card-name">Outlook</span>
                  {feedStatuses['outlook'] && <span className="feed-card-status">● Connected</span>}
                </div>
                {feedStatuses['outlook'] ? (
                  <p className="feed-card-desc">Your Outlook inbox is connected.</p>
                ) : (
                  <>
                    <p className="feed-card-desc">Read inbox, send emails via Microsoft OAuth.</p>
                    <button className="connect-btn" onClick={() => { window.location.href = '/api/feeds/email/oauth/start?provider=outlook'; }}>Connect Outlook</button>
                  </>
                )}
              </div>
            </div>

            <div className="config-actions" style={{ marginTop: '1.5rem' }}>
              <button className="btn-save" onClick={onComplete}>
                {Object.values(feedStatuses).some(Boolean) ? 'Done — Launch AI OS' : 'Skip — Launch AI OS'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
