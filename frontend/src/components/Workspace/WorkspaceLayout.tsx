import React, { useState, useCallback } from 'react';
import './WorkspaceLayout.css';

interface WorkspaceLayoutProps {
  leftPanel: React.ReactNode;
  centerPanel: React.ReactNode;
  rightPanel: React.ReactNode;
}

export const WorkspaceLayout: React.FC<WorkspaceLayoutProps> = ({ 
  leftPanel, 
  centerPanel, 
  rightPanel 
}) => {
  const [leftWidth, setLeftWidth] = useState(300);
  const [rightWidth, setRightWidth] = useState(320);
  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isResizingLeft) {
      const newWidth = Math.min(Math.max(220, e.clientX - 20), 420);
      setLeftWidth(newWidth);
    } else if (isResizingRight) {
      const newWidth = Math.min(Math.max(220, window.innerWidth - e.clientX - 20), 420);
      setRightWidth(newWidth);
    }
  }, [isResizingLeft, isResizingRight]);

  const handleMouseUp = useCallback(() => {
    setIsResizingLeft(false);
    setIsResizingRight(false);
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  }, []);

  React.useEffect(() => {
    if (isResizingLeft || isResizingRight) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizingLeft, isResizingRight, handleMouseMove, handleMouseUp]);

  return (
    <div className="workspace-layout">
      {/* Left Sidebar - Memory/Files */}
      <aside className="workspace-sidebar workspace-left" style={{ width: leftWidth }}>
        <div className="sidebar-content">
          {leftPanel}
        </div>
      </aside>
      
      {/* Left Resize Handle */}
      <div 
        className="resize-handle resize-handle-left"
        onMouseDown={() => setIsResizingLeft(true)}
      />

      {/* Center - Chat */}
      <main className="workspace-center">
        <div className="center-content">
          {centerPanel}
        </div>
      </main>

      {/* Right Resize Handle */}
      <div 
        className="resize-handle resize-handle-right"
        onMouseDown={() => setIsResizingRight(true)}
      />

      {/* Right Sidebar - TBD */}
      <aside className="workspace-sidebar workspace-right" style={{ width: rightWidth }}>
        <div className="sidebar-content">
          {rightPanel}
        </div>
      </aside>
    </div>
  );
};
