import React, { useState, useEffect } from 'react';
import './DatabaseToggle.css';

interface DatabaseMode {
  mode: string;
  database: string;
}

export const DatabaseToggle: React.FC = () => {
  const [mode, setMode] = useState<string>('personal');
  const [isLoading, setIsLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [pendingMode, setPendingMode] = useState<string | null>(null);

  // Load current mode on mount
  useEffect(() => {
    const loadMode = async () => {
      try {
        const response = await fetch('/api/db-mode/mode');
        if (response.ok) {
          const data: DatabaseMode = await response.json();
          setMode(data.mode);
        }
      } catch (error) {
        console.log('Could not fetch database mode');
      }
    };
    loadMode();
  }, []);

  const handleToggle = () => {
    const newMode = mode === 'personal' ? 'demo' : 'personal';
    setPendingMode(newMode);
    setShowConfirm(true);
  };

  const confirmSwitch = async () => {
    if (!pendingMode) return;
    
    setIsLoading(true);
    setShowConfirm(false);
    
    try {
      const response = await fetch(`/api/db-mode/mode/${pendingMode}`, {
        method: 'POST'
      });
      
      if (response.ok) {
        // Wait for server to restart then reload page
        setTimeout(() => {
          window.location.reload();
        }, 2500);
      }
    } catch (error) {
      console.error('Failed to switch mode:', error);
      setIsLoading(false);
    }
  };

  const cancelSwitch = () => {
    setShowConfirm(false);
    setPendingMode(null);
  };

  return (
    <div className="database-toggle">
      <button 
        className={`db-toggle-switch ${mode}`}
        onClick={handleToggle}
        disabled={isLoading}
        title={`Currently: ${mode}. Click to switch`}
      >
        <span className="switch-track">
          <span className="switch-thumb"></span>
        </span>
        <span className="switch-labels">
          <span className={`label ${mode === 'personal' ? 'active' : ''}`}>👤</span>
          <span className={`label ${mode === 'demo' ? 'active' : ''}`}>🎮</span>
        </span>
      </button>

      {showConfirm && (
        <div className="db-confirm-overlay">
          <div className="db-confirm-modal">
            <h3>Restart with {pendingMode} DB?</h3>
            <div className="db-confirm-buttons">
              <button onClick={cancelSwitch} className="db-cancel">N</button>
              <button onClick={confirmSwitch} className="db-confirm">Y</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
