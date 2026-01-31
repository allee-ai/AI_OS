import React, { useState, useRef } from 'react';
import './ImportModal.css';

interface ImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

interface ParsedPreview {
  platform: string;
  total_conversations: number;
  conversations: Array<{
    id: string;
    title: string;
    message_count: number;
    created_at: string;
    has_attachments: boolean;
  }>;
}

export const ImportModal: React.FC<ImportModalProps> = ({
  isOpen,
  onClose,
  onImportComplete
}) => {
  const [step, setStep] = useState<'upload' | 'preview' | 'importing' | 'complete'>('upload');
  const [selectedPlatform, setSelectedPlatform] = useState<string>('auto');
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [preview, setPreview] = useState<ParsedPreview | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const items = Array.from(e.dataTransfer.items);
    
    // Check for folder drop
    for (const item of items) {
      if (item.kind === 'file') {
        const _entry = item.webkitGetAsEntry();
        if (_entry?.isDirectory) {
          await handleFolderUpload(_entry as FileSystemDirectoryEntry);
          return;
        }
      }
    }

    // Handle file drop
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      await handleFileUpload(files[0]);
    }
  };

  const handleFolderUpload = async (_entry: FileSystemDirectoryEntry) => {
    setError(null);
    setStep('importing');
    setUploadProgress(10);

    try {
      // Create zip from folder (browser API limitation workaround)
      // For now, ask user to zip the folder manually
      setError('Please zip your export folder and upload the .zip file instead');
      setStep('upload');
      setUploadProgress(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setStep('upload');
    }
  };

  const handleFileUpload = async (file: File) => {
    setError(null);
    setStep('importing');
    setUploadProgress(10);

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (selectedPlatform !== 'auto') {
        formData.append('platform', selectedPlatform);
      }

      setUploadProgress(30);

      const response = await fetch('http://localhost:8000/api/import/upload', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('Upload failed');

      const data = await response.json();
      setUploadId(data.upload_id);
      setUploadProgress(60);

      // Parse the export
      const parseFormData = new FormData();
      parseFormData.append('upload_id', data.upload_id);
      if (selectedPlatform !== 'auto') {
        parseFormData.append('platform', selectedPlatform);
      }

      const parseResponse = await fetch('http://localhost:8000/api/import/parse', {
        method: 'POST',
        body: parseFormData
      });

      if (!parseResponse.ok) throw new Error('Parse failed');

      const previewData = await parseResponse.json();
      setPreview(previewData);
      setUploadProgress(100);
      setStep('preview');

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setStep('upload');
      setUploadProgress(0);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleCommitImport = async () => {
    if (!uploadId) return;

    setStep('importing');
    setUploadProgress(0);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('upload_id', uploadId);
      if (selectedPlatform !== 'auto') {
        formData.append('platform', selectedPlatform);
      }
      formData.append('organize_by_project', 'true');

      setUploadProgress(50);

      const response = await fetch('http://localhost:8000/api/import/commit', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) throw new Error('Import failed');

      setUploadProgress(100);
      setStep('complete');
      
      // Notify parent and close after delay
      setTimeout(() => {
        onImportComplete();
        onClose();
      }, 2000);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
      setStep('preview');
    }
  };

  const renderUploadStep = () => (
    <div className="import-step">
      <h3>Import Conversations</h3>
      
      <div className="platform-selector">
        <label>Platform:</label>
        <select value={selectedPlatform} onChange={(e) => setSelectedPlatform(e.target.value)}>
          <option value="auto">Auto-detect</option>
          <option value="chatgpt">ChatGPT</option>
          <option value="claude">Claude</option>
          <option value="gemini">Gemini</option>
          <option value="vscode-copilot">VS Code Copilot</option>
        </select>
      </div>

      <div
        className={`drop-zone ${isDragging ? 'dragging' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
      >
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
          <path d="M21 15V19C21 19.5304 20.7893 20.0391 20.4142 20.4142C20.0391 20.7893 19.5304 21 19 21H5C4.46957 21 3.96086 20.7893 3.58579 20.4142C3.21071 20.0391 3 19.5304 3 19V15" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M7 10L12 15L17 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          <path d="M12 15V3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <p>Drag & drop your export folder (zipped) or click to browse</p>
        <span className="hint">Supports ChatGPT, Claude, Gemini, and VS Code Copilot exports</span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".zip,.json,.html,.md"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />

      {error && <div className="error-message">{error}</div>}
    </div>
  );

  const renderPreviewStep = () => (
    <div className="import-step">
      <h3>Preview Import</h3>
      
      {preview && (
        <div className="import-preview">
          <div className="preview-stats">
            <div className="stat">
              <strong>{preview.platform}</strong>
              <span>Platform</span>
            </div>
            <div className="stat">
              <strong>{preview.total_conversations}</strong>
              <span>Conversations</span>
            </div>
          </div>

          <div className="conversation-list">
            <h4>Conversations to import:</h4>
            {preview.conversations.map(conv => (
              <div key={conv.id} className="conversation-preview">
                <div className="conv-info">
                  <span className="conv-title">{conv.title}</span>
                  <span className="conv-meta">{conv.message_count} messages</span>
                </div>
                {conv.has_attachments && (
                  <span className="attachment-badge">📎</span>
                )}
              </div>
            ))}
            {preview.total_conversations > 10 && (
              <p className="more-convs">...and {preview.total_conversations - 10} more</p>
            )}
          </div>

          <div className="preview-actions">
            <button className="btn-secondary" onClick={() => setStep('upload')}>
              Cancel
            </button>
            <button className="btn-primary" onClick={handleCommitImport}>
              Import {preview.total_conversations} Conversations
            </button>
          </div>
        </div>
      )}

      {error && <div className="error-message">{error}</div>}
    </div>
  );

  const renderImportingStep = () => (
    <div className="import-step">
      <h3>Importing...</h3>
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${uploadProgress}%` }}></div>
      </div>
      <p>Please wait while we import your conversations</p>
    </div>
  );

  const renderCompleteStep = () => (
    <div className="import-step">
      <h3>Import Complete!</h3>
      <div className="success-icon">✓</div>
      <p>Your conversations have been imported successfully</p>
    </div>
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content import-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>×</button>
        
        {step === 'upload' && renderUploadStep()}
        {step === 'preview' && renderPreviewStep()}
        {step === 'importing' && renderImportingStep()}
        {step === 'complete' && renderCompleteStep()}
      </div>
    </div>
  );
};
