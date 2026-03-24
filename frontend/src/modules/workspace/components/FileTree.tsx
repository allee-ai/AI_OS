import React, { useState, useCallback, useEffect } from 'react';
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
}

const TreeItem: React.FC<TreeItemProps> = ({ node, depth, activeFilePath, onToggle, onSelect }) => {
  const { file, children, expanded, loading } = node;
  const isFolder = file.type === 'folder';
  const isActive = activeFilePath === file.path;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isFolder) {
      onToggle(file.path);
    } else {
      onSelect(file);
    }
  };

  return (
    <>
      <div
        className={`tree-item ${isActive ? 'active' : ''} ${isFolder ? 'folder' : ''}`}
        style={{ paddingLeft: depth * 16 + 8 }}
        onClick={handleClick}
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
        <span className="tree-label">{file.name}</span>
      </div>
      {expanded && children && children.map(child => (
        <TreeItem
          key={child.file.path}
          node={child}
          depth={depth + 1}
          activeFilePath={activeFilePath}
          onToggle={onToggle}
          onSelect={onSelect}
        />
      ))}
    </>
  );
};

// ── File tree root ──────────────────────────────────────────────────

export const FileTree: React.FC<FileTreeProps> = ({ onOpenFile, activeFilePath }) => {
  const [nodes, setNodes] = useState<TreeNode[]>([]);
  const [rootLoading, setRootLoading] = useState(true);

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

  return (
    <div className="file-tree">
      <div className="file-tree-header">
        <span className="file-tree-title">EXPLORER</span>
        <button className="file-tree-refresh" onClick={refresh} title="Refresh">⟳</button>
      </div>
      <div className="file-tree-content">
        {rootLoading ? (
          <div className="file-tree-loading">Loading...</div>
        ) : nodes.length === 0 ? (
          <div className="file-tree-empty">No files</div>
        ) : (
          nodes.map(node => (
            <TreeItem
              key={node.file.path}
              node={node}
              depth={0}
              activeFilePath={activeFilePath}
              onToggle={handleToggle}
              onSelect={handleSelect}
            />
          ))
        )}
      </div>
    </div>
  );
};
