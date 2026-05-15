import { NavLink, useNavigate } from 'react-router-dom'

export default function Nav() {
  const role = localStorage.getItem('role')
  const username = localStorage.getItem('username')
  const navigate = useNavigate()

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('username')
    navigate('/login')
    window.location.reload()
  }

  return (
    <nav className="app-nav">
      {role === 'admin' && <NavLink to="/" className={({ isActive }) => isActive ? 'active' : ''}>Dashboard</NavLink>}
      {role === 'admin' && <NavLink to="/invoice" className={({ isActive }) => isActive ? 'active' : ''}>Invoice</NavLink>}
      {role === 'admin' && <NavLink to="/properties" className={({ isActive }) => isActive ? 'active' : ''}>Properties</NavLink>}
      {role === 'admin' && <a href="/sales">Sales</a>}
      {role === 'admin' && <NavLink to="/users" className={({ isActive }) => isActive ? 'active' : ''}>Users</NavLink>}
      {role === 'admin' && <NavLink to="/tenant" className={({ isActive }) => isActive ? 'active' : ''}>Tenant</NavLink>}
      <span style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 12 }}>
        {username && <span style={{ color: '#888', fontSize: 13 }}>{username}</span>}
        <button onClick={logout} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: 13 }}>Logout</button>
      </span>
    </nav>
  )
}
