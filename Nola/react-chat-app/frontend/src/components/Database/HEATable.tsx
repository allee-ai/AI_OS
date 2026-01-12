import React from 'react';
import { HEACell } from './HEACell';
import './HEATable.css';

// Updated interface to match new thread API response format
interface HEARecord {
  module: string;
  key?: string;  // Row key within the module
  context_level: number;
  level_label: string;
  data: any;
  metadata: any;
  weight?: number;  // Importance weight 0.0-1.0
  updated_at: string;
}

interface HEATableProps {
  data: HEARecord[];
  threadName: string;
  contextLevel: 1 | 2 | 3;
}

export const HEATable: React.FC<HEATableProps> = ({ data, threadName, contextLevel }) => {
  const getLevelEmoji = (level: number): string => {
    switch (level) {
      case 1: return '⚡'; // Quick/minimal
      case 2: return '💬'; // Conversational
      case 3: return '🧠'; // Deep/analytical
      default: return '📊';
    }
  };

  const getLevelName = (level: number): string => {
    switch (level) {
      case 1: return 'Realtime';
      case 2: return 'Conversational';
      case 3: return 'Analytical';
      default: return 'Unknown';
    }
  };

  return (
    <div className="hea-table-container">
      <div className="table-header">
        <h3>
          {getLevelEmoji(contextLevel)} {threadName} Thread
          <span className="level-badge">L{contextLevel} • {getLevelName(contextLevel)}</span>
        </h3>
        <span className="record-count">{data.length} modules</span>
      </div>
      
      <div className="hea-table-scroll">
        <table className="hea-table">
          <thead>
            <tr>
              <th className="module-column">Module / Key</th>
              <th className="data-column">L{contextLevel} Data</th>
              <th className="meta-column">Weight</th>
              <th className="meta-column">Updated</th>
            </tr>
          </thead>
          <tbody>
            {data.map((record, idx) => (
              <tr key={record.key || `${record.module}-${idx}`}>
                <td className="module-cell">
                  <div className="module-name">{record.module}</div>
                  {record.key && (
                    <div className="module-key">{record.key}</div>
                  )}
                </td>
                <td className="data-cell">
                  <HEACell 
                    data={record.data} 
                    level={`l${contextLevel}` as 'l1' | 'l2' | 'l3'} 
                    module={record.module} 
                  />
                </td>
                <td className="status-cell">
                  {record.weight !== undefined ? (
                    <span className="weight-badge" title={`Weight: ${record.weight}`}>
                      {(record.weight * 100).toFixed(0)}%
                    </span>
                  ) : (
                    <span className="status-badge unknown">-</span>
                  )}
                </td>
                <td className="meta-cell">
                  <div className="timestamp" title={record.updated_at}>
                    {new Date(record.updated_at).toLocaleDateString()}
                  </div>
                  <div className="time-detail">
                    {new Date(record.updated_at).toLocaleTimeString()}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-footer">
        <div className="footer-info">
          <span className="info-item">
            📊 Showing Level {contextLevel} context data
          </span>
          <span className="info-item">
            {contextLevel === 1 && '~10 tokens per module'}
            {contextLevel === 2 && '~50 tokens per module'}
            {contextLevel === 3 && '~200 tokens per module'}
          </span>
        </div>
      </div>
    </div>
  );
};
