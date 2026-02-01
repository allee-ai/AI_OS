/**
 * Subconscious Dashboard
 * ======================
 * Monitors background loops, temp_facts, and memory consolidation.
 * 
 * This is the "brain monitor" - shows what's happening behind the scenes:
 * - Background loop status (running, paused, errors)
 * - Temp facts pending consolidation
 * - Potentiation stats (SHORT vs LONG memory)
 * - Export readiness for finetuning
 */

import { useState, useEffect, useCallback } from 'react';
import './SubconsciousDashboard.css';

interface LoopStats {
  name: string;
  status: string;
  interval: number;
  last_run: string | null;
  run_count: number;
  error_count: number;
  consecutive_errors: number;
}

interface TempFact {
  id: number;
  text: string;
  status: string;
}

interface PotentiationStats {
  SHORT: { count: number; avg_strength: number; avg_fires: number };
  LONG: { count: number; avg_strength: number; avg_fires: number };
}

const STATUS_COLORS: Record<string, string> = {
  running: '#22c55e',
  stopped: '#6b7280',
  paused: '#f59e0b',
  error: '#ef4444'
};

export default function SubconsciousDashboard() {
  const [loops, setLoops] = useState<LoopStats[]>([]);
  const [tempFacts, setTempFacts] = useState<TempFact[]>([]);
  const [factsByStatus, setFactsByStatus] = useState<Record<string, number>>({});
  const [potentiation, setPotentiation] = useState<PotentiationStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [loopsRes, factsRes, potRes] = await Promise.all([
        fetch('http://localhost:8000/api/subconscious/loops'),
        fetch('http://localhost:8000/api/subconscious/temp-facts'),
        fetch('http://localhost:8000/api/subconscious/potentiation')
      ]);

      if (loopsRes.ok) {
        const data = await loopsRes.json();
        setLoops(data.loops || []);
      }

      if (factsRes.ok) {
        const data = await factsRes.json();
        setTempFacts(data.recent || []);
        setFactsByStatus(data.by_status || {});
      }

      if (potRes.ok) {
        const data = await potRes.json();
        setPotentiation(data.potentiation || null);
      }
    } catch (err) {
      console.error('Failed to fetch subconscious data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleConsolidate = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/subconscious/consolidate', {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setExportResult(`Consolidated: ${data.result?.promoted || 0} links promoted to LONG`);
        fetchData();
      }
    } catch (err) {
      setExportResult('Consolidation failed');
    }
    setTimeout(() => setExportResult(null), 3000);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch('http://localhost:8000/api/finetune/export', {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        const total = data.results?.combined?.total_examples || 0;
        setExportResult(`Exported ${total} training examples`);
      }
    } catch (err) {
      setExportResult('Export failed');
    } finally {
      setExporting(false);
      setTimeout(() => setExportResult(null), 5000);
    }
  };

  if (loading) {
    return <div className="subconscious-dashboard loading">Loading subconscious...</div>;
  }

  const totalPending = Object.values(factsByStatus).reduce((a, b) => a + b, 0);
  const longCount = potentiation?.LONG?.count || 0;
  const shortCount = potentiation?.SHORT?.count || 0;

  return (
    <div className="subconscious-dashboard">
      {/* Header Stats */}
      <div className="subconscious-stats">
        <div className="stat-card">
          <span className="stat-value">{loops.length}</span>
          <span className="stat-label">Background Loops</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{totalPending}</span>
          <span className="stat-label">Pending Facts</span>
        </div>
        <div className="stat-card">
          <span className="stat-value">{shortCount}</span>
          <span className="stat-label">SHORT Memory</span>
        </div>
        <div className="stat-card highlight">
          <span className="stat-value">{longCount}</span>
          <span className="stat-label">LONG Memory</span>
        </div>
      </div>

      {/* Actions */}
      <div className="subconscious-actions">
        <button onClick={handleConsolidate} className="action-btn consolidate">
          🧠 Consolidate Memory
        </button>
        <button onClick={handleExport} disabled={exporting} className="action-btn export">
          {exporting ? '⏳ Exporting...' : '📦 Export Training Data'}
        </button>
        {exportResult && <span className="action-result">{exportResult}</span>}
      </div>

      <div className="subconscious-layout">
        {/* Left: Loop Status */}
        <div className="panel loops-panel">
          <h3>🔄 Background Loops</h3>
          <div className="loops-list">
            {loops.map(loop => (
              <div key={loop.name} className="loop-item">
                <div className="loop-header">
                  <span 
                    className="loop-status-dot"
                    style={{ background: STATUS_COLORS[loop.status] || '#6b7280' }}
                  />
                  <span className="loop-name">{loop.name}</span>
                  <span className="loop-status-label">{loop.status}</span>
                </div>
                <div className="loop-details">
                  <span>Every {loop.interval}s</span>
                  <span>Runs: {loop.run_count}</span>
                  {loop.error_count > 0 && (
                    <span className="loop-errors">Errors: {loop.error_count}</span>
                  )}
                </div>
                {loop.last_run && (
                  <div className="loop-last-run">
                    Last: {new Date(loop.last_run).toLocaleTimeString()}
                  </div>
                )}
              </div>
            ))}
            {loops.length === 0 && (
              <div className="no-data">No loops registered</div>
            )}
          </div>
        </div>

        {/* Middle: Temp Facts */}
        <div className="panel facts-panel">
          <h3>📝 Temp Facts</h3>
          <div className="facts-status-bar">
            {Object.entries(factsByStatus).map(([status, count]) => (
              <div key={status} className={`status-chip ${status}`}>
                {status}: {count}
              </div>
            ))}
          </div>
          <div className="facts-list">
            {tempFacts.map(fact => (
              <div key={fact.id} className={`fact-item ${fact.status}`}>
                <span className="fact-text">{fact.text}</span>
                <span className={`fact-status ${fact.status}`}>{fact.status}</span>
              </div>
            ))}
            {tempFacts.length === 0 && (
              <div className="no-data">No pending facts</div>
            )}
          </div>
        </div>

        {/* Right: Potentiation */}
        <div className="panel potentiation-panel">
          <h3>⚡ Memory Potentiation</h3>
          <div className="potentiation-visual">
            <div className="potentiation-bar">
              <div 
                className="bar-short"
                style={{ width: `${(shortCount / (shortCount + longCount || 1)) * 100}%` }}
              >
                SHORT
              </div>
              <div 
                className="bar-long"
                style={{ width: `${(longCount / (shortCount + longCount || 1)) * 100}%` }}
              >
                LONG
              </div>
            </div>
          </div>
          
          {potentiation && (
            <div className="potentiation-details">
              <div className="pot-row">
                <span className="pot-label">SHORT</span>
                <span className="pot-count">{shortCount} links</span>
                <span className="pot-meta">
                  avg strength: {potentiation.SHORT?.avg_strength?.toFixed(2) || '0'}
                </span>
              </div>
              <div className="pot-row highlight">
                <span className="pot-label">LONG</span>
                <span className="pot-count">{longCount} links</span>
                <span className="pot-meta">
                  avg fires: {potentiation.LONG?.avg_fires?.toFixed(1) || '0'}
                </span>
              </div>
            </div>
          )}

          <div className="export-readiness">
            <h4>📦 Export Readiness</h4>
            <p>{longCount} consolidated memories ready for finetuning</p>
            {longCount >= 50 && (
              <span className="ready-badge">✓ Ready to export</span>
            )}
            {longCount < 50 && longCount > 0 && (
              <span className="building-badge">Building... ({longCount}/50)</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
