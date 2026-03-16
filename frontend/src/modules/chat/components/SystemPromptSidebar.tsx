import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/chatApi';
import { BASE_URL } from '../../../config/api';
import './SystemPromptSidebar.css';

const API_BASE = BASE_URL;

interface StateData {
  state: string;
  char_count: number;
  query?: string;
}

type SidebarTab = 'state' | 'summary' | 'prompts';

interface SystemPromptSidebarProps {
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  lastQuery?: string;
  sessionId?: string;
}

export const SystemPromptSidebar: React.FC<SystemPromptSidebarProps> = ({
  isCollapsed,
  onToggleCollapse,
  lastQuery,
  sessionId
}) => {
  const [activeTab, setActiveTab] = useState<SidebarTab>('state');
  const [data, setData] = useState<StateData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Summary state
  const [summary, setSummary] = useState<string | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);

  // Prompt editor state
  const [convoPrompt, setConvoPrompt] = useState('');
  const [filePrompt, setFilePrompt] = useState('');
  const [promptsLoading, setPromptsLoading] = useState(false);
  const [promptSaved, setPromptSaved] = useState<string | null>(null);

  const fetchState = async (query?: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = query ? `?query=${encodeURIComponent(query)}` : '';
      const response = await fetch(`${API_BASE}/api/subconscious/build_state${params}`);
      if (!response.ok) throw new Error('Failed to fetch');
      const result = await response.json();
      setData(result);
    } catch (err) {
      setError('Could not load state');
    } finally {
      setLoading(false);
    }
  };

  const fetchSummary = useCallback(async () => {
    if (!sessionId) { setSummary(null); return; }
    setSummaryLoading(true);
    try {
      const convo = await apiService.getConversation(sessionId);
      setSummary(convo.summary || null);
    } catch {
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [sessionId]);

  const handleSummarize = async () => {
    if (!sessionId) return;
    setSummaryLoading(true);
    try {
      const result = await apiService.summarizeConversation(sessionId);
      setSummary(result.summary);
    } catch (err) {
      console.error('Summarize failed:', err);
    } finally {
      setSummaryLoading(false);
    }
  };

  const fetchPrompts = async () => {
    setPromptsLoading(true);
    try {
      const [convo, file] = await Promise.all([
        apiService.getConvoSummaryPrompt(),
        apiService.getFileSummaryPrompt(),
      ]);
      setConvoPrompt(convo.prompt);
      setFilePrompt(file.prompt);
    } catch {
      // prompts may not be available yet
    } finally {
      setPromptsLoading(false);
    }
  };

  const savePrompt = async (type: 'convo' | 'file') => {
    try {
      if (type === 'convo') {
        await apiService.setConvoSummaryPrompt(convoPrompt);
      } else {
        await apiService.setFileSummaryPrompt(filePrompt);
      }
      setPromptSaved(type);
      setTimeout(() => setPromptSaved(null), 2000);
    } catch (err) {
      console.error('Failed to save prompt:', err);
    }
  };

  useEffect(() => {
    if (!isCollapsed && activeTab === 'state') {
      fetchState(lastQuery);
    }
  }, [isCollapsed, lastQuery, activeTab]);

  useEffect(() => {
    if (!isCollapsed && activeTab === 'summary') {
      fetchSummary();
    }
  }, [isCollapsed, activeTab, fetchSummary]);

  useEffect(() => {
    if (!isCollapsed && activeTab === 'prompts') {
      fetchPrompts();
    }
  }, [isCollapsed, activeTab]);

  // Poll state every 5 seconds when on state tab
  useEffect(() => {
    if (isCollapsed || activeTab !== 'state') return;
    const interval = setInterval(() => fetchState(lastQuery), 5000);
    return () => clearInterval(interval);
  }, [isCollapsed, activeTab, lastQuery]);

  if (isCollapsed) {
    return (
      <div className="system-prompt-sidebar collapsed">
        <button className="toggle-btn" onClick={onToggleCollapse} title="Show State">
          🧠
        </button>
      </div>
    );
  }

  return (
    <div className="system-prompt-sidebar">
      <div className="sidebar-header">
        <h3>{activeTab === 'state' ? 'State' : activeTab === 'summary' ? 'Summary' : 'Prompts'}</h3>
        <div className="header-actions">
          {activeTab === 'state' && (
            <button className="refresh-btn" onClick={() => fetchState()} title="Refresh">
              🔄
            </button>
          )}
          {activeTab === 'summary' && (
            <button className="refresh-btn" onClick={handleSummarize} disabled={summaryLoading || !sessionId} title="Generate summary">
              ✨
            </button>
          )}
          <button className="toggle-btn" onClick={onToggleCollapse} title="Hide">
            ✕
          </button>
        </div>
      </div>

      {/* Tab toggle */}
      <div className="sidebar-tabs">
        <button
          className={`sidebar-tab ${activeTab === 'state' ? 'active' : ''}`}
          onClick={() => setActiveTab('state')}
        >
          State
        </button>
        <button
          className={`sidebar-tab ${activeTab === 'summary' ? 'active' : ''}`}
          onClick={() => setActiveTab('summary')}
        >
          Summary
        </button>
        <button
          className={`sidebar-tab ${activeTab === 'prompts' ? 'active' : ''}`}
          onClick={() => setActiveTab('prompts')}
        >
          Prompts
        </button>
      </div>

      {/* STATE tab */}
      {activeTab === 'state' && (
        <>
          {loading && !data && <div className="loading">Loading...</div>}
          {error && <div className="error">{error}</div>}
          {data && (
            <div className="prompt-content">
              <div className="stats">
                <span className="stat">{data.char_count.toLocaleString()} chars</span>
              </div>
              <div className="prompt-text">
                <pre>{data.state}</pre>
              </div>
            </div>
          )}
        </>
      )}

      {/* SUMMARY tab */}
      {activeTab === 'summary' && (
        <div className="prompt-content">
          {summaryLoading ? (
            <div className="loading">{summary ? 'Regenerating...' : 'Loading...'}</div>
          ) : summary ? (
            <div className="summary-display">
              <p className="summary-body">{summary}</p>
              <button className="regenerate-btn" onClick={handleSummarize} disabled={!sessionId}>
                ✨ Regenerate
              </button>
            </div>
          ) : (
            <div className="summary-empty-state">
              <span className="empty-icon">📝</span>
              <p>{sessionId ? 'No summary yet for this conversation' : 'Select a conversation'}</p>
              {sessionId && (
                <button className="generate-btn" onClick={handleSummarize}>
                  ✨ Generate Summary
                </button>
              )}
            </div>
          )}
        </div>
      )}

      {/* PROMPTS tab */}
      {activeTab === 'prompts' && (
        <div className="prompt-content prompts-editor">
          {promptsLoading ? (
            <div className="loading">Loading prompts...</div>
          ) : (
            <>
              <div className="prompt-field">
                <label className="prompt-field-label">Conversation Summary Prompt</label>
                <textarea
                  className="prompt-textarea"
                  value={convoPrompt}
                  onChange={e => setConvoPrompt(e.target.value)}
                  rows={4}
                />
                <button className="save-prompt-btn" onClick={() => savePrompt('convo')}>
                  {promptSaved === 'convo' ? '✓ Saved' : 'Save'}
                </button>
              </div>
              <div className="prompt-field">
                <label className="prompt-field-label">File Summary Prompt</label>
                <textarea
                  className="prompt-textarea"
                  value={filePrompt}
                  onChange={e => setFilePrompt(e.target.value)}
                  rows={4}
                />
                <button className="save-prompt-btn" onClick={() => savePrompt('file')}>
                  {promptSaved === 'file' ? '✓ Saved' : 'Save'}
                </button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};
