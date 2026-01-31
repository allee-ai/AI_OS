import { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
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
import './App.css'

// App mode hook - inlined for simplicity
const useAppMode = () => {
  const [modeInfo, setModeInfo] = useState({ mode: 'personal' as const, is_demo: false });
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetch('/api/db-mode/mode')
      .then(res => res.ok ? res.json() : null)
      .then(data => data && setModeInfo({ mode: data.mode, is_demo: data.mode === 'demo' }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  
  return { ...modeInfo, loading };
};

function App() {
  const { loading, is_demo } = useAppMode();
  
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

  return (
    <BrowserRouter>
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
          <Route path="/dev" element={<DevDashboard />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/:section" element={<SettingsPage />} />
        </Routes>
        <footer className="app-footer">
          <p>Local-first • Your data stays on your machine • Powered by Ollama</p>
          <DatabaseToggle />
        </footer>
      </div>
    </BrowserRouter>
  )
}

export default App
