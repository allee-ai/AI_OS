import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FileExplorer } from './FileExplorer';
import { FileViewer } from './FileViewer';
import { useWorkspace } from '../hooks/useWorkspace';
import './WorkspacePanel.css';

interface QuickFile {
  path: string;
  name: string;
  size?: number;
  modified_at?: string;
  mime_type?: string;
  summary?: string | null;
  pinned?: boolean;
}

interface WorkspaceStats {
  files: number;
  folders: number;
  total_size_bytes: number;
  chunks: number;
  indexed_files: number;
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0, size = bytes;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
  return `${size.toFixed(1)} ${units[i]}`;
}

export const WorkspacePanel: React.FC = () => {
  const workspace = useWorkspace();
  const [searchInput, setSearchInput] = useState('');
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [sidebarTab, setSidebarTab] = useState<'explorer' | 'recent' | 'pinned' | 'notes'>('explorer');
  const [recentFiles, setRecentFiles] = useState<QuickFile[]>([]);
  const [pinnedFiles, setPinnedFiles] = useState<QuickFile[]>([]);
  const [notes, setNotes] = useState<QuickFile[]>([]);
  const [showNewNote, setShowNewNote] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [stats, setStats] = useState<WorkspaceStats | null>(null);

  // Load workspace stats
  useEffect(() => {
    fetch('/api/workspace/stats')
      .then(r => r.ok ? r.json() : null)
      .then(d => d && setStats(d))
      .catch(() => {});
  }, []);

  // Fetch sidebar data on tab switch
  useEffect(() => {
    if (sidebarTab === 'recent') {
      workspace.getRecentFiles(20).then(setRecentFiles);
    } else if (sidebarTab === 'pinned') {
      workspace.getPinnedFiles().then(setPinnedFiles);
    } else if (sidebarTab === 'notes') {
      workspace.listNotes().then(setNotes);
    }
  }, [sidebarTab]);

  // Debounced search
  const handleSearchChange = useCallback((value: string) => {
    setSearchInput(value);
    if (searchTimer.current) clearTimeout(searchTimer.current);
    searchTimer.current = setTimeout(() => {
      workspace.searchFiles(value);
    }, 300);
  }, [workspace.searchFiles]);

  const openQuickFile = (f: QuickFile) => {
    workspace.handleOpenFile({
      id: f.path,
      name: f.name,
      path: f.path,
      type: 'file',
      createdAt: new Date(),
      updatedAt: new Date(f.modified_at || Date.now()),
    });
  };

  const handleCreateNote = async () => {
    if (!noteTitle.trim() && !noteContent.trim()) return;
    await workspace.createNote(noteTitle || '', noteContent || '');
    setNoteTitle('');
    setNoteContent('');
    setShowNewNote(false);
    workspace.listNotes().then(setNotes);
  };

  const formatDate = (iso?: string) => {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="workspace-panel-container">
      {/* ── Stats bar ── */}
      <div className="workspace-stats-bar">
        <div className="workspace-stats-left">
          <Link to="/" className="workspace-home-link" title="Back to Home">←</Link>
          <span className="workspace-title">📂 Workspace</span>
          {stats && (
            <div className="workspace-stat-chips">
              <span className="ws-chip">{stats.files} files</span>
              <span className="ws-chip">{stats.folders} folders</span>
              <span className="ws-chip">{formatBytes(stats.total_size_bytes)}</span>
              {stats.indexed_files > 0 && <span className="ws-chip ws-chip-good">{stats.indexed_files} indexed</span>}
              {stats.chunks > 0 && <span className="ws-chip ws-chip-accent">{stats.chunks} chunks</span>}
            </div>
          )}
        </div>
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
        {/* Left: Sidebar with tabs */}
        <div className="workspace-explorer-pane">
          <div className="ws-sidebar-tabs">
            <button className={sidebarTab === 'explorer' ? 'active' : ''} onClick={() => setSidebarTab('explorer')} title="Files">📁</button>
            <button className={sidebarTab === 'recent' ? 'active' : ''} onClick={() => setSidebarTab('recent')} title="Recent">🕐</button>
            <button className={sidebarTab === 'pinned' ? 'active' : ''} onClick={() => setSidebarTab('pinned')} title="Pinned">📌</button>
            <button className={sidebarTab === 'notes' ? 'active' : ''} onClick={() => setSidebarTab('notes')} title="Notes">📝</button>
          </div>

          {sidebarTab === 'explorer' && (
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
          )}

          {sidebarTab === 'recent' && (
            <div className="ws-quick-list">
              <div className="ws-quick-header">Recent Files</div>
              {recentFiles.length === 0 ? (
                <div className="ws-quick-empty">No recent files</div>
              ) : (
                recentFiles.map((f, i) => (
                  <div key={i} className="ws-quick-item" onClick={() => openQuickFile(f)}>
                    <span className="ws-quick-name">{f.name}</span>
                    <span className="ws-quick-meta">{formatDate(f.modified_at)}</span>
                    {f.summary && <span className="ws-quick-summary">{f.summary}</span>}
                  </div>
                ))
              )}
            </div>
          )}

          {sidebarTab === 'pinned' && (
            <div className="ws-quick-list">
              <div className="ws-quick-header">Pinned Files</div>
              {pinnedFiles.length === 0 ? (
                <div className="ws-quick-empty">No pinned files — click 📌 on a file to pin it</div>
              ) : (
                pinnedFiles.map((f, i) => (
                  <div key={i} className="ws-quick-item" onClick={() => openQuickFile(f)}>
                    <span className="ws-quick-name">📌 {f.name}</span>
                    <span className="ws-quick-meta">{f.path}</span>
                  </div>
                ))
              )}
            </div>
          )}

          {sidebarTab === 'notes' && (
            <div className="ws-quick-list">
              <div className="ws-quick-header">
                <span>Notes</span>
                <button className="ws-note-add" onClick={() => setShowNewNote(!showNewNote)}>+ New</button>
              </div>
              {showNewNote && (
                <div className="ws-new-note">
                  <input
                    className="ws-note-title-input"
                    placeholder="Note title..."
                    value={noteTitle}
                    onChange={e => setNoteTitle(e.target.value)}
                  />
                  <textarea
                    className="ws-note-content-input"
                    placeholder="Write something..."
                    value={noteContent}
                    onChange={e => setNoteContent(e.target.value)}
                    rows={4}
                  />
                  <div className="ws-note-actions">
                    <button className="ws-note-cancel" onClick={() => setShowNewNote(false)}>Cancel</button>
                    <button className="ws-note-save" onClick={handleCreateNote}>Save Note</button>
                  </div>
                </div>
              )}
              {notes.length === 0 && !showNewNote ? (
                <div className="ws-quick-empty">No notes yet — create one above</div>
              ) : (
                notes.map((f, i) => (
                  <div key={i} className="ws-quick-item" onClick={() => openQuickFile(f)}>
                    <span className="ws-quick-name">📝 {f.name}</span>
                    <span className="ws-quick-meta">{formatDate(f.modified_at)}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Right: File viewer */}
        <div className={`workspace-viewer-pane ${workspace.openFile || workspace.openFileLoading ? 'open' : ''}`}>
          <FileViewer
            file={workspace.openFile}
            isLoading={workspace.openFileLoading}
            onClose={workspace.closeFile}
            onSummarize={workspace.summarizeFile}
            getImageUrl={workspace.getImageUrl}
            onSave={workspace.editFile}
            onPin={workspace.pinFile}
          />
        </div>
      </div>
    </div>
  );
};
