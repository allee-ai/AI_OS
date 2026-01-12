import React, { useEffect, useState } from 'react';
import { HEATable } from './HEATable';
import { apiService } from '../../services/api';
import './DatabasePanel.css';

// Updated interface to match new API response format
interface HEARecord {
  module: string;
  context_level: number;
  level_label: string;
  data: any;
  metadata: any;
  updated_at: string;
}

interface HEAResponse {
  thread: string;
  context_level: number;
  data: HEARecord[];
}

export const DatabasePanel: React.FC = () => {
  const [data, setData] = useState<HEARecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedThread, setSelectedThread] = useState('identity');
  const [contextLevel, setContextLevel] = useState<1 | 2 | 3>(2);

  useEffect(() => {
    loadData();
  }, [selectedThread, contextLevel]);

  const loadData = async () => {
    try {
      setIsLoading(true);
      setError(null);
      
      const response: HEAResponse = await apiService.getIdentityHEA(contextLevel);
      setData(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load database');
      console.error('Error loading database:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefresh = () => {
    loadData();
  };

  const getLevelDescription = (level: number): string => {
    switch (level) {
      case 1: return 'Minimal (~10 tokens)';
      case 2: return 'Moderate (~50 tokens)';
      case 3: return 'Full (~200 tokens)';
      default: return '';
    }
  };

  return (
    <div className="database-panel">
      <div className="database-header">
        <div className="header-left">
          <h2>🗄️ Database Explorer</h2>
          <button 
            className="refresh-button" 
            onClick={handleRefresh}
            disabled={isLoading}
            title="Refresh data"
          >
            ↻
          </button>
        </div>
        
        <div className="header-controls">
          {/* Context Level Selector */}
          <div className="context-level-selector">
            <label>Context Level:</label>
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
            <span className="level-description">{getLevelDescription(contextLevel)}</span>
          </div>

          {/* Thread Selector */}
          <div className="thread-selector">
            <button 
              className={`thread-button ${selectedThread === 'identity' ? 'active' : ''}`}
              onClick={() => setSelectedThread('identity')}
            >
              Identity
            </button>
          </div>
        </div>
      </div>

      <div className="database-content">
        {isLoading && (
          <div className="loading-state">
            <div className="spinner"></div>
            <p>Loading L{contextLevel} context...</p>
          </div>
        )}

        {error && (
          <div className="error-state">
            <p>⚠️ {error}</p>
            <button onClick={loadData}>Retry</button>
          </div>
        )}

        {!isLoading && !error && data.length === 0 && (
          <div className="empty-state">
            <p>No data available for L{contextLevel}</p>
          </div>
        )}

        {!isLoading && !error && data.length > 0 && (
          <HEATable 
            data={data} 
            threadName={selectedThread} 
            contextLevel={contextLevel}
          />
        )}
      </div>
    </div>
  );
};
