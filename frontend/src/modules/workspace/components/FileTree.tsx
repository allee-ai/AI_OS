import React, { useState, useCallback, useEffect, useRef } from 'react';
import type { WorkspaceFile } from '../types/workspace';
import { workspaceApi } from '../services/workspaceApi';
import './FileTree.css';

interface FileTreeProps {
  onOpenFile: (file: WorkspaceFile) => void;
  activeFilePath?: string | null;
  onNavigateTo?: (path: string) => void;
}

interface TreeNode {
  file: WorkspaceFile;
  children: TreeNode[] | null;  // null = not loaded yet
  expanded: boolean;
  loading: boolean;
}

// ── Icon helpers ────────────────────────────────────────────────────

function getFileIcon(name: string, isFolder: boolean, expanded: boolean): string {
  if (isFolder) return expanded ? '📂' : '📁';
  const ext = name.split('.').pop()?.toLowerCase() || '';
  const map: Record<string, string> = {
    py: '🐍', js: '⚡', ts: '💠', jsx: '⚛️', tsx: '⚛️',
    json: '{ }', yaml: '📋', yml: '📋', toml: '⚙️',
    md: '📑', txt: '📃', csv: '📊',
    html: '🌐', css: '🎨', svg: '🖼️',
    pdf: '📄', doc: '📝', docx: '📝',
    sh: '🔧', sql: '🗄️',
    png: '🖼️', jpg: '🖼️', jpeg: '🖼️', gif: '🖼️',
    zip: '📦', tar: '📦', gz: '📦',
  };
  return map[ext] || '📄';
}

// ── Single tree row ─────────────────────────────────────────────────

interface TreeItemProps {
  node: TreeNode;
  depth: number;
  activeFilePath?: string | null;
  onToggle: (path: string) => void;
  onSelect: (file: WorkspaceFile) => void;
  onRename: (oldPath: string, newName: string) => void;
  onDelete: (path: string, isFolder: boolean) => void;
  renamingPath: string | null;
  setRenamingPath: (path: string | null) => void;
}

const TreeItem: React.FC<TreeItemProps> = ({
  node, depth, activeFilePath, onToggle, onSelect,
  onRename, onDelete, renamingPath, setRenamingPath,
}) => {
  const { file, children, expanded, loading } = node;
  const isFolder = file.type === 'folder';
  const isActive = activeFilePath === file.path;
  const isRenaming = renamingPath === file.path;
  const inputRef = useRef<HTMLInputElement>(null);
  const [renameValue, setRenameValue] = useState(file.name);
  const [showCtx, setShowCtx] = useState(false);
  const [ctxPos, setCtxPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus();
      const dot = file.name.lastIndexOf('.');
      inputRef.current.setSelectionRange(0, dot > 0 ? dot : file.name.length);
    }
  }, [isRenaming, file.name]);

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isFolder) {
      onToggle(file.path);
    } else {
      onSelect(file);
    }
  };

  const handleContext = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowCtx(true);
    setCtxPos({ x: e.clientX, y: e.clientY });
  };

  const commitRename = () => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== file.name) {
      onRename(file.path, trimmed);
    }
    setRenamingPath(null);
  };

  const cancelRename = () => {
    setRenameValue(file.name);
    setRenamingPath(null);
  };

  // Close context menu on outside click
  useEffect(() => {
    if (!showCtx) return;
    const close = () => setShowCtx(false);
    window.addEventListener('click', close);
    return () => window.removeEventListener('click', close);
  }, [showCtx]);

  return (
    <>
      <div
        className={`tree-item ${isActive ? 'active' : ''} ${isFolder ? 'folder' : ''}`}
        style={{ paddingLeft: depth * 16 + 8 }}
        onClick={handleClick}
        onContextMenu={handleContext}
        title={file.path}
      >
        {isFolder ? (
          <span className={`tree-chevron ${expanded ? 'expanded' : ''}`}>
            {loading ? '⏳' : '▶'}
          </span>
        ) : (
          <span className="tree-chevron spacer" />
        )}
        <span className="tree-icon">{getFileIcon(file.name, isFolder, expanded)}</span>
        {isRenaming ? (
          <input
            ref={inputRef}
            className="tree-rename-input"
            value={renameValue}
            onChange={e => setRenameValue(e.target.value)}
            onBlur={commitRename}
            onKeyDown={e => {
              if (e.key === 'Enter') commitRename();
              if (e.key === 'Escape') cancelRename();
            }}
            onClick={e => e.stopPropagation()}
          />
        ) : (
          <span className="tree-label">{file.name}</span>
        )}
      </div>

      {/* Context menu */}
      {showCtx && (
        <div className="tree-context-menu" style={{ top: ctxPos.y, left: ctxPos.x }}>
          <button onClick={() => { setRenamingPath(file.path); setRenameValue(file.name); setShowCtx(false); }}>
            Rename
          </button>
          <button onClick={() => { onDelete(file.path, isFolder); setShowCtx(false); }}>
            Delete
          </button>
        </div>
      )}

      {expanded && children && children.map(child => (
        <TreeItem
          key={child.file.path}
          node={child}
          depth={depth + 1}
          activeFilePath={activeFilePath}
          onToggle={onToggle}
          onSelect={onSelect}
          onRename={onRename}
          onDelete={onDelete}
          renamingPath={renamingPath}
          setRenamingPath={setRenamingPath}
        />
      ))}
    </>
  );
};

// ── File tree root ──────────────────────────────────────────────────

export const FileTree: React.FC<FileTreeProps> = ({ onOpenFile, activeFilePath }) => {
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [rootLoading, setRootLoading] = useState(true);
  const [renamingPath, setRenamingPath] = useState<string | null>(null);
  const [creatingIn, setCreatingIn] = useState<{ parentPath: string; type: 'file' | 'folder' } | null>(null);
  const [newName, setNewName] = useState('');
  const newInputRef = useRef<HTMLInputElement>(null);

  // Load root on mount
  useEffect(() => {
    loadChildren('/').then(children => {
      setNodes(children);
      setRootLoading(false);
    });
  }, []);

  const loadChildren = async (path: string): Promise<TreeNode[]> => {
    try {
      const files = await workspaceApi.listFiles(path);
      // Sort: folders first, then alphabetical
      files.sort((a, b) => {
        if (a.type !== b.type) return a.type === 'folder' ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      return files.map(f => ({
        file: f,
        children: f.type === 'folder' ? null : [],
        expanded: false,
        loading: false,
      }));
    } catch {
      return [];
    }
  };

  // Recursively update a node at a given path
  const updateNodeAtPath = useCallback((
    nodeList: TreeNode[],
    targetPath: string,
    updater: (node: TreeNode) => TreeNode
  ): TreeNode[] => {
    return nodeList.map(n => {
      if (n.file.path === targetPath) return updater(n);
      if (n.children && targetPath.startsWith(n.file.path + '/')) {
        return { ...n, children: updateNodeAtPath(n.children, targetPath, updater) };
      }
      return n;
    });
  }, []);

  const handleToggle = useCallback(async (path: string) => {
    // Find current state
    const findNode = (list: TreeNode[]): TreeNode | null => {
      for (const n of list) {
        if (n.file.path === path) return n;
        if (n.children) {
          const found = findNode(n.children);
          if (found) return found;
        }
      }
      return null;
    };

    const node = findNode(nodes);
    if (!node) return;

    if (node.expanded) {
      // Collapse
      setNodes(prev => updateNodeAtPath(prev, path, n => ({ ...n, expanded: false })));
    } else if (node.children !== null && node.children.length > 0) {
      // Already loaded — just expand
      setNodes(prev => updateNodeAtPath(prev, path, n => ({ ...n, expanded: true })));
    } else {
      // Need to load children
      setNodes(prev => updateNodeAtPath(prev, path, n => ({ ...n, loading: true, expanded: true })));
      const children = await loadChildren(path);
      setNodes(prev => updateNodeAtPath(prev, path, n => ({ ...n, children, loading: false })));
    }
  }, [nodes, updateNodeAtPath]);

  const handleSelect = useCallback((file: WorkspaceFile) => {
    onOpenFile(file);
  }, [onOpenFile]);

  // Refresh tree (called after file operations)
  const refresh = useCallback(async () => {
    setRootLoading(true);
    const children = await loadChildren('/');
    setNodes(children);
    setRootLoading(false);
  }, []);

  // Rename handler
  const handleRename = useCallback(async (oldPath: string, newName: string) => {
    const parentPath = oldPath.substring(0, oldPath.lastIndexOf('/')) || '/';
    const newPath = parentPath === '/' ? `/${newName}` : `${parentPath}/${newName}`;
    try {
      await workspaceApi.renameFile(oldPath, newPath);
      await refresh();
    } catch (e: any) {
      console.error('Rename failed:', e);
    }
  }, [refresh]);

  // Delete handler
  const handleDelete = useCallback(async (path: string, isFolder: boolean) => {
    const label = isFolder ? 'folder' : 'file';
    if (!window.confirm(`Delete ${label} "${path.split('/').pop()}"?`)) return;
    try {
      await workspaceApi.deleteFile(path, path);
      await refresh();
    } catch (e: any) {
      console.error('Delete failed:', e);
    }
  }, [refresh]);

  // New file / new folder
  const startCreate = useCallback((type: 'file' | 'folder') => {
    setCreatingIn({ parentPath: '/', type });
    setNewName(type === 'file' ? 'untitled.txt' : 'new-folder');
    setTimeout(() => newInputRef.current?.focus(), 50);
  }, []);

  const commitCreate = useCallback(async () => {
    if (!creatingIn || !newName.trim()) { setCreatingIn(null); return; }
    const fullPath = creatingIn.parentPath === '/'
      ? `/${newName.trim()}`
      : `${creatingIn.parentPath}/${newName.trim()}`;
    try {
      if (creatingIn.type === 'folder') {
        await workspaceApi.createFolder({ name: newName.trim(), parentPath: creatingIn.parentPath });
      } else {
        await workspaceApi.createFile(fullPath, '');
      }
      await refresh();
    } catch (e: any) {
      console.error('Create failed:', e);
    }
    setCreatingIn(null);
    setNewName('');
  }, [creatingIn, newName, refresh]);

  // Focus new-name input when creating
  useEffect(() => {
    if (creatingIn && newInputRef.current) {
      newInputRef.current.focus();
      const dot = newName.lastIndexOf('.');
      newInputRef.current.setSelectionRange(0, dot > 0 ? dot : newName.length);
    }
  }, [creatingIn, newName]);

  return (
    <div className="file-tree">
      <div className="file-tree-header">
        <span className="file-tree-title">EXPLORER</span>
        <div className="file-tree-actions">
          <button className="file-tree-action" onClick={() => startCreate('file')} title="New File">+</button>
          <button className="file-tree-action" onClick={() => startCreate('folder')} title="New Folder">📁+</button>
          <button className="file-tree-action" onClick={refresh} title="Refresh">⟳</button>
        </div>
      </div>
      <div className="file-tree-content">
        {/* Inline new-item input */}
        {creatingIn && (
          <div className="tree-item creating" style={{ paddingLeft: 8 }}>
            <span className="tree-icon">{creatingIn.type === 'folder' ? '📁' : '📄'}</span>
            <input
              ref={newInputRef}
              className="tree-rename-input"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onBlur={commitCreate}
              onKeyDown={e => {
                if (e.key === 'Enter') commitCreate();
                if (e.key === 'Escape') { setCreatingIn(null); setNewName(''); }
              }}
            />
          </div>
        )}
        {rootLoading ? (
          <div className="file-tree-loading">Loading...</div>
        ) : nodes.length === 0 && !creatingIn ? (
          <div className="file-tree-empty">No files — click + to create one</div>
        ) : (
          nodes.map(node => (
            <TreeItem
              key={node.file.path}
              node={node}
              depth={0}
              activeFilePath={activeFilePath}
              onToggle={handleToggle}
              onSelect={handleSelect}
              onRename={handleRename}
              onDelete={handleDelete}
              renamingPath={renamingPath}
              setRenamingPath={setRenamingPath}
            />
          ))
        )}
      </div>
    </div>
  );
};
