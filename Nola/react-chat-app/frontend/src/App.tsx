import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { ChatPage } from './pages/ChatPage'
import { StimuliPage } from './pages/StimuliPage'
import { ThreadsPage } from './pages/ThreadsPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { DocsPage } from './pages/DocsPage'
import { ContactPage } from './pages/ContactPage'
import { SettingsPage } from './pages/SettingsPage'
import { StartupPage } from './pages/StartupPage'
import { DevDashboard } from './pages/DevDashboard'
import { ProfilesPage } from './pages/ProfilesPage'
import { useNolaMode } from './hooks/useNolaMode'
import './App.css'

function App() {
  const { mode_set, loading, is_demo } = useNolaMode();
  
  if (loading) {
    return (
      <div className="app loading-app">
        <div className="loading-container">
          <div className="startup-logo">🧠</div>
          <p>Loading Nola...</p>
        </div>
      </div>
    );
  }

  return (
    <BrowserRouter>
      {is_demo && (
        <div style={{
          backgroundColor: '#ff9800',
          color: '#000',
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
          ⚠️ DEMO MODE: Data will be reset on restart
        </div>
      )}
      <div className="app" style={is_demo ? { marginTop: '24px' } : {}}>
        <Routes>
          <Route path="/startup" element={<StartupPage />} />
          <Route path="/" element={mode_set ? <Dashboard /> : <Navigate to="/startup" replace />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/stimuli" element={<StimuliPage />} />
          <Route path="/threads" element={<ThreadsPage />} />
          <Route path="/profiles" element={<ProfilesPage />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/dev" element={<DevDashboard />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/settings/:section" element={<SettingsPage />} />
        </Routes>
        
        {mode_set && (
          <footer className="app-footer">
            <p>Local-first • Your data stays on your machine • Powered by Ollama</p>
          </footer>
        )}
      </div>
    </BrowserRouter>
  )
}

export default App
