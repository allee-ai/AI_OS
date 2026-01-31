import React from 'react';
import { FileExplorer } from './FileExplorer';
import { useWorkspace } from '../hooks/useWorkspace';
import './WorkspacePanel.css';

export const WorkspacePanel: React.FC = () => {
  const workspace = useWorkspace();

  return (
    <div className="workspace-panel-container">
      <div className="workspace-header">
        <h2>📂 Workspace</h2>
        <p className="workspace-subtitle">File Storage & Management</p>
      </div>
      
      <FileExplorer
        files={workspace.files}
        currentPath={workspace.currentPath}
        selectedFiles={workspace.selectedFiles}
        isLoading={workspace.isLoading}
        error={workspace.error}
        onNavigateTo={workspace.navigateTo}
        onNavigateUp={workspace.navigateUp}
        onUploadFiles={workspace.uploadFiles}
        onDeleteFile={workspace.deleteFile}
        onCreateFolder={workspace.createFolder}
        onDownloadFile={workspace.downloadFile}
        onToggleSelect={workspace.toggleSelect}
        onMoveFile={workspace.moveFile}
      />
    </div>
  );
};
