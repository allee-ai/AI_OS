import React, { useRef, useState } from 'react';
import type { WorkspaceFile } from '../../types/workspace';
import './FileExplorer.css';

interface FileExplorerProps {
  files: WorkspaceFile[];
  currentPath: string;
  selectedFiles: string[];
  isLoading: boolean;
  error: string | null;
  onNavigateTo: (path: string) => void;
  onNavigateUp: () => void;
  onUploadFiles: (files: FileList) => void;
  onDeleteFile: (fileId: string, filePath: string) => void;
  onCreateFolder: (name: string) => void;
  onDownloadFile: (file: WorkspaceFile) => void;
  onToggleSelect: (fileId: string) => void;
  onMoveFile: (sourceId: string, targetPath: string) => void;
}

// File icon based on type/extension
function getFileIcon(file: WorkspaceFile): string {
  if (file.type === 'folder') return '📁';
  
  const ext = file.name.split('.').pop()?.toLowerCase();
  const iconMap: Record<string, string> = {
    pdf: '📄',
    doc: '📝', docx: '📝',
    xls: '📊', xlsx: '📊',
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', svg: '🖼️',
    mp3: '🎵', wav: '🎵', flac: '🎵',
    mp4: '🎬', mov: '🎬', avi: '🎬',
    zip: '📦', tar: '📦', gz: '📦', rar: '📦',
    js: '⚡', ts: '💠', jsx: '⚛️', tsx: '⚛️',
    py: '🐍',
    json: '{ }',
    md: '📑',
    txt: '📃',
  };
  
  return iconMap[ext || ''] || '📄';
}

// Format file size
function formatSize(bytes?: number): string {
  if (!bytes) return '-';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024;
    i++;
  }
  return `${size.toFixed(1)} ${units[i]}`;
}

export const FileExplorer: React.FC<FileExplorerProps> = ({
  files,
  currentPath,
  selectedFiles,
  isLoading,
  error,
  onNavigateTo,
  onNavigateUp,
  onUploadFiles,
  onDeleteFile,
  onCreateFolder,
  onDownloadFile,
  onToggleSelect,
  onMoveFile,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showNewFolderDialog, setShowNewFolderDialog] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [dragOverId, setDragOverId] = useState<string | null>(null);

  // Handle file upload click
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  // Handle file input change
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onUploadFiles(e.target.files);
      e.target.value = ''; // Reset input
    }
  };

  // Handle new folder creation
  const handleCreateFolder = () => {
    if (newFolderName.trim()) {
      onCreateFolder(newFolderName.trim());
      setNewFolderName('');
      setShowNewFolderDialog(false);
    }
  };

  // Handle file click
  const handleFileClick = (file: WorkspaceFile, e: React.MouseEvent) => {
    if (e.ctrlKey || e.metaKey) {
      onToggleSelect(file.id);
    } else if (file.type === 'folder') {
      onNavigateTo(file.path);
    }
  };

  // Handle double click
  const handleDoubleClick = (file: WorkspaceFile) => {
    if (file.type === 'folder') {
      onNavigateTo(file.path);
    } else {
      onDownloadFile(file);
    }
  };

  // Drag and drop handlers
  const handleDragStart = (e: React.DragEvent, file: WorkspaceFile) => {
    e.dataTransfer.setData('fileId', file.id);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, file: WorkspaceFile) => {
    if (file.type === 'folder') {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      setDragOverId(file.id);
    }
  };

  const handleDragLeave = () => {
    setDragOverId(null);
  };

  const handleDrop = (e: React.DragEvent, targetFolder: WorkspaceFile) => {
    e.preventDefault();
    setDragOverId(null);
    const sourceId = e.dataTransfer.getData('fileId');
    if (sourceId && targetFolder.type === 'folder') {
      onMoveFile(sourceId, targetFolder.path);
    }
  };

  // Breadcrumb navigation
  const pathParts = currentPath.split('/').filter(Boolean);
  const breadcrumbs = [
    { name: 'Home', path: '/' },
    ...pathParts.map((part, i) => ({
      name: part,
      path: '/' + pathParts.slice(0, i + 1).join('/'),
    })),
  ];

  return (
    <div className="file-explorer">
      {/* Toolbar */}
      <div className="file-explorer-toolbar">
        <button 
          className="toolbar-btn" 
          onClick={onNavigateUp}
          disabled={currentPath === '/'}
          title="Go up"
        >
          ⬆️
        </button>
        <button 
          className="toolbar-btn" 
          onClick={handleUploadClick}
          title="Upload files"
        >
          📤 Upload
        </button>
        <button 
          className="toolbar-btn" 
          onClick={() => setShowNewFolderDialog(true)}
          title="New folder"
        >
          📁+ New Folder
        </button>
        {selectedFiles.length > 0 && (
          <button 
            className="toolbar-btn danger" 
            onClick={() => {
              const filesToDelete = files.filter(f => selectedFiles.includes(f.id));
              filesToDelete.forEach(f => onDeleteFile(f.id, f.path));
            }}
            title="Delete selected"
          >
            🗑️ Delete ({selectedFiles.length})
          </button>
        )}
        
        <input
          ref={fileInputRef}
          type="file"
          multiple
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
      </div>

      {/* Breadcrumb */}
      <div className="file-explorer-breadcrumb">
        {breadcrumbs.map((crumb, i) => (
          <span key={crumb.path}>
            {i > 0 && <span className="breadcrumb-separator">/</span>}
            <button 
              className="breadcrumb-item"
              onClick={() => onNavigateTo(crumb.path)}
            >
              {crumb.name}
            </button>
          </span>
        ))}
      </div>

      {/* Error message */}
      {error && (
        <div className="file-explorer-error">
          ⚠️ {error}
        </div>
      )}

      {/* New folder dialog */}
      {showNewFolderDialog && (
        <div className="new-folder-dialog">
          <input
            type="text"
            placeholder="Folder name..."
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleCreateFolder()}
            autoFocus
          />
          <button onClick={handleCreateFolder}>Create</button>
          <button onClick={() => setShowNewFolderDialog(false)}>Cancel</button>
        </div>
      )}

      {/* File list */}
      <div className="file-list">
        {isLoading ? (
          <div className="file-list-loading">Loading...</div>
        ) : files.length === 0 ? (
          <div className="file-list-empty">
            <p>📂 This folder is empty</p>
            <p className="hint">Upload files or create a folder to get started</p>
          </div>
        ) : (
          files.map((file) => (
            <div
              key={file.id}
              className={`file-item ${selectedFiles.includes(file.id) ? 'selected' : ''} ${dragOverId === file.id ? 'drag-over' : ''}`}
              onClick={(e) => handleFileClick(file, e)}
              onDoubleClick={() => handleDoubleClick(file)}
              draggable
              onDragStart={(e) => handleDragStart(e, file)}
              onDragOver={(e) => handleDragOver(e, file)}
              onDragLeave={handleDragLeave}
              onDrop={(e) => handleDrop(e, file)}
            >
              <span className="file-icon">{getFileIcon(file)}</span>
              <span className="file-name">{file.name}</span>
              <span className="file-size">{formatSize(file.size)}</span>
              <div className="file-actions">
                {file.type === 'file' && (
                  <button 
                    className="file-action-btn"
                    onClick={(e) => { e.stopPropagation(); onDownloadFile(file); }}
                    title="Download"
                  >
                    ⬇️
                  </button>
                )}
                <button 
                  className="file-action-btn danger"
                  onClick={(e) => { e.stopPropagation(); onDeleteFile(file.id, file.path); }}
                  title="Delete"
                >
                  🗑️
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
