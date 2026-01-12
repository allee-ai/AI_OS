import React, { useState } from 'react';
import { MemoryPanel } from '../Database/MemoryPanel';
import { WorkspacePanel } from '../Workspace/WorkspacePanel';
import './SidePanel.css';

type TabType = 'memory' | 'files';

export const SidePanel: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('memory');

  return (
    <div className="side-panel">
      <div className="side-panel-tabs">
        <button
          className={`tab-button ${activeTab === 'memory' ? 'active' : ''}`}
          onClick={() => setActiveTab('memory')}
        >
          🧠 Memory
        </button>
        <button
          className={`tab-button ${activeTab === 'files' ? 'active' : ''}`}
          onClick={() => setActiveTab('files')}
        >
          📁 Files
        </button>
      </div>

      <div className="side-panel-content">
        {activeTab === 'memory' && <MemoryPanel />}
        {activeTab === 'files' && <WorkspacePanel />}
      </div>
    </div>
  );
};
