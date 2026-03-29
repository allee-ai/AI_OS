import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { IS_DEMO } from './config/api'
// Modules
import { Dashboard, ContactPage } from './modules/home'
import { ChatPage } from './modules/chat/pages/ChatPage'
import { DatabaseToggle } from './modules/chat/components/DatabaseToggle'
import { FeedsPage } from './modules/feeds/pages/FeedsPage'
import { ThreadsPage } from './modules/threads/pages/ThreadsPage'
import IdentityProfilesPage from './modules/threads/identity/pages/ProfilesPage'
import PhilosophyProfilesPage from './modules/threads/philosophy/pages/ProfilesPage'
import { WorkspacePage } from './modules/workspace/pages/WorkspacePage'
import { DocsPage } from './modules/docs/pages/DocsPage'
import { SettingsPage } from './modules/services/pages/SettingsPage'
import { DevDashboard } from './modules/finetune/pages/DevDashboard'
import { SectionDetailPage } from './modules/finetune/pages/SectionDetailPage'
import { SubconsciousPage } from './modules/subconscious'
import { EvalDashboard } from './modules/eval'
import { ExperimentDashboard } from './modules/experiments'
import { SetupWizard } from './components/SetupWizard'
import './App.css'

// App mode hook - inlined for simplicity
const useAppMode = () => {
  const [modeInfo, setModeInfo] = useState({ mode: 'personal' as const, is_demo: IS_DEMO });
  const [setupDone, setSetupDone] = useState<boolean | null>(IS_DEMO ? true : null);
  const [loading, setLoading] = useState(!IS_DEMO);
  
  useEffect(() => {
    if (IS_DEMO) return; // SW handles API responses in demo mode
    Promise.all([
      fetch('/api/db-mode/mode').then(res => res.ok ? res.json() : null).catch(() => null),
      fetch('/api/models/setup/status').then(res => res.ok ? res.json() : null).catch(() => null),
    ]).then(([modeData, setupData]) => {
      if (modeData) setModeInfo({ mode: modeData.mode, is_demo: modeData.mode === 'demo' });
      setSetupDone(setupData ? setupData.configured : true);
    }).finally(() => setLoading(false));
  }, []);

  const recheckSetup = () => {
    fetch('/api/models/setup/status')
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setSetupDone(data.configured))
      .catch(() => setSetupDone(true));
  };
  
  return { ...modeInfo, loading, setupDone, recheckSetup };
};

function App() {
  const { loading, is_demo, setupDone, recheckSetup } = useAppMode();
  
  if (loading) {
    return (
      <div className="app loading-app">
        <div className="loading-container">
          <div className="startup-logo">🧠</div>
          <p>Loading AI OS...</p>
        </div>
      </div>
    );
  }

  if (setupDone === false) {
    return <SetupWizard onComplete={recheckSetup} />;
  }

  return (
    <BrowserRouter basename={import.meta.env.BASE_URL}>
      {is_demo && (
        <div style={{
          backgroundColor: '#4a9eff',
          color: '#fff',
          textAlign: 'center',
          padding: '4px',
          fontSize: '0.8rem',
          fontWeight: 'bold',
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 9999
        }}>
          🎮 DEMO MODE
        </div>
      )}
      <div className="app" style={is_demo ? { marginTop: '24px' } : {}}>        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/feeds" element={<FeedsPage />} />
          <Route path="/threads" element={<ThreadsPage />} />
          <Route path="/profiles" element={<IdentityProfilesPage />} />
          <Route path="/identity" element={<IdentityProfilesPage />} />
          <Route path="/philosophy" element={<PhilosophyProfilesPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/training" element={<DevDashboard />} />
          <Route path="/training/:module/:section" element={<SectionDetailPage />} />
          <Route path="/subconscious" element={<SubconsciousPage />} />
          <Route path="/eval" element={<EvalDashboard />} />
          <Route path="/experiments" element={<ExperimentDashboard />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/:section" element={<SettingsPage />} />
        </Routes>
        <footer className="app-footer">
          <p>Local-first • Your data stays on your machine</p>
          <DatabaseToggle />
        </footer>
      </div>
    </BrowserRouter>
  )
}

export default App
