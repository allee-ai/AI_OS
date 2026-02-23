import React, { useState, useRef } from 'react';
import './ContactsImportModal.css';

interface ContactsImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete: () => void;
}

interface ContactPreview {
  id: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  organization: string | null;
}

interface ParsedPreview {
  upload_id: string;
  total_contacts: number;
  contacts: ContactPreview[];
}

type ImportSource = 'google' | 'icloud' | 'outlook' | 'other';
type Step = 'source' | 'instructions' | 'upload' | 'preview' | 'importing' | 'complete';

const SOURCE_INSTRUCTIONS: Record<ImportSource, { title: string; steps: string[] }> = {
  google: {
    title: 'Export from Google Contacts',
    steps: [
      'Go to contacts.google.com',
      'Click "Export" in the left sidebar (or ⋮ menu → Export)',
      'Select "vCard (for iOS Contacts)" format',
      'Click "Export" to download the .vcf file',
    ]
  },
  icloud: {
    title: 'Export from iCloud',
    steps: [
      'Go to icloud.com/contacts',
      'Select the contacts you want (or ⌘+A for all)',
      'Click the gear icon ⚙️ → "Export vCard"',
      'Save the .vcf file',
    ]
  },
  outlook: {
    title: 'Export from Outlook',
    steps: [
      'Open Outlook and go to People/Contacts',
      'Select contacts to export',
      'File → Import/Export → Export to vCard',
      'Save the .vcf file',
    ]
  },
  other: {
    title: 'Export as vCard',
    steps: [
      'Open your contacts app',
      'Look for "Export" or "Share" option',
      'Choose "vCard" or ".vcf" format',
      'Save or share the file',
    ]
  }
};

export const ContactsImportModal: React.FC<ContactsImportModalProps> = ({
  isOpen,
  onClose,
  onImportComplete
}) => {
  const [step, setStep] = useState<Step>('source');
  const [selectedSource, setSelectedSource] = useState<ImportSource | null>(null);
  const [uploadId, setUploadId] = useState<string | null>(null);
  const [preview, setPreview] = useState<ParsedPreview | null>(null);
  const [selectedContacts, setSelectedContacts] = useState<Set<string>>(new Set());
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number; failed: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const resetModal = () => {
    setStep('source');
    setSelectedSource(null);
    setUploadId(null);
    setPreview(null);
    setSelectedContacts(new Set());
    setIsDragging(false);
    setUploadProgress(0);
    setError(null);
    setImportResult(null);
  };

  const handleClose = () => {
    resetModal();
    onClose();
  };

  const handleSourceSelect = (source: ImportSource) => {
    setSelectedSource(source);
    setStep('instructions');
  };

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

    const files = Array.from(e.dataTransfer.files);
    const vcfFile = files.find(f => f.name.endsWith('.vcf'));
    if (vcfFile) {
      await handleFileUpload(vcfFile);
    } else {
      setError('Please drop a .vcf file');
    }
  };

  const handleFileUpload = async (file: File) => {
    setError(null);
    setStep('importing');
    setUploadProgress(10);

    try {
      // Upload file
      const formData = new FormData();
      formData.append('file', file);

      setUploadProgress(30);

      const uploadResponse = await fetch('/api/identity/import/upload', {
        method: 'POST',
        body: formData
      });

      if (!uploadResponse.ok) {
        const err = await uploadResponse.json();
        throw new Error(err.detail || 'Upload failed');
      }

      const uploadData = await uploadResponse.json();
      setUploadId(uploadData.upload_id);
      setUploadProgress(60);

      // Parse and preview
      const parseResponse = await fetch(`/api/identity/import/parse?upload_id=${uploadData.upload_id}`, {
        method: 'POST'
      });

      if (!parseResponse.ok) {
        const err = await parseResponse.json();
        throw new Error(err.detail || 'Parse failed');
      }

      const previewData = await parseResponse.json();
      setPreview(previewData);
      
      // Select all by default
      const allIds = new Set<string>(previewData.contacts.map((c: ContactPreview) => c.id));
      setSelectedContacts(allIds);
      
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

  const toggleContact = (id: string) => {
    const newSelected = new Set(selectedContacts);
    if (newSelected.has(id)) {
      newSelected.delete(id);
    } else {
      newSelected.add(id);
    }
    setSelectedContacts(newSelected);
  };

  const toggleAllContacts = () => {
    if (!preview) return;
    if (selectedContacts.size === preview.contacts.length) {
      setSelectedContacts(new Set());
    } else {
      setSelectedContacts(new Set(preview.contacts.map(c => c.id)));
    }
  };

  const handleCommitImport = async () => {
    if (!uploadId) return;

    setStep('importing');
    setUploadProgress(0);
    setError(null);

    try {
      setUploadProgress(50);

      const response = await fetch('/api/identity/import/commit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          upload_id: uploadId,
          selected_ids: selectedContacts.size < (preview?.total_contacts || 0) 
            ? Array.from(selectedContacts) 
            : null,
          skip_existing: true
        })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Import failed');
      }

      const result = await response.json();
      setImportResult(result);
      setUploadProgress(100);
      setStep('complete');

      // Notify parent after delay
      setTimeout(() => {
        onImportComplete();
      }, 1500);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
      setStep('preview');
    }
  };

  // Render steps
  const renderSourceStep = () => (
    <div className="import-step">
      <h3>Import Contacts</h3>
      <p className="step-description">Where are your contacts?</p>
      
      <div className="source-grid">
        <button className="source-option" onClick={() => handleSourceSelect('google')}>
          <span className="source-icon">📧</span>
          <span className="source-name">Google Contacts</span>
        </button>
        <button className="source-option" onClick={() => handleSourceSelect('icloud')}>
          <span className="source-icon">☁️</span>
          <span className="source-name">iCloud</span>
        </button>
        <button className="source-option" onClick={() => handleSourceSelect('outlook')}>
          <span className="source-icon">📬</span>
          <span className="source-name">Outlook</span>
        </button>
        <button className="source-option" onClick={() => handleSourceSelect('other')}>
          <span className="source-icon">📁</span>
          <span className="source-name">Other / vCard File</span>
        </button>
      </div>
    </div>
  );

  const renderInstructionsStep = () => {
    if (!selectedSource) return null;
    const instructions = SOURCE_INSTRUCTIONS[selectedSource];
    
    return (
      <div className="import-step">
        <h3>{instructions.title}</h3>
        
        <ol className="export-steps">
          {instructions.steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>

        <div className="instructions-actions">
          <button className="btn-secondary" onClick={() => setStep('source')}>
            ← Back
          </button>
          <button className="btn-primary" onClick={() => setStep('upload')}>
            I have my .vcf file →
          </button>
        </div>
      </div>
    );
  };

  const renderUploadStep = () => (
    <div className="import-step">
      <h3>Upload Contacts File</h3>

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
        <p>Drag & drop your .vcf file or click to browse</p>
        <span className="hint">vCard files from any contacts app</span>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".vcf"
        onChange={handleFileSelect}
        style={{ display: 'none' }}
      />

      <div className="upload-actions">
        <button className="btn-secondary" onClick={() => setStep('instructions')}>
          ← Back
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}
    </div>
  );

  const renderPreviewStep = () => (
    <div className="import-step">
      <h3>Preview Contacts</h3>
      
      {preview && (
        <div className="import-preview">
          <div className="preview-stats">
            <div className="stat">
              <strong>{preview.total_contacts}</strong>
              <span>Contacts Found</span>
            </div>
            <div className="stat">
              <strong>{selectedContacts.size}</strong>
              <span>Selected</span>
            </div>
          </div>

          <div className="contact-list">
            <div className="contact-list-header">
              <label>
                <input
                  type="checkbox"
                  checked={selectedContacts.size === preview.contacts.length}
                  onChange={toggleAllContacts}
                />
                Select All
              </label>
            </div>
            
            {preview.contacts.map(contact => (
              <div key={contact.id} className="contact-preview">
                <input
                  type="checkbox"
                  checked={selectedContacts.has(contact.id)}
                  onChange={() => toggleContact(contact.id)}
                />
                <div className="contact-info">
                  <span className="contact-name">{contact.full_name}</span>
                  <span className="contact-meta">
                    {contact.email || contact.phone || contact.organization || ''}
                  </span>
                </div>
              </div>
            ))}
            
            {preview.total_contacts > 20 && (
              <p className="more-contacts">...and {preview.total_contacts - 20} more</p>
            )}
          </div>

          <div className="preview-actions">
            <button className="btn-secondary" onClick={() => setStep('upload')}>
              ← Back
            </button>
            <button 
              className="btn-primary" 
              onClick={handleCommitImport}
              disabled={selectedContacts.size === 0}
            >
              Import {selectedContacts.size} Contacts
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
      <p>Please wait while we import your contacts</p>
    </div>
  );

  const renderCompleteStep = () => (
    <div className="import-step">
      <h3>Import Complete!</h3>
      <div className="success-icon">✓</div>
      {importResult && (
        <div className="import-summary">
          <p><strong>{importResult.imported}</strong> contacts imported</p>
          {importResult.skipped > 0 && <p>{importResult.skipped} skipped (already exist)</p>}
          {importResult.failed > 0 && <p>{importResult.failed} failed</p>}
        </div>
      )}
      <button className="btn-primary" onClick={handleClose}>Done</button>
    </div>
  );

  return (
    <div className="modal-overlay" onClick={handleClose}>
      <div className="modal-content contacts-import-modal" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={handleClose}>×</button>
        
        {step === 'source' && renderSourceStep()}
        {step === 'instructions' && renderInstructionsStep()}
        {step === 'upload' && renderUploadStep()}
        {step === 'preview' && renderPreviewStep()}
        {step === 'importing' && renderImportingStep()}
        {step === 'complete' && renderCompleteStep()}
      </div>
    </div>
  );
};

export default ContactsImportModal;
