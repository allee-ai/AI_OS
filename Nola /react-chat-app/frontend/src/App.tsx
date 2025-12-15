import { ChatContainer } from './components/Chat/ChatContainer'
import './App.css'

function App() {
  return (
    <div className="app">
      <div className="app-header">
        <h1>React Chat Demo</h1>
        <p>Local-first AI chat with intelligent context management</p>
      </div>
      
      <main className="app-main">
        <ChatContainer />
      </main>
      
      <footer className="app-footer">
        <p>Powered by Demo Backend AI • Real-time WebSocket Connection</p>
      </footer>
    </div>
  )
}

export default App
