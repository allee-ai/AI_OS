import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { ChatPage } from './pages/ChatPage'
import { FeedsPage } from './pages/FeedsPage'
import { ThreadsPage } from './pages/ThreadsPage'
import { WorkspacePage } from './pages/WorkspacePage'
import { DocsPage } from './pages/DocsPage'
import { ContactPage } from './pages/ContactPage'
import { SettingsPage } from './pages/SettingsPage'
import { DevDashboard } from './pages/DevDashboard'
import ProfilesPage from './pages/ProfilesPage'
import { DatabaseToggle } from './components/Chat/DatabaseToggle'
import { useAppMode } from './hooks/useAppMode'
import './App.css'

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
          <Route path="/profiles" element={<ProfilesPage />} />
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
