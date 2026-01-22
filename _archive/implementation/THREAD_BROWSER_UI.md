# Thread Browser UI Implementation

**Status**: ✅ COMPLETE (implemented as ThreadsPage)  
**Updated**: 2026-01-09

**Goal:** Replace/augment the introspection panel with a full thread browser where you can click any thread, see its modules, and inspect/edit data.

## Implementation ✅

The thread browser is implemented as `Nola/react-chat-app/frontend/src/pages/ThreadsPage.tsx`:

- ✅ Thread tabs (identity, log, philosophy, reflex, form, linking_core)
- ✅ Thread health display with status indicators
- ✅ Identity flat table with L1/L2/L3 columns
- ✅ Philosophy flat table (same schema as identity)
- ✅ Edit/Delete actions on rows
- ✅ Add Row form for identity and philosophy
- ✅ Level selector (L1/L2/L3)
- ✅ Log event viewer with filters and sorting
- ✅ Add Event form for log thread

Accessible at `/threads` route.

## Future Enhancements (Nice to Have)

- [ ] Search/filter within identity/philosophy tables
- [ ] Promote/Demote weight actions
- [ ] Bulk edit/delete

---

## Original Design Reference

```
┌────────────────────────────────────────────────────────┐
│ 🧵 Thread Browser                          [Summary ▼] │
├────────────────────────────────────────────────────────┤
│ ┌──────────┬─────┬──────┬──────────┬────────┐         │
│ │ identity │ log │ form │ philosophy│ reflex │         │  ← Thread tabs
│ └──────────┴─────┴──────┴──────────┴────────┘         │
├────────────────────────────────────────────────────────┤
│                                                        │
│  📁 identity                                           │
│  ├── 👤 user_profile ────────────── 5 items           │
│  ├── 🖥️ machine_context ─────────── 2 items           │
│  └── 🤖 nola_self ───────────────── 4 items           │
│                                                        │
├────────────────────────────────────────────────────────┤
│  👤 user_profile                         [+ Add Key]   │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 🔑 user_name                                      │ │
│  │    Level: L1  Weight: 0.95  Accessed: 2h ago     │ │
│  │    ┌────────────────────────────────────────┐    │ │
│  │    │ { "value": "Jordan Rivera" }           │    │ │
│  │    └────────────────────────────────────────┘    │ │
│  │    [Edit] [Delete] [↑ Promote] [↓ Demote]        │ │
│  ├──────────────────────────────────────────────────┤ │
│  │ 🔑 projects                                       │ │
│  │    Level: L2  Weight: 0.80  Accessed: 1d ago     │ │
│  │    ┌────────────────────────────────────────┐    │ │
│  │    │ { "value": ["Nola AI", "AI_OS"] }      │    │ │
│  │    └────────────────────────────────────────┘    │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  [📸 Create Checkpoint]        Last: 2h ago (3 saved) │
└────────────────────────────────────────────────────────┘
```

---

## Component Structure

```
components/ThreadBrowser/
├── index.ts                 # Exports
├── ThreadBrowser.tsx        # Main container
├── ThreadBrowser.css        # All styles
├── ThreadTabs.tsx           # Tab bar for threads
├── ModuleList.tsx           # List modules in thread
├── ModuleViewer.tsx         # Show rows in module
├── DataRow.tsx              # Individual key display
├── DataEditor.tsx           # Edit modal (future)
└── CheckpointBar.tsx        # Checkpoint controls
```

---

## Components

### ThreadBrowser.tsx (Main Container)

```tsx
interface ThreadBrowserProps {
  defaultThread?: string;
  showCheckpoints?: boolean;
}

// State
const [selectedThread, setSelectedThread] = useState<string>('identity');
const [selectedModule, setSelectedModule] = useState<string | null>(null);
const [threadSummary, setThreadSummary] = useState<ThreadSummary | null>(null);
const [moduleData, setModuleData] = useState<ModuleRow[]>([]);
const [contextLevel, setContextLevel] = useState<number>(2);

// Layout
return (
  <div className="thread-browser">
    <header className="tb-header">
      <h3>🧵 Thread Browser</h3>
      <LevelSelector value={contextLevel} onChange={setContextLevel} />
    </header>
    
    <ThreadTabs 
      threads={THREADS}
      selected={selectedThread}
      onSelect={handleThreadSelect}
      summary={threadSummary}
    />
    
    {selectedModule ? (
      <ModuleViewer
        thread={selectedThread}
        module={selectedModule}
        level={contextLevel}
        data={moduleData}
        onBack={() => setSelectedModule(null)}
      />
    ) : (
      <ModuleList
        thread={selectedThread}
        modules={threadSummary?.[selectedThread]?.modules || []}
        onSelect={handleModuleSelect}
      />
    )}
    
    {showCheckpoints && <CheckpointBar />}
  </div>
);
```

### ThreadTabs.tsx

```tsx
const THREADS = [
  { id: 'identity', icon: '🪪', label: 'Identity' },
  { id: 'log', icon: '📜', label: 'Log' },
  { id: 'form', icon: '⚡', label: 'Form' },
  { id: 'philosophy', icon: '🧭', label: 'Philosophy' },
  { id: 'reflex', icon: '⚡', label: 'Reflex' },
];

return (
  <div className="thread-tabs">
    {THREADS.map(thread => (
      <button
        key={thread.id}
        className={`thread-tab ${selected === thread.id ? 'active' : ''}`}
        onClick={() => onSelect(thread.id)}
      >
        <span className="tab-icon">{thread.icon}</span>
        <span className="tab-label">{thread.label}</span>
        {summary?.[thread.id]?.total_rows && (
          <span className="tab-count">{summary[thread.id].total_rows}</span>
        )}
      </button>
    ))}
  </div>
);
```

### ModuleList.tsx

```tsx
const MODULE_ICONS: Record<string, string> = {
  user_profile: '👤',
  machine_context: '🖥️',
  nola_self: '🤖',
  events: '📋',
  sessions: '💬',
  checkpoints: '📸',
  // etc.
};

return (
  <div className="module-list">
    <h4>📁 {thread}</h4>
    {modules.map(mod => (
      <button
        key={mod.name}
        className="module-item"
        onClick={() => onSelect(mod.name)}
      >
        <span className="module-icon">{MODULE_ICONS[mod.name] || '📄'}</span>
        <span className="module-name">{mod.name}</span>
        <span className="module-count">{mod.count} items</span>
        <span className="module-arrow">→</span>
      </button>
    ))}
  </div>
);
```

### ModuleViewer.tsx

```tsx
return (
  <div className="module-viewer">
    <header className="mv-header">
      <button className="back-button" onClick={onBack}>← Back</button>
      <h4>{MODULE_ICONS[module]} {module}</h4>
      <button className="add-button">+ Add Key</button>
    </header>
    
    <div className="mv-search">
      <input 
        type="text" 
        placeholder="Search keys..." 
        value={search}
        onChange={e => setSearch(e.target.value)}
      />
    </div>
    
    <div className="mv-rows">
      {filteredData.map(row => (
        <DataRow 
          key={row.key}
          data={row}
          onEdit={() => handleEdit(row)}
          onDelete={() => handleDelete(row.key)}
        />
      ))}
    </div>
  </div>
);
```

### DataRow.tsx

```tsx
interface DataRowProps {
  data: {
    key: string;
    metadata: Record<string, any>;
    data: Record<string, any>;
    level: number;
    weight: number;
    last_accessed?: string;
  };
  onEdit?: () => void;
  onDelete?: () => void;
}

return (
  <div className="data-row">
    <div className="dr-header">
      <span className="dr-key">🔑 {data.key}</span>
      <span className={`dr-level level-${data.level}`}>L{data.level}</span>
      <span className="dr-weight">w:{data.weight.toFixed(2)}</span>
    </div>
    
    {data.last_accessed && (
      <div className="dr-meta">
        Accessed: {formatRelativeTime(data.last_accessed)}
      </div>
    )}
    
    <div className="dr-data">
      <pre>{JSON.stringify(data.data, null, 2)}</pre>
    </div>
    
    <div className="dr-actions">
      <button onClick={onEdit}>Edit</button>
      <button onClick={onDelete} className="danger">Delete</button>
    </div>
  </div>
);
```

---

## Service Layer

### introspectionService.ts additions

```typescript
interface ThreadSummary {
  [threadName: string]: {
    modules: string[];
    module_details: {
      [moduleName: string]: {
        count: number;
        keys: string[];
      };
    };
    total_rows: number;
  };
}

interface ModuleRow {
  key: string;
  metadata: Record<string, any>;
  data: Record<string, any>;
  level: number;
  weight: number;
  last_accessed?: string;
}

class IntrospectionService {
  // ... existing methods ...

  async getThreadSummary(): Promise<ThreadSummary> {
    const response = await fetch(`${this.baseUrl}/api/introspection/threads/summary`);
    if (!response.ok) throw new Error(`Thread summary error: ${response.status}`);
    return response.json();
  }

  async getThreadData(thread: string, level: number = 2): Promise<Record<string, ModuleRow[]>> {
    const response = await fetch(
      `${this.baseUrl}/api/introspection/threads/${thread}?level=${level}`
    );
    if (!response.ok) throw new Error(`Thread data error: ${response.status}`);
    const data = await response.json();
    return data.modules;
  }

  async getModuleData(thread: string, module: string, level: number = 2): Promise<ModuleRow[]> {
    const response = await fetch(
      `${this.baseUrl}/api/introspection/threads/${thread}/${module}?level=${level}`
    );
    if (!response.ok) throw new Error(`Module data error: ${response.status}`);
    const data = await response.json();
    return data.rows;
  }

  async updateKey(thread: string, module: string, key: string, value: any): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/introspection/threads/${thread}/${module}/${key}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(value)
      }
    );
    if (!response.ok) throw new Error(`Update error: ${response.status}`);
  }

  async deleteKey(thread: string, module: string, key: string): Promise<void> {
    const response = await fetch(
      `${this.baseUrl}/api/introspection/threads/${thread}/${module}/${key}`,
      { method: 'DELETE' }
    );
    if (!response.ok) throw new Error(`Delete error: ${response.status}`);
  }
}
```

---

## Hook: useThreadBrowser

```typescript
// hooks/useThreadBrowser.ts

interface UseThreadBrowserOptions {
  initialThread?: string;
  level?: number;
  pollInterval?: number;
}

interface UseThreadBrowserResult {
  // State
  selectedThread: string;
  selectedModule: string | null;
  threadSummary: ThreadSummary | null;
  moduleData: ModuleRow[];
  level: number;
  isLoading: boolean;
  error: string | null;
  
  // Actions
  selectThread: (thread: string) => void;
  selectModule: (module: string | null) => void;
  setLevel: (level: number) => void;
  refresh: () => Promise<void>;
  updateKey: (key: string, value: any) => Promise<void>;
  deleteKey: (key: string) => Promise<void>;
}

export function useThreadBrowser(options: UseThreadBrowserOptions = {}): UseThreadBrowserResult {
  const {
    initialThread = 'identity',
    level: initialLevel = 2,
    pollInterval = 0  // No polling by default for browser
  } = options;

  const [selectedThread, setSelectedThread] = useState(initialThread);
  const [selectedModule, setSelectedModule] = useState<string | null>(null);
  const [threadSummary, setThreadSummary] = useState<ThreadSummary | null>(null);
  const [moduleData, setModuleData] = useState<ModuleRow[]>([]);
  const [level, setLevel] = useState(initialLevel);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch thread summary on mount
  useEffect(() => {
    fetchSummary();
  }, []);

  // Fetch module data when selection changes
  useEffect(() => {
    if (selectedModule) {
      fetchModuleData();
    }
  }, [selectedThread, selectedModule, level]);

  const fetchSummary = async () => {
    try {
      const summary = await introspectionService.getThreadSummary();
      setThreadSummary(summary);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch summary');
    }
  };

  const fetchModuleData = async () => {
    if (!selectedModule) return;
    setIsLoading(true);
    try {
      const data = await introspectionService.getModuleData(
        selectedThread, 
        selectedModule, 
        level
      );
      setModuleData(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data');
    } finally {
      setIsLoading(false);
    }
  };

  const selectThread = (thread: string) => {
    setSelectedThread(thread);
    setSelectedModule(null);  // Reset module when thread changes
    setModuleData([]);
  };

  const selectModule = (module: string | null) => {
    setSelectedModule(module);
  };

  const refresh = async () => {
    await fetchSummary();
    if (selectedModule) {
      await fetchModuleData();
    }
  };

  const updateKey = async (key: string, value: any) => {
    if (!selectedModule) return;
    await introspectionService.updateKey(selectedThread, selectedModule, key, value);
    await fetchModuleData();  // Refresh
  };

  const deleteKey = async (key: string) => {
    if (!selectedModule) return;
    await introspectionService.deleteKey(selectedThread, selectedModule, key);
    await fetchModuleData();  // Refresh
  };

  return {
    selectedThread,
    selectedModule,
    threadSummary,
    moduleData,
    level,
    isLoading,
    error,
    selectThread,
    selectModule,
    setLevel,
    refresh,
    updateKey,
    deleteKey
  };
}
```

---

## Backend Endpoints Needed

Most already exist, but we need:

```python
# PUT /api/introspection/threads/{thread}/{module}/{key}
@router.put("/threads/{thread_name}/{module_name}/{key}")
async def update_key(thread_name: str, module_name: str, key: str, body: dict):
    """Update a specific key's data."""
    from Nola.threads.schema import push_to_module
    push_to_module(
        thread_name, module_name, key,
        metadata=body.get("metadata", {}),
        data=body.get("data", {}),
        level=body.get("level", 2),
        weight=body.get("weight", 0.5)
    )
    return {"success": True}

# DELETE /api/introspection/threads/{thread}/{module}/{key}
@router.delete("/threads/{thread_name}/{module_name}/{key}")
async def delete_key(thread_name: str, module_name: str, key: str):
    """Delete a specific key."""
    from Nola.threads.schema import delete_from_module
    delete_from_module(thread_name, module_name, key)
    return {"success": True}
```

---

## CSS Structure

```css
/* ThreadBrowser.css */

.thread-browser {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #1a1a2e;
}

/* Thread Tabs */
.thread-tabs {
  display: flex;
  gap: 2px;
  padding: 8px;
  background: #16213e;
  border-bottom: 1px solid #0f3460;
  overflow-x: auto;
}

.thread-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #a0aec0;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}

.thread-tab:hover {
  background: rgba(255,255,255,0.1);
}

.thread-tab.active {
  background: #0f3460;
  color: white;
}

.tab-count {
  background: rgba(0,0,0,0.3);
  padding: 2px 6px;
  border-radius: 10px;
  font-size: 10px;
}

/* Module List */
.module-list {
  padding: 12px;
}

.module-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  margin-bottom: 4px;
  background: rgba(0,0,0,0.2);
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  color: #e8e8e8;
}

.module-item:hover {
  background: rgba(15, 52, 96, 0.5);
  border-color: #0f3460;
}

.module-name {
  flex: 1;
}

.module-count {
  color: #718096;
  font-size: 11px;
}

/* Data Rows */
.data-row {
  background: rgba(0,0,0,0.2);
  border: 1px solid #2d3748;
  border-radius: 6px;
  margin-bottom: 8px;
  overflow: hidden;
}

.dr-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(0,0,0,0.2);
}

.dr-key {
  font-weight: 600;
  flex: 1;
}

.dr-level {
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
}

.dr-level.level-1 { background: #22c55e33; color: #22c55e; }
.dr-level.level-2 { background: #3b82f633; color: #3b82f6; }
.dr-level.level-3 { background: #8b5cf633; color: #8b5cf6; }

.dr-weight {
  color: #718096;
  font-size: 11px;
}

.dr-data {
  padding: 8px 12px;
}

.dr-data pre {
  margin: 0;
  font-size: 11px;
  color: #a0aec0;
  white-space: pre-wrap;
  word-break: break-word;
}

.dr-actions {
  display: flex;
  gap: 4px;
  padding: 8px 12px;
  border-top: 1px solid #2d3748;
}

.dr-actions button {
  padding: 4px 8px;
  font-size: 11px;
  border-radius: 3px;
  border: none;
  cursor: pointer;
  background: #4a5568;
  color: white;
}

.dr-actions button:hover {
  background: #2d3748;
}

.dr-actions button.danger {
  background: #e53e3e33;
  color: #fc8181;
}
```

---

## Implementation Order

1. **Backend first** - Add PUT/DELETE endpoints, verify existing ones work
2. **Service layer** - Add methods to introspectionService.ts
3. **Hook** - Create useThreadBrowser.ts
4. **Components** - Build from bottom up: DataRow → ModuleViewer → ModuleList → ThreadTabs → ThreadBrowser
5. **Integration** - Replace/add alongside RightSidebar
6. **Polish** - Animations, search, edit modal

---

## Future Enhancements

- [ ] Edit modal with JSON editor
- [ ] Bulk operations (select multiple, delete)
- [ ] Export module to JSON
- [ ] Import from JSON
- [ ] Diff view between checkpoints
- [ ] Search across all threads
- [ ] Keyboard navigation (j/k up/down, Enter to select)
