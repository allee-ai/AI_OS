import { useState, useEffect, useCallback } from 'react';
import './ToolDashboard.css';

interface Tool {
  name: string;
  description: string;
  category: string;
  actions: string[];
  requires_env: string[];
  weight: number;
  enabled: boolean;
  available: boolean;
  code?: string;
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
    }
  }, [activeTool, fetchToolDetail]);

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
            <select 
              value={filterCategory} 
              onChange={(e) => setFilterCategory(e.target.value)}
              className="filter-select"
            >
              <option value="all">All Categories</option>
              {categories.map(cat => (
                <option key={cat.value} value={cat.value}>{cat.icon} {cat.label}</option>
              ))}
            </select>
            <select 
              value={filterAvailable} 
              onChange={(e) => setFilterAvailable(e.target.value as 'all' | 'available' | 'unavailable')}
              className="filter-select"
            >
              <option value="all">All Status</option>
              <option value="available">✓ Available</option>
              <option value="unavailable">✗ Unavailable</option>
            </select>
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
                        <span className="tool-name">{tool.name}</span>
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
                  <h3>Handler Code (Python)</h3>
                  {editing ? (
                    <textarea
                      value={editForm.code || ''}
                      onChange={(e) => setEditForm({ ...editForm, code: e.target.value })}
                      rows={15}
                      className="code-editor"
                      spellCheck={false}
                      placeholder={`@register_handler("${toolDetail.name}")
def handle_${toolDetail.name.replace(/-/g, '_')}(action: str, params: Dict[str, Any]) -> ToolResult:
    """Handle ${toolDetail.name} operations."""
    # Your code here
    return ToolResult(
        status=ExecutionStatus.SUCCESS,
        tool="${toolDetail.name}",
        action=action,
        output="Result",
    )`}
                    />
                  ) : toolDetail.code ? (
                    <pre className="code-block">{toolDetail.code}</pre>
                  ) : (
                    <p className="no-code">No handler code defined. Edit to add Python code.</p>
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
                <select
                  value={newTool.category}
                  onChange={(e) => setNewTool({ ...newTool, category: e.target.value })}
                >
                  {categories.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.icon} {cat.label}</option>
                  ))}
                </select>
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
