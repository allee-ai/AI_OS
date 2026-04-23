import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'

/* ── Types ── */
interface SensoryEvent {
  id: number
  source: string
  kind: string
  text: string
  confidence: number
  meta_json?: string
  created_at: string
}

interface DroppedEvent {
  id: number
  source: string
  kind: string
  text: string
  score: number
  reason: string
  created_at: string
}

interface SalienceConfig {
  threshold: number
  min_text_chars: number
  source_weight: Record<string, number>
  kind_boost: Record<string, number>
  confidence_weight: number
  novelty_bonus_if_new_text: number
  dedup_recent_seconds: number
  always_keep_contains: string[]
  always_drop_contains: string[]
}

interface ConsentRow {
  source: string
  kind: string
  enabled: number
  enabled_at?: string
  enabled_by?: string
  notes?: string
  updated_at: string
}

interface ConsentLogRow {
  id: number
  source: string
  kind: string
  action: string
  actor?: string
  notes?: string
  created_at: string
}

interface BlockedRow {
  id: number
  source: string
  kind: string
  text: string
  confidence: number
  reason: string
  created_at: string
}

type Tab = 'events' | 'dropped' | 'consent' | 'config'

/* ── API ── */
async function fetchEvents(source?: string): Promise<SensoryEvent[]> {
  const p = new URLSearchParams({ limit: '100' })
  if (source) p.set('source', source)
  const r = await fetch(`/api/sensory/events?${p}`)
  const d = await r.json()
  return d.events || []
}

async function fetchStats(): Promise<Record<string, number>> {
  const r = await fetch('/api/sensory/stats')
  const d = await r.json()
  return d.counts_by_source || {}
}

async function fetchConsent(): Promise<{ consent: ConsentRow[]; enabled: number; count: number }> {
  const r = await fetch('/api/sensory/consent')
  return await r.json()
}

async function setConsent(source: string, kind: string, enabled: boolean, notes = ''): Promise<void> {
  await fetch('/api/sensory/consent', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, kind, enabled, notes }),
  })
}

async function fetchConsentLog(): Promise<ConsentLogRow[]> {
  const r = await fetch('/api/sensory/consent/log?limit=50')
  const d = await r.json()
  return d.log || []
}

async function fetchBlocked(): Promise<BlockedRow[]> {
  const r = await fetch('/api/sensory/blocked?limit=50')
  const d = await r.json()
  return d.blocked || []
}

async function fetchDropped(source?: string): Promise<DroppedEvent[]> {
  const p = new URLSearchParams({ limit: '100' })
  if (source) p.set('source', source)
  const r = await fetch(`/api/sensory/dropped?${p}`)
  const d = await r.json()
  return d.dropped || []
}

async function fetchConfig(): Promise<SalienceConfig> {
  const r = await fetch('/api/sensory/salience/config')
  return await r.json()
}

async function saveConfig(cfg: SalienceConfig): Promise<void> {
  await fetch('/api/sensory/salience/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  })
}

async function scoreTest(source: string, kind: string, text: string, confidence: number): Promise<{ score: number; threshold: number; would_promote: boolean; reason: string }> {
  const r = await fetch('/api/sensory/score', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, kind, text, confidence }),
  })
  return await r.json()
}

/* ── Helpers ── */
function consent, setConsentRows] = useState<ConsentRow[]>([])
  const [consentLog, setConsentLog] = useState<ConsentLogRow[]>([])
  const [blocked, setBlocked] = useState<BlockedRow[]>([])
  const [timeAgo(iso: string): string {
  const then = new Date(iso).getTime()
  const diff = (Date.now() - then) / 1000
  if (diff < 60) return `${Math.floor(diff)}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

const SOURCE_COLORS: Record<string, string> = {
  mic: '#4ade80',
  camera: '#60a5fa',
  screen: '#a78bfa',
  clipboard: '#fbbf24',
  system: '#94a3b8',
  ambient: '#2dd4bf',
}
sent') {
        const [c, log, bl] = await Promise.all([fetchConsent(), fetchConsentLog(), fetchBlocked()])
        setConsentRows(c.consent)
        setConsentLog(log)
        setBlocked(bl)
      } else if (tab === 'con
/* ── Page ── */
export function SensoryPage() {
  const [tab, setTab] = useState<Tab>('events')
  const [events, setEvents] = useState<SensoryEvent[]>([])
  const [dropped, setDropped] = useState<DroppedEvent[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [config, setConfig] = useState<SalienceConfig | null>(null)
  const [sourceFilter, setSourceFilter] = useState<string>('')
  const [loading, setLoading] = useState(false)

  // Score tester state
  const [testSource, setTestSource] = useState('mic')
  const [testKind, setTestKind] = useState('push_to_talk')
  const [testText, setTestText] = useState('')
  const [testConf, setTestConf] = useState(0.9)
  const [testResult, setTestResult] = useState<{ score: number; threshold: number; would_promote: boolean; reason: string } | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    try {
      if (tab === 'events') {
        const [ev, st] = await Promise.all([fetchEvents(sourceFilter || undefined), fetchStats()])
        setEvents(ev)
        setStats(st)
      } else if (tab === 'dropped') {
        const dr = await fetchDropped(sourceFilter || undefined)
        setDropped(dr)
      } else if (tab === 'config') {
        const cfg = await fetchConfig()
        setConfig(cfg)
      }
    } finally {
      setLoading(false)
    }
  }, [tab, sourceFilter])

  useEffect(() => {
    refresh()
    if (tab === 'events' || tab === 'dropped') {
      const t = setInterval(refresh, 5000)
      return () => clearInterval(t)
    }
  }, [tab, sourceFilter, refresh])

  const runScoreTest = async () => {
    if (!testText.trim()) return
    const r = await scoreTest(testSource, testKind, testText, testConf)
    setTestResult(r)
  }

  const saveConfigEdit = async () => {
    if (!config) return
    await saveConfig(config)
    await refresh()
    alert('Saved. Takes effect on next event.')
  }

  return (
    <div style={{ padding: 20, fontFamily: 'ui-sans-serif, system-ui', color: '#e5e7eb', background: '#0b0f1a', minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 16 }}>
        <h1 style={{ margin: 0, fontSize: 24 }}>Sensory Bus</h1>
        <Link to="/" style={{ color: '#60a5fa', textDecoration: 'none', fontSize: 13 }}>← home</Link>
        <span style={{ color: '#64748b', fontSize: 13 }}>text-based feed for mic, vision, screen, clipboard, system</span>
      </div>

      {/* Stats bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {Object.entries(stats).map(([src, n]) => (
          <button
            key={src}
            onClick={() => setSourceFilter(sourceFilter === src ? '' : src)}
            style={{
              background: sourceFilter === src ? (SOURCE_COLORS[src] || '#374151') : '#1f2937',
              color: sourceFilter === src ? '#000' : '#e5e7eb',
              border: `1px solid ${SOURCE_COLORS[src] || '#374151'}`,
              borderRadius: 6,
              padding: '6px 12px',
              cursor: 'pointer',
              fontSize: 13,
              fontWeight: 600,
            }}
          >
            {src}: {n}
          </button>
        ))}sent', 'config'] as Tab[]).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              background: tab === t ? '#1f2937' : 'transparent',
              color: tab === t ? '#fff' : '#94a3b8',
              border: 'none',
              borderBottom: tab === t ? '2px solid #60a5fa' : '2px solid transparent',
              padding: '8px 16px',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            {t === 'events' ? 'Events' : t === 'dropped' ? 'Dropped (salience)' : t === 'consent' ? 'Consent 🔒
              border: 'none',
              borderBottom: tab === t ? '2px solid #60a5fa' : '2px solid transparent',
              padding: '8px 16px',
              cursor: 'pointer',
              fontSize: 14,
            }}
          >
            {t === 'events' ? 'Events' : t === 'dropped' ? 'Dropped (audit)' : 'Salience Config'}
          </button>
        ))}
      </div>

      {loading && <div style={{ color: '#64748b', fontSize: 12, marginBottom: 8 }}>refreshing…</div>}

      {/* Events table */}
      {tab === 'events' && (
        <div>
          {events.length === 0 ? (
            <div style={{ color: '#64748b', padding: 24, textAlign: 'center' }}>No events yet. POST to /api/sensory/record to add some.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#111827', textAlign: 'left' }}>
                  <th style={{ padding: 8 }}>when</th>
                  <th style={{ padding: 8 }}>source</th>
                  <th style={{ padding: 8 }}>kind</th>
                  <th style={{ padding: 8 }}>conf</th>
                  <th style={{ padding: 8 }}>text</th>
                </tr>
              </thead>
              <tbody>
                {events.map(e => (
                  <tr key={e.id} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: 8, color: '#64748b', whiteSpace: 'nowrap' }}>{timeAgo(e.created_at)}</td>
                    <td style={{ padding: 8 }}>
                      <span style={{ color: SOURCE_COLORS[e.source] || '#fff', fontWeight: 600 }}>{e.source}</span>
                    </td>
                    <td style={{ padding: 8, color: '#94a3b8' }}>{e.kind}</td>
                    <td style={{ padding: 8, color: e.confidence >= 0.7 ? '#4ade80' : e.confidence >= 0.4 ? '#fbbf24' : '#f87171' }}>{e.confidence.toFixed(2)}</td>
                    <td style={{ padding: 8 }}>{e.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Dropped table */}
      {tab === 'dropped' && (
        <div>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 12 }}>
            Events that didn't clear the salience threshold. Nothing is silently lost — review here and adjust config if something useful is being filtered out.
          </p>
          {dropped.length === 0 ? (
            <div style={{ color: '#64748b', padding: 24, textAlign: 'center' }}>No dropped events.</div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#111827', textAlign: 'left' }}>
                  <th style={{ padding: 8 }}>when</th>
                  <th style={{ padding: 8 }}>source</th>
                  <th style={{ padding: 8 }}>kind</th>
                  <th style={{ padding: 8 }}>score</th>
                  <th style={{ padding: 8 }}>reason</th>
                  <th style={{ padding: 8 }}>text</th>
                </tr>
              </thead>
              <tbody>
                {dropped.map(d => (
                  <tr key={d.id} style={{ borderBottom: '1px solid #1f2937' }}>
                    <td style={{ padding: 8, color: '#64748b', whiteSpace: 'nowrap' }}>{timeAgo(d.created_at)}</td>
                    <td style={{ padding: 8, color: SOURCE_COLORS[d.source] || '#fff' }}>{d.source}</td>
                    <td style={{ padding: 8, color: '#94a3b8' }}>{d.kind}</td>
                    <td style={{ padding: 8, color: '#f87171' }}>{d.score.toFixed(2)}</td>
                    <td style={{ padding: 8, color: '#fbbf24', fontFamily: 'monospace', fontSize: 12 }}>{d.reason}</td>
                    <td style={{ padding: 8, color: '#94a3b8' }}>{d.text}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Consent tab */}
      {tab === 'consent' && (
        <div>
          <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 12 }}>
            Every (source, kind) is <strong style={{ color: '#f87171' }}>OFF by default</strong>. Writes without consent never touch <code>sensory_events</code> — they go to the blocked log below with reason <code>no_consent</code>. Flips are audit-logged.
          </p>

          {/* Grid of toggles grouped by source */}
          {Object.entries(
            consent.reduce<Record<string, ConsentRow[]>>((acc, r) => {
              (acc[r.source] ||= []).push(r)
              return acc
            }, {})
          ).map(([src, rows]) => (
            <div key={src} style={{ marginBottom: 16 }}>
              <h3 style={{ color: SOURCE_COLORS[src] || '#e5e7eb', marginBottom: 8, fontSize: 15 }}>
                {src} <span style={{ color: '#64748b', fontSize: 12, fontWeight: 400 }}>
                  ({rows.filter(r => r.enabled).length}/{rows.length} enabled)
                </span>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 8 }}>
                {rows.map(r => (
                  <label
                    key={`${r.source}.${r.kind}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: 10,
                      background: r.enabled ? '#064e3b' : '#111827',
                      border: `1px solid ${r.enabled ? '#10b981' : '#1f2937'}`,
                      borderRadius: 6,
                      cursor: 'pointer',
                      fontSize: 13,
                    }}
                  >
                    <input
                      type="checkbox"
                      checked={!!r.enabled}
                      onChange={async (e) => {
                        await setConsent(r.source, r.kind, e.target.checked, 'toggled from dashboard')
                        await refresh()
                      }}
                    />
                    <span style={{ flex: 1, fontFamily: 'monospace' }}>{r.kind}</span>
                    {r.enabled_at && r.enabled ? (
                      <span style={{ fontSize: 10, color: '#6ee7b7' }}>on since {timeAgo(r.enabled_at)}</span>
                    ) : null}
                  </label>
                ))}
              </div>
            </div>
          ))}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16, marginTop: 24 }}>
            <div>
              <h3 style={{ marginTop: 0, fontSize: 14 }}>Audit log (last 50)</h3>
              <div style={{ maxHeight: 300, overflowY: 'auto', background: '#0f172a', borderRadius: 6, padding: 8, fontSize: 11, fontFamily: 'monospace' }}>
                {consentLog.map(l => (
                  <div key={l.id} style={{ padding: '2px 0', color: l.action === 'enable' ? '#6ee7b7' : l.action === 'disable' ? '#fca5a5' : '#64748b' }}>
                    {timeAgo(l.created_at).padEnd(10)} {l.action.toUpperCase().padEnd(8)} {l.source}/{l.kind} by {l.actor || '?'}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 style={{ marginTop: 0, fontSize: 14 }}>Blocked (no_consent, last 50)</h3>
              <div style={{ maxHeight: 300, overflowY: 'auto', background: '#0f172a', borderRadius: 6, padding: 8, fontSize: 11 }}>
                {blocked.length === 0 ? (
                  <div style={{ color: '#64748b', padding: 8 }}>Nothing tried to write without consent. Good.</div>
                ) : blocked.map(b => (
                  <div key={b.id} style={{ padding: '4px 0', borderBottom: '1px solid #1f2937' }}>
                    <span style={{ color: SOURCE_COLORS[b.source] || '#fff' }}>{b.source}</span>
                    <span style={{ color: '#94a3b8' }}>/{b.kind}</span>
                    <span style={{ color: '#64748b', marginLeft: 8 }}>{timeAgo(b.created_at)}</span>
                    <div style={{ color: '#e5e7eb', marginTop: 2, fontFamily: 'monospace' }}>{b.text}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Config + score tester */}
      {tab === 'config' && config && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <div>
            <h3 style={{ marginTop: 0 }}>Salience Config</h3>
            <p style={{ color: '#94a3b8', fontSize: 12 }}>Raw JSON — edit and save. Hot-reloads on next event.</p>
            <textarea
              value={JSON.stringify(config, null, 2)}
              onChange={e => {
                try { setConfig(JSON.parse(e.target.value)) } catch {}
              }}
              style={{
                width: '100%',
                height: 500,
                background: '#0f172a',
                color: '#e5e7eb',
                border: '1px solid #1f2937',
                borderRadius: 6,
                padding: 12,
                fontFamily: 'monospace',
                fontSize: 12,
              }}
            />
            <button
              onClick={saveConfigEdit}
              style={{
                marginTop: 8,
                background: '#2563eb',
                color: '#fff',
                border: 'none',
                borderRadius: 6,
                padding: '8px 16px',
                cursor: 'pointer',
                fontSize: 13,
              }}
            >Save Config</button>
          </div>

          <div>
            <h3 style={{ marginTop: 0 }}>Score Tester</h3>
            <p style={{ color: '#94a3b8', fontSize: 12 }}>Test whether an event would promote without writing it.</p>
            <div style={{ display: 'grid', gap: 8 }}>
              <label style={{ fontSize: 12, color: '#94a3b8' }}>Source
                <select value={testSource} onChange={e => setTestSource(e.target.value)} style={{ width: '100%', background: '#0f172a', color: '#e5e7eb', border: '1px solid #1f2937', padding: 6, borderRadius: 4 }}>
                  <option>mic</option><option>camera</option><option>screen</option><option>clipboard</option><option>system</option><option>ambient</option>
                </select>
              </label>
              <label style={{ fontSize: 12, color: '#94a3b8' }}>Kind
                <input value={testKind} onChange={e => setTestKind(e.target.value)} style={{ width: '100%', background: '#0f172a', color: '#e5e7eb', border: '1px solid #1f2937', padding: 6, borderRadius: 4 }} />
              </label>
              <label style={{ fontSize: 12, color: '#94a3b8' }}>Confidence ({testConf.toFixed(2)})
                <input type="range" min="0" max="1" step="0.05" value={testConf} onChange={e => setTestConf(parseFloat(e.target.value))} style={{ width: '100%' }} />
              </label>
              <label style={{ fontSize: 12, color: '#94a3b8' }}>Text
                <textarea value={testText} onChange={e => setTestText(e.target.value)} rows={4} style={{ width: '100%', background: '#0f172a', color: '#e5e7eb', border: '1px solid #1f2937', padding: 6, borderRadius: 4, fontFamily: 'inherit' }} />
              </label>
              <button onClick={runScoreTest} style={{ background: '#059669', color: '#fff', border: 'none', borderRadius: 6, padding: '8px 16px', cursor: 'pointer', fontSize: 13 }}>Score It</button>
            </div>
            {testResult && (
              <div style={{ marginTop: 16, padding: 12, background: '#111827', borderRadius: 6, border: `1px solid ${testResult.would_promote ? '#059669' : '#dc2626'}` }}>
                <div style={{ fontSize: 20, fontWeight: 600, color: testResult.would_promote ? '#4ade80' : '#f87171' }}>
                  {testResult.would_promote ? 'PROMOTE' : 'DROP'} — score {testResult.score.toFixed(2)} (threshold {testResult.threshold.toFixed(2)})
                </div>
                <div style={{ fontSize: 12, color: '#94a3b8', fontFamily: 'monospace', marginTop: 4 }}>{testResult.reason}</div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SensoryPage
