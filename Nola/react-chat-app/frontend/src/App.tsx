import { ChatContainer } from './components/Chat/ChatContainer'
import './App.css'

function App() {
  return (
    <div className="app">
      <div className="app-header">
        <h1>🧠 Nola</h1>
        <p>Personal AI with hierarchical memory</p>
      </div>
      
      <main className="app-main">
        <ChatContainer />
      </main>
      
      <footer className="app-footer">
        <p>Local-first • Your data stays on your machine • Powered by Ollama</p>
      </footer>
    </div>
  )
}

export default App
