import { useEffect, useState, useRef, useCallback } from 'react';
import { BASE_URL } from '../../../config/api';
import './ConnectPanel.css';

const API = BASE_URL;

/**
 * ConnectPanel — one-stop "connect this feed" UI.
 *
 * Every feed in Feeds/sources/ is reachable through two pieces of
 * backend plumbing that already exist:
 *
 *   1. GET  /api/feeds/{feed}/secret-schema
 *        → returns the paste-based form fields + which are filled
 *   2. POST /api/feeds/{feed}/secrets/bulk
 *        → stores them (Fernet-encrypted via agent.core.secrets)
 *
 * On top of that, two feeds have nicer flows that we prefer when
 * available:
 *
 *   github : Device Flow  (POST /api/feeds/github/device/start + poll)
 *   email  : OAuth redirect for gmail / outlook / proton
 *            (GET /api/feeds/email/oauth/start?provider=…)
 *
 * Everything else falls back to "paste these fields and save".
 *
 * Intended to be dropped at the top of each feed viewer so the user
 * has a single, consistent place to connect that feed.
 */

interface Field {
  key: string;
  label: string;
  type: 'text' | 'password' | 'number' | 'select' | 'textarea';
  required?: boolean;
  hint?: string;
  default?: string;
  options?: string[];
  has_value?: boolean;
}

interface Schema {
  feed: string;
  fields: Field[];
  configured: boolean;
  missing_required: string[];
}

interface Props {
  feed: string;
  /** Title shown above the panel. Defaults to the feed name. */
  title?: string;
  /** Called when connection state changes (connect/disconnect/save). */
  onChanged?: () => void;
}

const EMAIL_PROVIDERS = [
  { id: 'gmail', label: 'Gmail', icon: '📧' },
  { id: 'outlook', label: 'Outlook', icon: '📬' },
  { id: 'proton', label: 'Proton Mail', icon: '🔒' },
];

export default function ConnectPanel({ feed, title, onChanged }: Props) {
  const [schema, setSchema] = useState<Schema | null>(null);
  const [loading, setLoading] = useState(true);
  const [values, setValues] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<{ kind: 'ok' | 'err' | 'info'; text: string } | null>(null);

  // GitHub device flow
  const [device, setDevice] = useState<null | {
    userCode: string;
    verificationUri: string;
    deviceCode: string;
    expiresAt: number;
  }>(null);
  const [deviceMsg, setDeviceMsg] = useState('');
  const poll = useRef<number | null>(null);

  const fetchSchema = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/feeds/${feed}/secret-schema`);
      if (!res.ok) {
        setSchema(null);
        return;
      }
      const data: Schema = await res.json();
      setSchema(data);
      // Prefill defaults for unfilled fields
      const init: Record<string, string> = {};
      for (const f of data.fields) {
        if (!f.has_value && f.default) init[f.key] = f.default;
      }
      setValues(init);
    } catch {
      setSchema(null);
    } finally {
      setLoading(false);
    }
  }, [feed]);

  useEffect(() => {
    fetchSchema();
    return () => {
      if (poll.current) window.clearInterval(poll.current);
    };
  }, [fetchSchema]);

  // ── GitHub device flow ──────────────────────────────
  const startGithubDevice = async () => {
    setDeviceMsg('Starting…');
    try {
      const res = await fetch(`${API}/api/feeds/github/device/start`, { method: 'POST' });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setDeviceMsg(`Error: ${e.detail || res.statusText}`);
        return;
      }
      const d = await res.json();
      setDevice({
        userCode: d.user_code,
        verificationUri: d.verification_uri,
        deviceCode: d.device_code,
        expiresAt: Date.now() + d.expires_in * 1000,
      });
      setDeviceMsg('Enter the code at GitHub');
      const ms = Math.max(2000, (d.interval || 5) * 1000);
      poll.current = window.setInterval(() => pollGithubDevice(d.device_code), ms);
    } catch (e: any) {
      setDeviceMsg(`Failed: ${e.message || e}`);
    }
  };
  const pollGithubDevice = async (code: string) => {
    try {
      const res = await fetch(`${API}/api/feeds/github/device/poll?device_code=${code}`, {
        method: 'POST',
      });
      const d = await res.json();
      if (d.status === 'success') {
        if (poll.current) window.clearInterval(poll.current);
        setDevice(null);
        setDeviceMsg('Connected.');
        fetchSchema();
        onChanged?.();
      } else if (d.status === 'pending') {
        setDeviceMsg('Waiting for GitHub…');
      } else if (d.status === 'slow_down') {
        setDeviceMsg('Slowing down…');
      } else if (res.status >= 400) {
        if (poll.current) window.clearInterval(poll.current);
        setDevice(null);
        setDeviceMsg(d.detail || 'Authorization failed');
      }
    } catch (e: any) {
      setDeviceMsg(`Poll error: ${e.message || e}`);
    }
  };
  const cancelDevice = () => {
    if (poll.current) window.clearInterval(poll.current);
    setDevice(null);
    setDeviceMsg('');
  };

  // ── Email OAuth redirect ────────────────────────────
  const startEmailOauth = (provider: string) => {
    window.location.href = `${API}/api/feeds/email/oauth/start?provider=${provider}`;
  };

  // ── Save paste-form ─────────────────────────────────
  const save = async () => {
    if (!schema) return;
    setSaving(true);
    setMsg(null);
    try {
      // Only send keys the user actually set (empty strings clear them)
      const payload: Record<string, string> = {};
      for (const f of schema.fields) {
        const v = values[f.key];
        if (v !== undefined && v !== null) payload[f.key] = v;
      }
      const res = await fetch(`${API}/api/feeds/${feed}/secrets/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ values: payload }),
      });
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        setMsg({ kind: 'err', text: e.detail || res.statusText });
      } else {
        setMsg({ kind: 'ok', text: 'Saved. Testing connection…' });
        fetchSchema();
        onChanged?.();
        setValues({});
      }
    } catch (e: any) {
      setMsg({ kind: 'err', text: e.message || String(e) });
    } finally {
      setSaving(false);
    }
  };

  // ── Disconnect ──────────────────────────────────────
  const disconnect = async () => {
    if (!confirm(`Disconnect ${feed}? This clears all stored secrets for this feed.`)) return;
    try {
      const res = await fetch(`${API}/api/feeds/secrets/${feed}`, { method: 'DELETE' });
      if (res.ok) {
        setMsg({ kind: 'info', text: 'Disconnected.' });
        fetchSchema();
        onChanged?.();
      } else {
        setMsg({ kind: 'err', text: 'Disconnect failed' });
      }
    } catch (e: any) {
      setMsg({ kind: 'err', text: e.message || String(e) });
    }
  };

  if (loading) return <div className="connect-panel loading">Loading connection options…</div>;

  if (!schema) {
    return (
      <div className="connect-panel">
        <div className="connect-head">
          <h3>{title || `Connect ${feed}`}</h3>
          <span className="connect-status unknown">no schema</span>
        </div>
        <p className="connect-hint">
          This feed does not expose a credential schema. Connect via
          config file or environment variables.
        </p>
      </div>
    );
  }

  const configured = schema.configured;
  const isGithub = feed === 'github';
  const isEmail = feed === 'email';

  return (
    <div className={`connect-panel ${configured ? 'ok' : 'need'}`}>
      <div className="connect-head" onClick={() => setExpanded((e) => !e)}>
        <div className="connect-head-left">
          <h3>{title || `Connect ${feed}`}</h3>
          <span className={`connect-status ${configured ? 'ok' : 'need'}`}>
            {configured ? '✓ connected' : `needs ${schema.missing_required.length} field(s)`}
          </span>
        </div>
        <span className="connect-toggle">{expanded ? '▾' : '▸'}</span>
      </div>

      {expanded && (
        <div className="connect-body">
          {/* Quick-connect buttons for feeds with nicer flows */}
          {isGithub && !device && (
            <div className="quick-connect">
              <button className="btn primary" onClick={startGithubDevice} disabled={configured}>
                {configured ? 'Already connected' : 'Login with GitHub'}
              </button>
              <span className="or">or paste a Personal Access Token below</span>
            </div>
          )}
          {isGithub && device && (
            <div className="device-flow">
              <div className="device-code">
                <span className="device-code-label">Your code</span>
                <span className="device-code-value">{device.userCode}</span>
              </div>
              <a className="btn primary" href={device.verificationUri} target="_blank" rel="noopener">
                Open GitHub →
              </a>
              <button className="btn ghost" onClick={cancelDevice}>Cancel</button>
              <div className="device-msg">{deviceMsg}</div>
            </div>
          )}
          {isEmail && (
            <div className="quick-connect">
              {EMAIL_PROVIDERS.map((p) => (
                <button key={p.id} className="btn primary" onClick={() => startEmailOauth(p.id)}>
                  {p.icon} Login with {p.label}
                </button>
              ))}
              <span className="or">or configure IMAP manually below</span>
            </div>
          )}

          {/* Paste-form for every schema-backed feed */}
          <form
            className="connect-form"
            onSubmit={(e) => {
              e.preventDefault();
              save();
            }}
          >
            {schema.fields.map((f) => (
              <div key={f.key} className="field">
                <label>
                  {f.label}
                  {f.required && <span className="req">*</span>}
                  {f.has_value && <span className="has-value">(stored)</span>}
                </label>
                {f.type === 'select' ? (
                  <select
                    value={values[f.key] ?? ''}
                    onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                  >
                    <option value="">— choose —</option>
                    {(f.options || []).map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                ) : f.type === 'textarea' ? (
                  <textarea
                    rows={4}
                    value={values[f.key] ?? ''}
                    placeholder={f.has_value ? '(stored — leave blank to keep)' : f.default || ''}
                    onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                  />
                ) : (
                  <input
                    type={f.type === 'password' ? 'password' : f.type === 'number' ? 'number' : 'text'}
                    value={values[f.key] ?? ''}
                    placeholder={f.has_value ? '••••••••' : f.default || ''}
                    onChange={(e) => setValues({ ...values, [f.key]: e.target.value })}
                  />
                )}
                {f.hint && <small className="hint">{f.hint}</small>}
              </div>
            ))}

            <div className="actions">
              <button type="submit" className="btn primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save'}
              </button>
              {configured && (
                <button type="button" className="btn danger" onClick={disconnect}>
                  Disconnect
                </button>
              )}
              {msg && <span className={`msg ${msg.kind}`}>{msg.text}</span>}
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
