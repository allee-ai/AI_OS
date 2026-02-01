import { useState, useEffect, useCallback } from 'react';
import ThemedSelect from './ThemedSelect';
import './ToolDashboard.css';

interface Tool {
  name: string;
  description: string;
  category: string;
  actions: string[];
  run_file: string;
  run_type: string;
  path: string | null;
  exists: boolean;
  requires_env: string[];
  weight: number;
  enabled: boolean;
  available: boolean;
  code?: string;
}

interface ExecuteResult {
  tool_name: string;
  action: string;
  status: string;
  output: unknown;
  error: string | null;
  duration_ms: number;
  timestamp: string;
  success: boolean;
}

interface Category {
  value: string;
  label: string;
  icon: string;
}

const API_BASE = 'http://localhost:8000';

const CATEGORY_ICONS: Record<string, string> = {
  communication: '📧',
  browser: '🌐',
  memory: '🧠',
  files: '📁',
  automation: '⚙️',
  internal: '🔧',
};

export const ToolDashboard = () => {
  const [tools, setTools] = useState<Tool[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const [toolDetail, setToolDetail] = useState<Tool | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  
  // Edit state
  const [editing, setEditing] = useState(false);
  const [editForm, setEditForm] = useState<Partial<Tool>>({});
  const [saving, setSaving] = useState(false);
  
  // Add modal state
  const [showAddModal, setShowAddModal] = useState(false);
  const [newTool, setNewTool] = useState<Partial<Tool>>({
    name: '',
    description: '',
    category: 'internal',
    actions: [],
    requires_env: [],
    weight: 0.5,
    enabled: true,
    code: '',
  });
  const [newAction, setNewAction] = useState('');
  const [newEnvVar, setNewEnvVar] = useState('');
  
  // Filter state
  const [filterCategory, setFilterCategory] = useState<string>('all');
  const [filterAvailable, setFilterAvailable] = useState<'all' | 'available' | 'unavailable'>('all');
  
  // Execute/test state
  const [selectedAction, setSelectedAction] = useState<string>('');
  const [executeParams, setExecuteParams] = useState<string>('{}');
  const [executing, setExecuting] = useState(false);
  const [executeResult, setExecuteResult] = useState<ExecuteResult | null>(null);

  const fetchTools = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/form/tools`);
      const data = await res.json();
      setTools(data);
    } catch (err) {
      console.error('Failed to fetch tools:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCategories = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/form/categories`);
      const data = await res.json();
      setCategories(data);
    } catch (err) {
      console.error('Failed to fetch categories:', err);
    }
  }, []);

  const fetchToolDetail = useCallback(async (name: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/form/tools/${name}`);
      const data = await res.json();
      setToolDetail(data);
    } catch (err) {
      console.error('Failed to fetch tool detail:', err);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTools();
    fetchCategories();
  }, [fetchTools, fetchCategories]);

  useEffect(() => {
    if (activeTool) {
      fetchToolDetail(activeTool);
      setEditing(false);
      setExecuteResult(null);
      setSelectedAction('');
      setExecuteParams('{}');
    }
  }, [activeTool, fetchToolDetail]);

  const executeTool = async () => {
    if (!activeTool || !selectedAction) return;
    
    setExecuting(true);
    setExecuteResult(null);
    
    try {
      let params = {};
      try {
        params = JSON.parse(executeParams);
      } catch {
        // Invalid JSON, use empty object
      }
      
      const res = await fetch(`${API_BASE}/api/form/tools/${activeTool}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: selectedAction, params }),
      });
      
      const result = await res.json();
      setExecuteResult(result);
    } catch (err) {
      setExecuteResult({
        tool_name: activeTool,
        action: selectedAction,
        status: 'error',
        output: null,
        error: String(err),
        duration_ms: 0,
        timestamp: new Date().toISOString(),
        success: false,
      });
    } finally {
      setExecuting(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete tool "${name}"? This will remove the code from tools.py.`)) return;
    
    try {
      const res = await fetch(`${API_BASE}/api/form/tools/${name}`, { method: 'DELETE' });
      if (res.ok) {
        fetchTools();
        if (activeTool === name) {
          setActiveTool(null);
          setToolDetail(null);
        }
      }
    } catch (err) {
      console.error('Failed to delete tool:', err);
    }
  };

  const startEditing = () => {
    if (toolDetail) {
      setEditForm({ ...toolDetail });
      setEditing(true);
    }
  };

  const cancelEditing = () => {
    setEditing(false);
    setEditForm({});
  };

  const saveChanges = async () => {
    if (!activeTool || !editForm) return;
    
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/form/tools/${activeTool}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editForm),
      });
      
      if (res.ok) {
        setEditing(false);
        fetchToolDetail(activeTool);
        fetchTools();
      }
    } catch (err) {
      console.error('Failed to save changes:', err);
    } finally {
      setSaving(false);
    }
  };

  const createTool = async () => {
    if (!newTool.name || !newTool.description) return;
    
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/form/tools`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(newTool),
      });
      
      if (res.ok) {
        setShowAddModal(false);
        setNewTool({
          name: '',
          description: '',
          category: 'internal',
          actions: [],
          requires_env: [],
          weight: 0.5,
          enabled: true,
          code: '',
        });
        fetchTools();
      }
    } catch (err) {
      console.error('Failed to create tool:', err);
    } finally {
      setSaving(false);
    }
  };

  const addAction = () => {
    if (newAction.trim()) {
      setNewTool({
        ...newTool,
        actions: [...(newTool.actions || []), newAction.trim()],
      });
      setNewAction('');
    }
  };

  const removeAction = (action: string) => {
    setNewTool({
      ...newTool,
      actions: (newTool.actions || []).filter(a => a !== action),
    });
  };

  const addEnvVar = () => {
    if (newEnvVar.trim()) {
      setNewTool({
        ...newTool,
        requires_env: [...(newTool.requires_env || []), newEnvVar.trim()],
      });
      setNewEnvVar('');
    }
  };

  const removeEnvVar = (envVar: string) => {
    setNewTool({
      ...newTool,
      requires_env: (newTool.requires_env || []).filter(e => e !== envVar),
    });
  };

  // Filter tools
  const filteredTools = tools.filter(tool => {
    if (filterCategory !== 'all' && tool.category !== filterCategory) return false;
    if (filterAvailable === 'available' && !tool.available) return false;
    if (filterAvailable === 'unavailable' && tool.available) return false;
    return true;
  });

  // Group by category
  const groupedTools = filteredTools.reduce((acc, tool) => {
    const cat = tool.category;
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(tool);
    return acc;
  }, {} as Record<string, Tool[]>);

  return (
    <div className="tool-dashboard">
      <div className="tool-dashboard-layout">
        {/* Left: Tool List */}
        <div className="tool-list">
          <div className="tool-list-header">
            <span>Tools ({filteredTools.length})</span>
            <button className="add-btn" onClick={() => setShowAddModal(true)}>+ Add</button>
          </div>

          <div className="tool-filters">
            <ThemedSelect
              options={[
                { value: 'all', label: 'All Categories' },
                ...categories.map(cat => ({ value: cat.value, label: cat.label, icon: cat.icon }))
              ]}
              value={filterCategory}
              onChange={setFilterCategory}
              className="filter-select"
            />
            <ThemedSelect
              options={[
                { value: 'all', label: 'All Status' },
                { value: 'available', label: '✓ Available' },
                { value: 'unavailable', label: '✗ Unavailable' }
              ]}
              value={filterAvailable}
              onChange={(v) => setFilterAvailable(v as 'all' | 'available' | 'unavailable')}
              className="filter-select"
            />
          </div>

          {loading ? (
            <div className="loading">Loading tools...</div>
          ) : (
            <div className="tools-grouped">
              {Object.entries(groupedTools).map(([category, catTools]) => (
                <div key={category} className="tool-category-group">
                  <div className="category-header">
                    <span className="category-icon">{CATEGORY_ICONS[category] || '📦'}</span>
                    <span>{category}</span>
                    <span className="category-count">{catTools.length}</span>
                  </div>
                  {catTools.map((tool) => (
                    <button
                      key={tool.name}
                      className={`tool-item ${activeTool === tool.name ? 'active' : ''} ${!tool.available ? 'unavailable' : ''}`}
                      onClick={() => setActiveTool(tool.name)}
                    >
                      <div className="tool-info">
                        <span className="tool-name">
                          {tool.exists ? '✓' : '○'} {tool.name}
                        </span>
                        <span className="tool-desc">{tool.description.slice(0, 40)}...</span>
                      </div>
                      <div className={`status-dot ${tool.available ? 'available' : 'unavailable'}`} />
                    </button>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Tool Detail */}
        <div className="tool-detail">
          {!activeTool ? (
            <div className="no-selection">
              <div className="no-selection-icon">🔧</div>
              <h3>Select a tool</h3>
              <p>Choose a tool to view its configuration and handler code.</p>
              <button className="primary-btn" onClick={() => setShowAddModal(true)}>
                + Create New Tool
              </button>
            </div>
          ) : detailLoading ? (
            <div className="loading">Loading tool details...</div>
          ) : toolDetail ? (
            <>
              <div className="detail-header">
                <div className="detail-title">
                  <span className="detail-icon">{CATEGORY_ICONS[toolDetail.category] || '📦'}</span>
                  <div>
                    <h2>{toolDetail.name}</h2>
                    <span className="detail-category">{toolDetail.category}</span>
                  </div>
                </div>
                <div className="detail-actions">
                  {editing ? (
                    <>
                      <button className="save-btn" onClick={saveChanges} disabled={saving}>
                        {saving ? 'Saving...' : 'Save'}
                      </button>
                      <button className="cancel-btn" onClick={cancelEditing}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="edit-btn" onClick={startEditing}>Edit</button>
                      <button className="delete-btn" onClick={() => handleDelete(toolDetail.name)}>
                        Delete
                      </button>
                    </>
                  )}
                </div>
              </div>

              <div className={`status-banner ${toolDetail.available ? 'available' : 'unavailable'}`}>
                {toolDetail.available ? '✓ Available' : '✗ Missing Requirements'}
                {!toolDetail.available && toolDetail.requires_env.length > 0 && (
                  <span className="missing-env">
                    Needs: {toolDetail.requires_env.join(', ')}
                  </span>
                )}
              </div>

              <div className="detail-sections">
                {/* Description */}
                <div className="detail-section">
                  <h3>Description</h3>
                  {editing ? (
                    <textarea
                      value={editForm.description || ''}
                      onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                      rows={3}
                    />
                  ) : (
                    <p>{toolDetail.description}</p>
                  )}
                </div>

                {/* Actions */}
                <div className="detail-section">
                  <h3>Actions</h3>
                  <div className="action-tags">
                    {toolDetail.actions.map((action) => (
                      <span key={action} className="action-tag">{action}</span>
                    ))}
                  </div>
                </div>

                {/* Weight */}
                <div className="detail-section">
                  <h3>Weight (Priority)</h3>
                  {editing ? (
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={editForm.weight || 0.5}
                      onChange={(e) => setEditForm({ ...editForm, weight: parseFloat(e.target.value) })}
                    />
                  ) : (
                    <div className="weight-bar">
                      <div className="weight-fill" style={{ width: `${toolDetail.weight * 100}%` }} />
                      <span className="weight-label">{toolDetail.weight}</span>
                    </div>
                  )}
                </div>

                {/* Handler Code */}
                <div className="detail-section code-section">
                  <h3>
                    Executable Code
                    <span className="code-path">
                      {toolDetail.run_file ? `executables/${toolDetail.run_file}` : 'No file'}
                    </span>
                  </h3>
                  {editing ? (
                    <textarea
                      value={editForm.code || ''}
                      onChange={(e) => setEditForm({ ...editForm, code: e.target.value })}
                      rows={15}
                      className="code-editor"
                      spellCheck={false}
                      placeholder={`"""
${toolDetail.name} Tool
"""

from typing import Any, Dict


def run(action: str, params: Dict[str, Any]) -> Any:
    """Execute a ${toolDetail.name} action."""
    
    if action == "${toolDetail.actions[0] || 'example'}":
        # Your implementation here
        return {"status": "success"}
    
    raise ValueError(f"Unknown action: {action}")`}
                    />
                  ) : toolDetail.code ? (
                    <pre className="code-block">{toolDetail.code}</pre>
                  ) : (
                    <p className="no-code">
                      {toolDetail.exists 
                        ? 'Loading executable code...' 
                        : `No executable file found. Create: executables/${toolDetail.run_file || toolDetail.name + '.py'}`}
                    </p>
                  )}
                </div>

                {/* Execution Environment */}
                <div className="detail-section execute-section">
                  <h3>🧪 Test Environment</h3>
                  <div className="execute-controls">
                    <div className="execute-row">
                      <ThemedSelect
                        options={toolDetail.actions.map(action => ({ value: action, label: action }))}
                        value={selectedAction}
                        onChange={setSelectedAction}
                        placeholder="Select action..."
                        className="action-select"
                      />
                      <button 
                        className="run-btn"
                        onClick={executeTool}
                        disabled={!selectedAction || executing || !toolDetail.available}
                      >
                        {executing ? '⏳ Running...' : '▶ Run'}
                      </button>
                    </div>
                    <div className="params-row">
                      <label>Params (JSON):</label>
                      <textarea
                        value={executeParams}
                        onChange={(e) => setExecuteParams(e.target.value)}
                        rows={3}
                        className="params-editor"
                        placeholder='{"key": "value"}'
                        spellCheck={false}
                      />
                    </div>
                  </div>
                  
                  {executeResult && (
                    <div className={`execute-result ${executeResult.success ? 'success' : 'error'}`}>
                      <div className="result-header">
                        <span className="result-status">
                          {executeResult.success ? '✓' : '✗'} {executeResult.status}
                        </span>
                        <span className="result-duration">{executeResult.duration_ms.toFixed(1)}ms</span>
                      </div>
                      {executeResult.error ? (
                        <pre className="result-error">{executeResult.error}</pre>
                      ) : (
                        <pre className="result-output">
                          {typeof executeResult.output === 'object' 
                            ? JSON.stringify(executeResult.output, null, 2)
                            : String(executeResult.output)}
                        </pre>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          ) : null}
        </div>
      </div>

      {/* Add Tool Modal */}
      {showAddModal && (
        <div className="modal-overlay" onClick={() => setShowAddModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Create New Tool</h2>
              <button className="close-btn" onClick={() => setShowAddModal(false)}>×</button>
            </div>
            
            <div className="modal-body">
              <div className="form-group">
                <label>Name *</label>
                <input
                  type="text"
                  value={newTool.name}
                  onChange={(e) => setNewTool({ ...newTool, name: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                  placeholder="my_tool"
                />
              </div>
              
              <div className="form-group">
                <label>Description *</label>
                <textarea
                  value={newTool.description}
                  onChange={(e) => setNewTool({ ...newTool, description: e.target.value })}
                  placeholder="What does this tool do?"
                  rows={2}
                />
              </div>
              
              <div className="form-group">
                <label>Category</label>
                <ThemedSelect
                  options={categories.map(cat => ({ value: cat.value, label: cat.label, icon: cat.icon }))}
                  value={newTool.category || 'internal'}
                  onChange={(v) => setNewTool({ ...newTool, category: v })}
                />
              </div>
              
              <div className="form-group">
                <label>Actions</label>
                <div className="tag-input">
                  <input
                    type="text"
                    value={newAction}
                    onChange={(e) => setNewAction(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addAction())}
                    placeholder="Add action..."
                  />
                  <button onClick={addAction}>+</button>
                </div>
                <div className="tags">
                  {(newTool.actions || []).map(action => (
                    <span key={action} className="tag">
                      {action}
                      <button onClick={() => removeAction(action)}>×</button>
                    </span>
                  ))}
                </div>
              </div>
              
              <div className="form-group">
                <label>Required Environment Variables</label>
                <div className="tag-input">
                  <input
                    type="text"
                    value={newEnvVar}
                    onChange={(e) => setNewEnvVar(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addEnvVar())}
                    placeholder="API_KEY"
                  />
                  <button onClick={addEnvVar}>+</button>
                </div>
                <div className="tags">
                  {(newTool.requires_env || []).map(envVar => (
                    <span key={envVar} className="tag env-tag">
                      {envVar}
                      <button onClick={() => removeEnvVar(envVar)}>×</button>
                    </span>
                  ))}
                </div>
              </div>
              
              <div className="form-group">
                <label>Weight (Priority): {newTool.weight}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={newTool.weight}
                  onChange={(e) => setNewTool({ ...newTool, weight: parseFloat(e.target.value) })}
                />
              </div>
              
              <div className="form-group">
                <label>Handler Code (Python)</label>
                <textarea
                  value={newTool.code}
                  onChange={(e) => setNewTool({ ...newTool, code: e.target.value })}
                  rows={12}
                  className="code-editor"
                  spellCheck={false}
                  placeholder={`@register_handler("${newTool.name || 'my_tool'}")
def handle_${(newTool.name || 'my_tool').replace(/-/g, '_')}(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle ${newTool.name || 'my_tool'} operations."""
    
    if action == "example":
        return ToolResult(
            status=ExecutionStatus.SUCCESS,
            tool="${newTool.name || 'my_tool'}",
            action=action,
            output="Success!",
        )
    
    return ToolResult(
        status=ExecutionStatus.ERROR,
        tool="${newTool.name || 'my_tool'}",
        action=action,
        output=None,
        error=f"Unknown action: {action}",
    )`}
                />
              </div>
            </div>
            
            <div className="modal-footer">
              <button className="cancel-btn" onClick={() => setShowAddModal(false)}>Cancel</button>
              <button 
                className="create-btn" 
                onClick={createTool}
                disabled={saving || !newTool.name || !newTool.description}
              >
                {saving ? 'Creating...' : 'Create Tool'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ToolDashboard;
