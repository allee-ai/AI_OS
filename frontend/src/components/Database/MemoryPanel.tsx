import React, { useEffect, useState } from 'react';
import { HEATable } from './HEATable';
import { apiService } from '../../services/api';
import './MemoryPanel.css';

// Updated interface to match new thread API response format
interface HEARecord {
  module: string;
  key?: string;
  context_level: number;
  level_label: string;
  data: any;
  metadata: any;
  weight?: number;
  updated_at: string;
}

// Interface for tracking changes
interface ChangeRecord {
  timestamp: string;
  module: string;
  field: string;
  oldValue: any;
  newValue: any;
  context_level: number;
}

export const MemoryPanel: React.FC = () => {
  const [data, setData] = useState<HEARecord[]>([]);
  const [changes, setChanges] = useState<ChangeRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'identity' | 'dynamic'>('identity');
  const [contextLevel, setContextLevel] = useState<1 | 2 | 3>(2);

  useEffect(() => {
    loadData();
  }, [activeTab, contextLevel]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      if (activeTab === 'identity') {
        const response = await apiService.getIdentityHEA(contextLevel);
        setData(response.data);
      } else {
        // For dynamic tab, we'll show changes/history
        // For now, fetch from a changes endpoint or show placeholder
        try {
          const response = await apiService.getIdentityChanges(contextLevel);
          setChanges(response.changes || []);
        } catch {
          // If endpoint doesn't exist yet, show empty state
          setChanges([]);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load memory');
      console.error('Error loading memory:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => {
    loadData();
  };

  const getLevelDescription = (level: number): string => {
    switch (level) {
      case 1: return 'Minimal';
      case 2: return 'Moderate';
      case 3: return 'Full';
      default: return '';
    }
  };

  const formatTimestamp = (ts: string) => {
    const date = new Date(ts);
    return date.toLocaleString();
  };

  return (
    <div className="memory-panel">
      <div className="memory-header">
        <div className="header-row">
          <div className="header-left">
            <h3>🧠 Memory</h3>
            <button 
              className="refresh-button" 
              onClick={handleRefresh}
              disabled={isLoading}
              title="Refresh data"
            >
              ↻
            </button>
          </div>
          
          {/* Context Level Selector */}
          <div className="context-level-selector">
            <div className="level-buttons">
              {[1, 2, 3].map((level) => (
                <button
                  key={level}
                  className={`level-button ${contextLevel === level ? 'active' : ''}`}
                  onClick={() => setContextLevel(level as 1 | 2 | 3)}
                  title={getLevelDescription(level)}
                >
                  L{level}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="tab-selector">
          <button 
            className={`tab-button ${activeTab === 'identity' ? 'active' : ''}`}
            onClick={() => setActiveTab('identity')}
          >
            📋 Identity
            <span className="tab-hint">Initial State</span>
          </button>
          <button 
            className={`tab-button ${activeTab === 'dynamic' ? 'active' : ''}`}
            onClick={() => setActiveTab('dynamic')}
          >
            🔄 Dynamic
            <span className="tab-hint">Changes</span>
          </button>
        </div>
      </div>

      <div className="memory-content">
        {isLoading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading {activeTab}...</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <p>⚠️ {error}</p>
            <button onClick={loadData}>Retry</button>
          </div>
        )}

        {/* Identity Tab Content */}
        {activeTab === 'identity' && !isLoading && !error && (
          <>
            {data.length === 0 ? (
              <div className="empty-state">
                <p>No identity data available</p>
                <p className="hint">Identity modules define who Nola is</p>
              </div>
            ) : (
              <HEATable data={data} threadName="Identity" contextLevel={contextLevel} />
            )}
          </>
        )}

        {/* Dynamic Tab Content */}
        {activeTab === 'dynamic' && !isLoading && !error && (
          <>
            {changes.length === 0 ? (
              <div className="empty-state">
                <div className="empty-icon">🔄</div>
                <p>No changes recorded yet</p>
                <p className="hint">Changes to identity will appear here as they happen</p>
              </div>
            ) : (
              <div className="changes-list">
                {changes.map((change, idx) => (
                  <div key={idx} className="change-card">
                    <div className="change-header">
                      <span className="change-module">{change.module}</span>
                      <span className="change-time">{formatTimestamp(change.timestamp)}</span>
                    </div>
                    <div className="change-field">{change.field}</div>
                    <div className="change-diff">
                      <div className="old-value">
                        <span className="diff-label">−</span>
                        <span className="diff-content">{JSON.stringify(change.oldValue)}</span>
                      </div>
                      <div className="new-value">
                        <span className="diff-label">+</span>
                        <span className="diff-content">{JSON.stringify(change.newValue)}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
