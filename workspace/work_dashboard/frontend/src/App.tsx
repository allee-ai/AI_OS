import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Nav from './components/Nav'
import Dashboard from './pages/Dashboard'
import TenantPortal from './pages/TenantPortal'
import Properties from './pages/Properties'
import Login from './pages/Login'
import Users from './pages/Users'
import Invoice from './pages/Invoice'

function ConditionalNav() {
  const { pathname } = useLocation()
  const token = localStorage.getItem('token')
  if (!token) return null
  if (pathname.startsWith('/invoice')) return null
  return <Nav />
}

function RequireAuth({ children, allowedRoles }: { children: React.ReactNode; allowedRoles: string[] }) {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role') || ''
  if (!token) return <Navigate to="/login" />
  if (!allowedRoles.includes(role)) {
    if (role === 'sales') {
      window.location.href = '/sales'
      return null
    }
    return <Navigate to="/login" />
  }
  return <>{children}</>
}

export default function App() {
  const token = localStorage.getItem('token')

  return (
    <BrowserRouter>
      <div className="page">
        <ConditionalNav />
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/tenant" element={<TenantPortal />} />
          <Route path="/" element={<RequireAuth allowedRoles={['admin']}><Dashboard /></RequireAuth>} />
          <Route path="/invoice" element={<RequireAuth allowedRoles={['admin']}><Invoice /></RequireAuth>} />
          <Route path="/properties" element={<RequireAuth allowedRoles={['admin']}><Properties /></RequireAuth>} />
          <Route path="/users" element={<RequireAuth allowedRoles={['admin']}><Users /></RequireAuth>} />
          <Route path="*" element={<Navigate to={token ? '/' : '/login'} />} />
        </Routes>
      </div>
    </BrowserRouter>
  )
}
