import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { BASE_URL } from '../../../config/api';
import './ThreadsPage.css';
import { ToolDashboard } from '../form';
import { ReflexDashboard } from '../reflex';
import SubconsciousDashboard from '../../subconscious/components/SubconsciousDashboard';
import IdentityProfilesPage from '../identity/pages/ProfilesPage';
import PhilosophyProfilesPage from '../philosophy/pages/ProfilesPage';
import { ConceptGraph3D } from '../linking_core';
import { LogDashboard } from '../../log';

interface ThreadHealth {
  name: string;
  status: string;
  message: string;
  has_data: boolean;
}

interface IdentityRow {
  key: string;
  metadata_type: string;
  metadata_desc: string;
  l1: string;
  l2: string;
  l3: string;
  weight: number;
}

// Philosophy uses same structure as Identity
type PhilosophyRow = IdentityRow;

interface GenericRow {
  key: string;
  data: Record<string, any>;
  metadata: Record<string, any>;
  level: number;
  weight: number;
}

const THREAD_ICONS: Record<string, string> = {
  identity: '🪪',
  log: '📜',
  philosophy: '🏛️',
  reflex: '⚡',
  form: '🔧',
  linking_core: '🔗',
  subconscious: '🧠',
};

// Threads that display documentation instead of data tables
const DOC_THREADS = new Set<string>([]);  // linking_core now has 3D viz

export const ThreadsPage = () => {
  const [threads, setThreads] = useState<Record<string, ThreadHealth>>({});
  const [activeThread, setActiveThread] = useState<string | null>(null);
  const [identityRows, setIdentityRows] = useState<IdentityRow[]>([]);
  const [philosophyRows, setPhilosophyRows] = useState<PhilosophyRow[]>([]);
  const [genericModules, setGenericModules] = useState<Record<string, GenericRow[]>>({});
  const [readmeContent, setReadmeContent] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [dataLoading, setDataLoading] = useState(false);

  const fetchIdentityCount = () => {
    fetch(`${BASE_URL}/api/identity/table`)
      .then(res => res.json())
      .then(data => {
        setIdentityRows(data.rows || []);
        setDataLoading(false);
      })
      .catch(() => {
        setIdentityRows([]);
        setDataLoading(false);
      });
  };

  const fetchPhilosophyData = () => {
    fetch(`${BASE_URL}/api/philosophy/table`)
      .then(res => res.json())
      .then(data => {
        setPhilosophyRows(data.rows || []);
        setGenericModules({});
        setDataLoading(false);
      })
      .catch(() => {
        setPhilosophyRows([]);
        setDataLoading(false);
      });
  };

  const [searchParams] = useSearchParams();
  const tabParam = searchParams.get('tab');

  useEffect(() => {
    fetch(`${BASE_URL}/api/subconscious/threads`)
      .then(res => res.json())
      .then(data => {
        setThreads(data.threads || {});
        setLoading(false);
        // Check URL param first, then find first with data
        if (tabParam && Object.keys(data.threads || {}).includes(tabParam)) {
          setActiveThread(tabParam);
        } else {
          const firstWithData = Object.values(data.threads || {}).find((t: any) => t.has_data);
          if (firstWithData) {
            setActiveThread((firstWithData as ThreadHealth).name);
          }
        }
      })
      .catch(() => setLoading(false));
  }, [tabParam]);

  useEffect(() => {
    if (!activeThread) return;
    
    setDataLoading(true);
    setReadmeContent('');
    
    // Documentation threads - fetch README
    if (DOC_THREADS.has(activeThread)) {
      fetch(`${BASE_URL}/api/${activeThread}/readme`)
        .then(res => res.json())
        .then(data => {
          setReadmeContent(data.content || '');
          setIdentityRows([]);
          setGenericModules({});
          setDataLoading(false);
        })
        .catch(() => {
          setReadmeContent('');
          setDataLoading(false);
        });
      return;
    }
    
    if (activeThread === 'identity') {
      fetchIdentityCount();
    } else if (activeThread === 'philosophy') {
      fetchPhilosophyData();
    } else if (activeThread === 'log' || activeThread === 'form' || activeThread === 'reflex' || activeThread === 'linking_core' || activeThread === 'subconscious') {
      // These threads have their own dashboards that fetch their own data
      setDataLoading(false);
    } else {
      fetch(`${BASE_URL}/api/${activeThread}/introspect?level=2`)
        .then(res => res.json())
        .then(data => {
          setGenericModules(data.modules || {});
          setIdentityRows([]);
          setPhilosophyRows([]);
          setDataLoading(false);
        })
        .catch(() => {
          setGenericModules({});
          setDataLoading(false);
        });
    }
  }, [activeThread]);

  const formatValue = (value: any): string => {
    if (typeof value === 'string') return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return value.join(', ');
    if (typeof value === 'object' && value !== null) {
      if (value.value !== undefined) return formatValue(value.value);
      return JSON.stringify(value);
    }
    return String(value);
  };

  const totalItems = activeThread === 'identity' 
    ? identityRows.length 
    : activeThread === 'philosophy'
    ? philosophyRows.length
    : Object.values(genericModules).reduce((sum, arr) => sum + arr.length, 0);

  const renderGenericView = () => (
    <div className="thread-data">
      {Object.entries(genericModules).map(([moduleName, rows]) => (
        <div key={moduleName} className="module-section">
          <h3 className="module-name">{moduleName}</h3>
          <div className="thread-rows">
            {rows.map((row, i) => (
              <div key={row.key || i} className="thread-row">
                <div className="row-header">
                  <span className="row-key">{row.key}</span>
                  <span className="row-level">L{row.level}</span>
                  <span className="row-weight">{(row.weight * 100).toFixed(0)}%</span>
                </div>
                <div className="row-value">
                  {formatValue(row.data)}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );

  const renderReadme = () => (
    <div className="readme-content">
      <pre className="readme-markdown">{readmeContent}</pre>
    </div>
  );

  return (
    <div className="page-wrapper threads-page">
      <div className="page-header">
        <Link to="/" className="back-link">← Back</Link>
        <h1>🧵 Threads</h1>
      </div>

      <nav className="thread-nav">
        {loading ? (
          <div className="muted">Loading...</div>
        ) : (
          Object.values(threads).map(t => (
            <button
              key={t.name}
              className={`thread-tab ${activeThread === t.name ? 'active' : ''} ${t.status}`}
              onClick={() => setActiveThread(t.name)}
            >
              <span className="thread-icon">{THREAD_ICONS[t.name] || '🧵'}</span>
              <span className="thread-name">{t.name}</span>
              <span className={`thread-status-dot ${t.status}`} />
            </button>
          ))
        )}
      </nav>

      <div className="threads-layout">
        <main className="thread-content">
          {!activeThread ? (
            <div className="empty-state">Select a thread to view</div>
          ) : dataLoading ? (
            <div className="empty-state">Loading {activeThread}...</div>
          ) : DOC_THREADS.has(activeThread) && readmeContent ? (
            <>
              <div className="thread-data-header">
                <h2>{THREAD_ICONS[activeThread]} {activeThread}</h2>
                <span className="item-count">Documentation</span>
              </div>
              {renderReadme()}
            </>
          ) : totalItems === 0 && !DOC_THREADS.has(activeThread) && activeThread !== 'identity' && activeThread !== 'philosophy' && activeThread !== 'linking_core' && activeThread !== 'form' && activeThread !== 'reflex' && activeThread !== 'subconscious' ? (
            <div className="empty-state">
              <p>No data in {activeThread}</p>
              <p className="muted">{threads[activeThread]?.message}</p>
            </div>
          ) : (
            <>
              {activeThread === 'identity' ? (
                <div style={{ height: '100%', width: '100%' }}>
                  <IdentityProfilesPage />
                </div>
              ) : activeThread === 'linking_core' ? (
                <div style={{ height: '100%', width: '100%', minHeight: '600px' }}>
                  <ConceptGraph3D mode="ambient" />
                </div>
              ) : activeThread === 'log' ? (
                <div style={{ height: '100%', width: '100%', minHeight: '600px' }}>
                  <LogDashboard embedded />
                </div>
              ) : (
                <>
                  <div className="thread-data-header">
                    <h2>{THREAD_ICONS[activeThread]} {activeThread}</h2>
                    <span className="item-count">{totalItems} items</span>
                  </div>
                  
                  {activeThread === 'philosophy'
                    ? <PhilosophyProfilesPage />
                    : activeThread === 'form'
                    ? <ToolDashboard />
                    : activeThread === 'reflex'
                    ? <ReflexDashboard />
                    : activeThread === 'subconscious'
                    ? <SubconsciousDashboard />
                    : renderGenericView()}
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
};
