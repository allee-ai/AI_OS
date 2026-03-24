import React, { useState, useEffect } from 'react';

interface StatusCardProps {
  title: string;
  value: number;
  unit?: string;
  trend?: 'up' | 'down' | 'flat';
}

const StatusCard: React.FC<StatusCardProps> = ({ title, value, unit = '', trend = 'flat' }) => {
  const [animate, setAnimate] = useState(false);

  useEffect(() => {
    setAnimate(true);
    const timer = setTimeout(() => setAnimate(false), 300);
    return () => clearTimeout(timer);
  }, [value]);

  const trendIcon = { up: '↑', down: '↓', flat: '→' }[trend];
  const trendColor = { up: 'var(--green)', down: 'var(--red)', flat: 'var(--text-secondary)' }[trend];

  return (
    <div className={`status-card ${animate ? 'pulse' : ''}`}>
      <h3>{title}</h3>
      <div className="value">
        <span className="number">{value.toLocaleString()}</span>
        {unit && <span className="unit">{unit}</span>}
      </div>
      <span style={{ color: trendColor }}>{trendIcon}</span>
    </div>
  );
};

export default StatusCard;
