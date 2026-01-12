import React, { useState } from 'react';
import './HEACell.css';

interface HEACellProps {
  data: any;
  level: 'l1' | 'l2' | 'l3';
  module: string;
}

export const HEACell: React.FC<HEACellProps> = ({ data, level, module }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  const isEmpty = !data || (typeof data === 'object' && Object.keys(data).length === 0);

  const getPreview = () => {
    if (isEmpty) return <span className="empty-cell">—</span>;
    
    if (typeof data === 'string') {
      return data.length > 50 ? `${data.substring(0, 50)}...` : data;
    }
    
    if (typeof data === 'object') {
      const keys = Object.keys(data);
      const preview = keys.slice(0, 3).join(', ');
      return keys.length > 3 ? `${preview}... (+${keys.length - 3})` : preview;
    }
    
    return String(data);
  };

  const handleClick = () => {
    if (!isEmpty) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div className={`hea-cell ${isEmpty ? 'empty' : ''} ${isExpanded ? 'expanded' : ''}`}>
      <div className="cell-preview" onClick={handleClick}>
        {getPreview()}
        {!isEmpty && (
          <button className="expand-button" title={isExpanded ? 'Collapse' : 'Expand'}>
            {isExpanded ? '▼' : '▶'}
          </button>
        )}
      </div>
      
      {isExpanded && !isEmpty && (
        <div className="cell-expanded">
          <div className="expanded-header">
            <span className="expanded-title">{module} • {level.toUpperCase()}</span>
            <button className="close-button" onClick={() => setIsExpanded(false)}>×</button>
          </div>
          <pre className="json-content">{JSON.stringify(data, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
