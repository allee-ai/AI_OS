import { useEffect, useState, useRef, useCallback } from 'react';
import { Link } from 'react-router-dom';
import './DocsPage.css';

interface DocNode {
  name: string;
  path: string;
  is_folder: boolean;
  children?: DocNode[];
  size?: number;
}

export const DocsPage = () => {
  const [tree, setTree] = useState<DocNode | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [contentLoading, setContentLoading] = useState(false);
  const [openFolders, setOpenFolders] = useState<Record<string, boolean>>({});
  
  // Resizable sidebar
  const [sidebarWidth, setSidebarWidth] = useState(() => {
    const saved = localStorage.getItem('docs-sidebar-width');
    return saved ? parseInt(saved, 10) : 280;
  });
  const [isResizing, setIsResizing] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);

  const startResizing = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing || !sidebarRef.current) return;
      const newWidth = Math.max(180, Math.min(500, e.clientX - sidebarRef.current.getBoundingClientRect().left));
      setSidebarWidth(newWidth);
      localStorage.setItem('docs-sidebar-width', String(newWidth));
    };
    const handleMouseUp = () => setIsResizing(false);

    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing]);

  useEffect(() => {
    fetch('http://localhost:8000/api/docs')
      .then(res => res.json())
      .then(data => {
        setTree(data.tree || null);
        setLoading(false);
        // Auto-expand root folder
        if (data.tree) {
          setOpenFolders({ '': true });
        }
        // Auto-select root README if exists
        const rootReadme = (data.tree?.children || []).find(
          (ch: DocNode) => !ch.is_folder && ch.name.toLowerCase() === 'readme.md'
        );
        if (rootReadme) loadDoc(rootReadme.path);
      })
      .catch(() => setLoading(false));
  }, []);

  const loadDoc = (path: string) => {
    setSelectedDoc(path);
    setContentLoading(true);
    fetch(`http://localhost:8000/api/docs/content?path=${encodeURIComponent(path)}`)
      .then(res => res.json())
      .then(data => {
        setContent(data.content || '');
        setContentLoading(false);
      })
      .catch(() => {
        setContent('Error loading document');
        setContentLoading(false);
      });
  };

  // Resolve relative paths based on current document
  const resolveDocPath = (href: string, currentDoc: string | null): string | null => {
    if (!currentDoc) return null;
    
    // External links - not a doc path
    if (href.startsWith('http://') || href.startsWith('https://')) return null;
    
    // Anchor links - not a doc path
    if (href.startsWith('#')) return null;
    
    // Get the directory of the current doc (empty string if at root)
    const lastSlash = currentDoc.lastIndexOf('/');
    const currentDir = lastSlash >= 0 ? currentDoc.substring(0, lastSlash) : '';
    
    let resolved: string;
    
    // Handle relative paths
    if (href.startsWith('./')) {
      // Same directory: ./file.md
      const fileName = href.slice(2);
      resolved = currentDir ? `${currentDir}/${fileName}` : fileName;
    } else if (href.startsWith('../')) {
      // Parent directory: ../file.md or ../../folder/file.md
      let targetPath = href;
      let baseDir = currentDir;
      while (targetPath.startsWith('../')) {
        targetPath = targetPath.slice(3);
        const lastSlashInBase = baseDir.lastIndexOf('/');
        baseDir = lastSlashInBase >= 0 ? baseDir.substring(0, lastSlashInBase) : '';
      }
      resolved = baseDir ? `${baseDir}/${targetPath}` : targetPath;
    } else if (!href.startsWith('/')) {
      // Relative path without ./ prefix (same as ./)
      resolved = currentDir ? `${currentDir}/${href}` : href;
    } else {
      // Absolute path from root
      resolved = href.startsWith('/') ? href.slice(1) : href;
    }
    
    // Clean up any double slashes
    resolved = resolved.replace(/\/+/g, '/');
    
    // Remove leading slash if present
    if (resolved.startsWith('/')) {
      resolved = resolved.slice(1);
    }
    
    return resolved;
  };

  // Handle clicks on the markdown content to intercept doc links
  const handleContentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;
    if (target.tagName === 'A') {
      const href = target.getAttribute('href');
      if (href && !href.startsWith('http://') && !href.startsWith('https://') && !href.startsWith('#')) {
        e.preventDefault();
        const resolvedPath = resolveDocPath(href, selectedDoc);
        console.log('Doc link clicked:', { href, selectedDoc, resolvedPath });
        if (resolvedPath) {
          loadDoc(resolvedPath);
        }
      }
    }
  };

  // Simple markdown to HTML (basic support)
  const renderMarkdown = (md: string) => {
    let html = md
      // Code blocks
      .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
      // Inline code
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      // Headers
      .replace(/^### (.+)$/gm, '<h3>$1</h3>')
      .replace(/^## (.+)$/gm, '<h2>$1</h2>')
      .replace(/^# (.+)$/gm, '<h1>$1</h1>')
      // Bold
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      // Italic
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      // Links - external get target="_blank", internal don't
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, text, href) => {
        if (href.startsWith('http://') || href.startsWith('https://')) {
          return `<a href="${href}" target="_blank" rel="noopener">${text}</a>`;
        }
        return `<a href="${href}" class="doc-link">${text}</a>`;
      })
      // Lists
      .replace(/^- (.+)$/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
      // Paragraphs
      .replace(/\n\n/g, '</p><p>')
      // Line breaks
      .replace(/\n/g, '<br/>');
    
    return `<p>${html}</p>`;
  };

  const getFileName = (path: string) => {
    return path.split('/').pop() || path;
  };

  const toggleFolder = (path: string) => {
    setOpenFolders(prev => ({ ...prev, [path]: !prev[path] }));
  };

  // Sort children so README.md comes first, then folders, then other files
  const sortChildren = (children: DocNode[]): DocNode[] => {
    return [...children].sort((a, b) => {
      const aIsReadme = a.name.toLowerCase() === 'readme.md';
      const bIsReadme = b.name.toLowerCase() === 'readme.md';
      if (aIsReadme && !bIsReadme) return -1;
      if (!aIsReadme && bIsReadme) return 1;
      if (a.is_folder && !b.is_folder) return -1;
      if (!a.is_folder && b.is_folder) return 1;
      return a.name.localeCompare(b.name);
    });
  };

  const renderTreeNode = (node: DocNode, depth = 0) => {
    const indent = { paddingLeft: `${depth * 16}px` };

    if (node.is_folder) {
      const isOpen = !!openFolders[node.path];
      const folderIcon = isOpen ? '📂' : '📁';
      const sortedChildren = sortChildren(node.children || []);
      return (
        <div key={node.path || '_root'} className="tree-node folder">
          <button
            className={`doc-item folder ${isOpen ? 'open' : ''}`}
            onClick={() => toggleFolder(node.path)}
            style={indent}
          >
            <span className="doc-icon">{folderIcon}</span>
            <span className="doc-name">{node.name}</span>
            <span className="doc-count">{countFilesInNode(node)}</span>
          </button>
          {isOpen && (
            <div className="folder-children">
              {sortedChildren.map(ch => renderTreeNode(ch, depth + 1))}
            </div>
          )}
        </div>
      );
    }

    const isReadme = node.name.toLowerCase() === 'readme.md';
    return (
      <button
        key={node.path}
        className={`doc-item file ${selectedDoc === node.path ? 'active' : ''} ${isReadme ? 'readme' : ''}`}
        style={indent}
        onClick={() => loadDoc(node.path)}
      >
        <span className="doc-icon">{isReadme ? '📖' : '📄'}</span>
        <span className="doc-name">{node.name}</span>
      </button>
    );
  };

  const countFilesInNode = (node: DocNode): number => {
    if (!node.is_folder) return 1;
    return (node.children || []).reduce((acc, ch) => acc + countFilesInNode(ch), 0);
  };

  return (
    <div className="page-wrapper docs-page">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>📖 Documentation</h1>
      </div>

      <div className="docs-layout">
        <nav 
          ref={sidebarRef}
          className={`docs-nav ${isResizing ? 'resizing' : ''}`}
          style={{ width: sidebarWidth }}
        >
          <div className="docs-nav-header">📁 AI_OS ({tree ? countFilesInNode(tree) : 0} docs)</div>
          {loading ? (
            <div className="muted">Loading...</div>
          ) : !tree ? (
            <div className="muted">No docs found</div>
          ) : (
            <div className="docs-tree">
              {/* Render root children directly (root is always expanded) */}
              {sortChildren(tree.children || []).map(ch => renderTreeNode(ch, 0))}
            </div>
          )}
          <div className="docs-nav-resize" onMouseDown={startResizing} />
        </nav>

        <main className="docs-content">
          {!selectedDoc ? (
            <div className="empty-state">Select a document to view</div>
          ) : contentLoading ? (
            <div className="empty-state">Loading...</div>
          ) : (
            <article className="markdown-body">
              <div className="doc-title">{getFileName(selectedDoc)}</div>
              <div className="doc-path">{selectedDoc}</div>
              <div 
                onClick={handleContentClick}
                dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }} 
              />
            </article>
          )}
        </main>
      </div>
    </div>
  );
};
