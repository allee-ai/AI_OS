import React, { useState, useCallback, useRef } from 'react';
import { FileExplorer } from './FileExplorer';
import { FileViewer } from './FileViewer';
import { useWorkspace } from '../hooks/useWorkspace';
import './WorkspacePanel.css';

export const WorkspacePanel: React.FC = () => {
  const workspace = useWorkspace();
  const [searchInput, setSearchInput] = useState('');
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced search
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      workspace.searchFiles(value);
    }, 300);
  }, [workspace.searchFiles]);

  return (
    <div className="workspace-panel-container">
      <div className="workspace-header">
        <h2>📂 Workspace</h2>
        <div className="workspace-search">
          <input
            type="text"
            className="search-input"
            placeholder="🔍 Search files..."
            value={searchInput}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>
      </div>

      {/* Search results overlay */}
      {workspace.searchQuery && (
        <div className="search-results-panel">
          <div className="search-results-header">
            <span>Results for "{workspace.searchQuery}"</span>
            <button
              className="search-clear"
              onClick={() => { setSearchInput(''); workspace.searchFiles(''); }}
            >
              ✕
            </button>
          </div>
          {workspace.searchLoading ? (
            <div className="search-loading">Searching...</div>
          ) : workspace.searchResults.length === 0 ? (
            <div className="search-empty">No matches found</div>
          ) : (
            <div className="search-results-list">
              {workspace.searchResults.map((r, i) => (
                <div
                  key={i}
                  className="search-result-item"
                  onClick={() => {
                    workspace.handleOpenFile({ id: r.path, name: r.name, path: r.path, type: 'file', createdAt: new Date(), updatedAt: new Date() });
                    setSearchInput('');
                    workspace.searchFiles('');
                  }}
                >
                  <span className="result-name">{r.name}</span>
                  <span className="result-path">{r.path}</span>
                  {r.snippet && (
                    <span className="result-snippet" dangerouslySetInnerHTML={{ __html: r.snippet }} />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      <div className="workspace-split">
        {/* Left: File explorer */}
        <div className="workspace-explorer-pane">
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
            onOpenFile={workspace.handleOpenFile}
            activeFilePath={workspace.openFile?.path ?? null}
          />
        </div>

        {/* Right: File viewer */}
        <div className={`workspace-viewer-pane ${workspace.openFile || workspace.openFileLoading ? 'open' : ''}`}>
          <FileViewer
            file={workspace.openFile}
            isLoading={workspace.openFileLoading}
            onClose={workspace.closeFile}
            onSummarize={workspace.summarizeFile}
            getImageUrl={workspace.getImageUrl}
          />
        </div>
      </div>
    </div>
  );
};
