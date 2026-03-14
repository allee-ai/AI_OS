import React, { useEffect, useState } from 'react';
import type { FileMeta } from '../types/workspace';
import './FileViewer.css';

interface FileViewerProps {
  file: FileMeta | null;
  isLoading: boolean;
  onClose: () => void;
  onSummarize: (path: string) => Promise<string | null>;
  getImageUrl: (path: string) => Promise<string>;
  onSave?: (path: string, content: string) => Promise<boolean>;
  onPin?: (path: string, pinned: boolean) => Promise<void>;
}

/** Map mime/extension → language label for syntax display */
function getLanguage(file: FileMeta): string | null {
  const ext = file.name.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    py: 'python', js: 'javascript', ts: 'typescript',
    jsx: 'jsx', tsx: 'tsx', json: 'json',
    html: 'html', css: 'css', xml: 'xml',
    md: 'markdown', sh: 'shell', bash: 'shell',
    yaml: 'yaml', yml: 'yaml', toml: 'toml',
    sql: 'sql', rs: 'rust', go: 'go',
    java: 'java', c: 'c', cpp: 'cpp', h: 'c',
    rb: 'ruby', php: 'php', swift: 'swift',
  };
  return map[ext || ''] ?? null;
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  let i = 0;
  let size = bytes;
  while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
  return `${size.toFixed(1)} ${units[i]}`;
}

function formatDate(iso: string | null): string {
  if (!iso) return '-';
  const d = new Date(iso);
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/** Basic markdown-ish rendering: headings, bold, italic, code, links */
function renderSimpleMarkdown(text: string): React.ReactNode {
  const lines = text.split('\n');
  return lines.map((line, i) => {
    // Headings
    const hMatch = line.match(/^(#{1,3})\s+(.*)/);
    if (hMatch) {
      const level = hMatch[1].length;
      return React.createElement(`h${level + 1}`, { key: i, className: 'md-heading' }, hMatch[2]);
    }
    // Empty line → spacing
    if (!line.trim()) return <div key={i} className="md-spacer" />;
    // Otherwise paragraph
    return <p key={i} className="md-para">{line}</p>;
  });
}

export const FileViewer: React.FC<FileViewerProps> = ({
  file,
  isLoading,
  onClose,
  onSummarize,
  getImageUrl,
  onSave,
  onPin,
}) => {
  const [summarizing, setSummarizing] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [saving, setSaving] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(true);

  // Load image URL if file is an image
  useEffect(() => {
    if (file?.is_image) {
      let cancelled = false;
      getImageUrl(file.path).then(url => {
        if (!cancelled) setImageUrl(url);
      });
      return () => { cancelled = true; };
    } else {
      setImageUrl(null);
    }
  }, [file?.path, file?.is_image, getImageUrl]);

  // Load PDF blob URL for iframe rendering
  useEffect(() => {
    if (file?.is_pdf) {
      let cancelled = false;
      getImageUrl(file.path).then(url => {
        if (!cancelled) setPdfUrl(url);
      });
      return () => {
        cancelled = true;
        if (pdfUrl) URL.revokeObjectURL(pdfUrl);
      };
    } else {
      setPdfUrl(null);
    }
  }, [file?.path, file?.is_pdf, getImageUrl]);

  if (isLoading) {
    return (
      <div className="file-viewer">
        <div className="file-viewer-empty">
          <div className="viewer-spinner" />
          <p>Loading file...</p>
        </div>
      </div>
    );
  }

  if (!file) {
    return (
      <div className="file-viewer">
        <div className="file-viewer-empty">
          <span className="empty-icon">📄</span>
          <p>Select a file to preview</p>
          <p className="hint">Click any file in the explorer</p>
        </div>
      </div>
    );
  }

  const language = getLanguage(file);
  const isMarkdown = file.name.endsWith('.md');
  const isImage = !!file.is_image;
  const isPdf = !!file.is_pdf;
  const isDocx = !!file.is_docx;

  const handleSummarize = async () => {
    setSummarizing(true);
    await onSummarize(file.path);
    setSummarizing(false);
  };

  const isEditable = !!file.content && !isImage && !isPdf && !isDocx;

  const startEditing = () => {
    setEditContent(file.content || '');
    setEditing(true);
  };

  const cancelEditing = () => {
    setEditing(false);
    setEditContent('');
  };

  const handleSave = async () => {
    if (!onSave) return;
    setSaving(true);
    const ok = await onSave(file.path, editContent);
    setSaving(false);
    if (ok) setEditing(false);
  };

  return (
    <div className="file-viewer">
      {/* Header */}
      <div className="file-viewer-header">
        <div className="file-viewer-title">
          <span className="viewer-filename">{file.name}</span>
          <span className="viewer-path">{file.path}</span>
        </div>
        <div className="viewer-header-actions">
          {onPin && (
            <button className="viewer-pin" onClick={() => onPin(file.path, true)} title="Pin file">
              📌
            </button>
          )}
          {isEditable && !editing && (
            <button className="viewer-edit-btn" onClick={startEditing} title="Edit file">
              ✎
            </button>
          )}
          <button
            className={`viewer-summary-toggle ${summaryOpen ? 'active' : ''}`}
            onClick={() => setSummaryOpen(!summaryOpen)}
            title={summaryOpen ? 'Hide summary' : 'Show summary'}
          >
            📝
          </button>
          <button className="viewer-close" onClick={onClose} title="Close">×</button>
        </div>
      </div>

      {/* Meta bar */}
      <div className="file-viewer-meta">
        <span className="meta-item">{formatBytes(file.size)}</span>
        {file.mime_type && <span className="meta-item">{file.mime_type}</span>}
        {language && <span className="meta-item lang-badge">{language}</span>}
        <span className="meta-item">{formatDate(file.modified_at)}</span>
      </div>

      {/* Split: Content + Summary sidebar */}
      <div className="file-viewer-body">
        {/* Content */}
        <div className="file-viewer-content">
        {editing ? (
          <div className="edit-mode">
            <div className="edit-toolbar">
              <span className="edit-label">Editing — {file.name}</span>
              <div className="edit-actions">
                <button className="edit-cancel" onClick={cancelEditing}>Cancel</button>
                <button className="edit-save" onClick={handleSave} disabled={saving}>
                  {saving ? 'Saving...' : '💾 Save'}
                </button>
              </div>
            </div>
            <textarea
              className="edit-textarea"
              value={editContent}
              onChange={e => setEditContent(e.target.value)}
              spellCheck={false}
            />
          </div>
        ) : isImage && imageUrl ? (
          <div className="image-preview">
            <img src={imageUrl} alt={file.name} />
          </div>
        ) : isPdf && pdfUrl ? (
          <div className="pdf-preview">
            <iframe src={pdfUrl} title={file.name} />
          </div>
        ) : isDocx && file.content ? (
          <div className="docx-preview">
            <div className="docx-badge">DOCX &mdash; extracted text</div>
            {file.content.split('\n\n').map((para, i) => (
              <p key={i} className="docx-para">{para}</p>
            ))}
          </div>
        ) : isMarkdown && file.content ? (
          <div className="markdown-preview">
            {renderSimpleMarkdown(file.content)}
          </div>
        ) : file.content ? (
          <pre className={`code-preview ${language ? `lang-${language}` : ''}`}>
            <code>{file.content}</code>
          </pre>
        ) : (
          <div className="no-preview">
            <p>Preview not available for this file type</p>
            <p className="hint">{file.mime_type || 'Unknown type'}</p>
          </div>
        )}
        </div>

        {/* Summary sidebar */}
        <div className={`file-summary-sidebar ${summaryOpen ? 'open' : ''}`}>
          <div className="summary-sidebar-header">
            <span className="summary-label">Summary</span>
            <button
              className="summary-btn"
              onClick={handleSummarize}
              disabled={summarizing}
              title="Generate / regenerate summary"
            >
              {summarizing ? '⏳' : '✨'}
            </button>
          </div>
          <div className="summary-sidebar-body">
            {file.summary ? (
              <p className="summary-text">{file.summary}</p>
            ) : (
              <div className="summary-sidebar-empty">
                <span>📝</span>
                <p>No summary yet</p>
                <button
                  className="summary-generate-btn"
                  onClick={handleSummarize}
                  disabled={summarizing}
                >
                  {summarizing ? 'Summarizing...' : '✨ Summarize'}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
