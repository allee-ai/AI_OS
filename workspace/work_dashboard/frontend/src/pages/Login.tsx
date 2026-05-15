import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const res = await api.login(username, password)
      localStorage.setItem('token', res.token)
      localStorage.setItem('role', res.role)
      localStorage.setItem('username', res.username)
      if (res.role === 'sales') {
        window.location.href = '/sales'
      } else {
        navigate('/')
      }
    } catch {
      setError('Invalid credentials')
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: '80px auto' }}>
      <h1 style={{ fontSize: 20, marginBottom: 20 }}>Sign In</h1>
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <input type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} autoComplete="username" />
        <input type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} autoComplete="current-password" />
        {error && <p style={{ color: '#dc3545', margin: 0, fontSize: 14 }}>{error}</p>}
        <button className="btn btn-primary" type="submit">Sign In</button>
      </form>
    </div>
  )
}
