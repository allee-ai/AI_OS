import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { 
  MemoryDashboard, 
  ConsolidationDashboard, 
  FactExtractorDashboard,
  KernelDashboard,
  AgentDashboard 
} from '../components/Services';
import './SettingsPage.css';

interface ServiceInfo {
  id: string;
  name: string;
  description: string;
  icon: string;
  status: string;
  message?: string;
  config?: {
    enabled: boolean;
    settings: Record<string, unknown>;
  };
}

interface UnsavedChangesDialogProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

const UnsavedChangesDialog = ({ isOpen, onConfirm, onCancel }: UnsavedChangesDialogProps) => {
  if (!isOpen) return null;
  
  return (
    <div className="dialog-overlay">
      <div className="dialog">
        <h3>Unsaved Changes</h3>
        <p>You have unsaved changes. Are you sure you want to leave?</p>
        <div className="dialog-actions">
          <button className="btn-secondary" onClick={onCancel}>Cancel</button>
          <button className="btn-primary" onClick={onConfirm}>Leave Anyway</button>
        </div>
      </div>
    </div>
  );
};

export const SettingsPage = () => {
  const { section } = useParams<{ section?: string }>();
  const navigate = useNavigate();
  
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [pendingNavigation, setPendingNavigation] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);
  const [restartMessage, setRestartMessage] = useState<string | null>(null);
  
  const activeSection = section || 'general';

  // Fetch services once on mount
  useEffect(() => {
    const fetchServices = async () => {
      try {
        const res = await fetch('http://localhost:8000/api/services/');
        if (res.ok) {
          const data = await res.json();
          setServices(data);
        }
      } catch (err) {
        console.error('Failed to fetch services:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchServices();
  }, []);

  const handleNavigation = useCallback((path: string) => {
    if (hasUnsavedChanges) {
      setPendingNavigation(path);
      setShowDialog(true);
    } else {
      navigate(path);
    }
  }, [hasUnsavedChanges, navigate]);

  const handleDialogConfirm = () => {
    setShowDialog(false);
    setHasUnsavedChanges(false);
    if (pendingNavigation) {
      navigate(pendingNavigation);
      setPendingNavigation(null);
    }
  };

  const handleDialogCancel = () => {
    setShowDialog(false);
    setPendingNavigation(null);
  };

  const handleRestart = async () => {
    setRestarting(true);
    setRestartMessage(null);
    
    try {
      const res = await fetch('http://localhost:8000/api/services/restart', {
        method: 'POST'
      });
      
      if (res.ok) {
        const data = await res.json();
        setRestartMessage(data.message);
        setHasUnsavedChanges(false);
        
        // Refresh services status
        const servicesRes = await fetch('http://localhost:8000/api/services/');
        if (servicesRes.ok) {
          setServices(await servicesRes.json());
        }
      } else {
        const error = await res.json();
        setRestartMessage(`Error: ${error.detail}`);
      }
    } catch (err) {
      setRestartMessage('Failed to restart services');
    } finally {
      setRestarting(false);
    }
  };

  const handleSaveServiceConfig = async (serviceId: string, config: { enabled: boolean; settings: Record<string, unknown> }) => {
    try {
      const res = await fetch(`http://localhost:8000/api/services/${serviceId}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        setHasUnsavedChanges(false);
        // Refresh services list
        const servicesRes = await fetch('http://localhost:8000/api/services/');
        if (servicesRes.ok) {
          setServices(await servicesRes.json());
        }
      }
    } catch (err) {
      console.error('Failed to save config:', err);
    }
  };

  const renderContent = () => {
    if (activeSection === 'general') {
      return <GeneralSettings onChangesMade={() => setHasUnsavedChanges(true)} />;
    }
    
    // Find the service
    const service = services.find(s => s.id === activeSection);
    if (!service) {
      return <div className="settings-empty">Select a section from the sidebar</div>;
    }

    const dashboardProps = {
      config: service.config || null,
      status: service.status,
      message: service.message,
      onChangesMade: () => setHasUnsavedChanges(true),
      onSave: (config: { enabled: boolean; settings: Record<string, unknown> }) => 
        handleSaveServiceConfig(service.id, config)
    };

    switch (service.id) {
      case 'memory':
        return <MemoryDashboard {...dashboardProps} />;
      case 'consolidation':
        return <ConsolidationDashboard {...dashboardProps} />;
      case 'fact-extractor':
        return <FactExtractorDashboard {...dashboardProps} />;
      case 'kernel':
        return <KernelDashboard {...dashboardProps} />;
      case 'agent':
        return <AgentDashboard {...dashboardProps} />;
      default:
        return <GenericServiceDashboard service={service} onChangesMade={() => setHasUnsavedChanges(true)} />;
    }
  };

  return (
    <div className="settings-page">
      <UnsavedChangesDialog
        isOpen={showDialog}
        onConfirm={handleDialogConfirm}
        onCancel={handleDialogCancel}
      />
      
      <aside className="settings-sidebar">
        <div className="sidebar-header">
          <Link to="/" className="back-link">← Dashboard</Link>
          <h2>Settings</h2>
        </div>
        
        <nav className="sidebar-nav">
          <button
            className={`sidebar-item ${activeSection === 'general' ? 'active' : ''}`}
            onClick={() => handleNavigation('/settings/general')}
          >
            <span className="sidebar-icon">⚙️</span>
            <span>General</span>
          </button>
          
          <div className="sidebar-section-header">Services</div>
          
          {loading ? (
            <div className="sidebar-loading">Loading...</div>
          ) : (
            services.map(service => (
              <button
                key={service.id}
                className={`sidebar-item ${activeSection === service.id ? 'active' : ''}`}
                onClick={() => handleNavigation(`/settings/${service.id}`)}
              >
                <span className="sidebar-icon">{service.icon}</span>
                <span>{service.name}</span>
                <span className={`status-dot ${service.status}`} />
              </button>
            ))
          )}
        </nav>
        
        <div className="sidebar-footer">
          {hasUnsavedChanges && (
            <p className="unsaved-warning">⚠️ Unsaved changes</p>
          )}
          <button 
            className="restart-btn"
            onClick={handleRestart}
            disabled={restarting}
          >
            {restarting ? 'Restarting...' : '🔄 Restart Services'}
          </button>
          {restartMessage && (
            <p className={`restart-message ${restartMessage.includes('Error') ? 'error' : 'success'}`}>
              {restartMessage}
            </p>
          )}
        </div>
      </aside>
      
      <main className="settings-content">
        {renderContent()}
      </main>
    </div>
  );
};

interface GeneralSettingsProps {
  onChangesMade: () => void;
}

const GeneralSettings = ({ onChangesMade }: GeneralSettingsProps) => {
  return (
    <div className="settings-panel">
      <h1>General Settings</h1>
      <p className="settings-description">Configure UI preferences and general options.</p>
      
      <section className="settings-section">
        <h3>Appearance</h3>
        <div className="setting-row">
          <label>Theme</label>
          <select onChange={onChangesMade}>
            <option value="dark">Dark</option>
            <option value="light">Light</option>
            <option value="system">System</option>
          </select>
        </div>
      </section>
      
      <section className="settings-section">
        <h3>Model</h3>
        <div className="setting-row">
          <label>Default Model</label>
          <select onChange={onChangesMade}>
            <option value="llama3.2">llama3.2</option>
            <option value="mistral">mistral</option>
            <option value="qwen2.5">qwen2.5</option>
          </select>
        </div>
      </section>
      
      <section className="settings-section">
        <h3>Notifications</h3>
        <div className="setting-row">
          <label>Enable notifications</label>
          <input type="checkbox" onChange={onChangesMade} />
        </div>
      </section>
    </div>
  );
};

interface GenericServiceDashboardProps {
  service: ServiceInfo;
  onChangesMade: () => void;
}

const GenericServiceDashboard = ({ service, onChangesMade }: GenericServiceDashboardProps) => {
  return (
    <div className="settings-panel">
      <div className="service-header">
        <span className="service-icon">{service.icon}</span>
        <div>
          <h1>{service.name}</h1>
          <p className="settings-description">{service.description}</p>
        </div>
      </div>
      
      <section className="settings-section">
        <h3>Status</h3>
        <div className="status-card">
          <div className={`status-indicator-large ${service.status}`}>
            <span className="status-dot-large" />
            <span className="status-text">{service.status}</span>
          </div>
          {service.message && (
            <p className="status-message">{service.message}</p>
          )}
        </div>
      </section>
      
      <section className="settings-section">
        <h3>Configuration</h3>
        <div className="setting-row">
          <label>Enabled</label>
          <input 
            type="checkbox" 
            checked={service.config?.enabled ?? true}
            onChange={onChangesMade}
          />
        </div>
        <p className="setting-hint">
          Custom dashboard for this service coming soon.
        </p>
      </section>
    </div>
  );
};
