import { useEffect, useState } from 'react'
import { api } from '../api'

interface User {
  id: number
  username: string
  role: string
  created_at: string
}

export default function Users() {
  const [users, setUsers] = useState<User[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [newUsername, setNewUsername] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [newRole, setNewRole] = useState<'sales' | 'admin'>('sales')
  const [error, setError] = useState('')
  const [resetId, setResetId] = useState<number | null>(null)
  const [resetPwd, setResetPwd] = useState('')
  const me = localStorage.getItem('username') || ''

  const load = () => {
    api.getUsers().then(setUsers).catch(e => setError(String(e)))
  }
  useEffect(load, [])

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    if (!newUsername.trim() || newPassword.length < 4) {
      setError('Username required, password must be at least 4 chars')
      return
    }
    try {
      await api.createUser({ username: newUsername.trim(), password: newPassword, role: newRole })
      setNewUsername(''); setNewPassword(''); setNewRole('sales'); setShowAdd(false)
      load()
    } catch (e: any) {
      setError(e?.message || 'Failed to create user')
    }
  }

  const handleReset = async (id: number) => {
    if (resetPwd.length < 4) { setError('Password must be at least 4 chars'); return }
    await api.resetUserPassword(id, resetPwd)
    setResetId(null); setResetPwd('')
    load()
  }

  const handleDelete = async (u: User) => {
    if (!confirm(`Delete user ${u.username}? They won't be able to log in anymore.`)) return
    try {
      await api.deleteUser(u.id)
      load()
    } catch (e: any) {
      setError(e?.message || 'Failed to delete')
    }
  }

  return (
    <>
      <div className="topbar">
        <h1>Users</h1>
      </div>

      <div className="section">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <span style={{ color: '#666', fontSize: 14 }}>{users.length} {users.length === 1 ? 'user' : 'users'}</span>
          <button className="btn btn-sm btn-primary" style={{ marginLeft: 'auto' }} onClick={() => setShowAdd(!showAdd)}>
            {showAdd ? 'Cancel' : '+ Add user'}
          </button>
        </div>

        {showAdd && (
          <form onSubmit={handleAdd} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, padding: 12, background: '#f8f9fa', borderRadius: 6 }}>
            <input placeholder="Username" value={newUsername} onChange={e => setNewUsername(e.target.value)} autoComplete="off" style={{ flex: '1 1 160px' }} required />
            <input type="text" placeholder="Password" value={newPassword} onChange={e => setNewPassword(e.target.value)} autoComplete="off" style={{ flex: '1 1 160px' }} required />
            <select value={newRole} onChange={e => setNewRole(e.target.value as any)} style={{ width: 120 }}>
              <option value="sales">Sales</option>
              <option value="admin">Admin</option>
            </select>
            <button className="btn btn-sm btn-primary" type="submit">Create</button>
          </form>
        )}

        {error && <p style={{ color: '#dc3545', fontSize: 14 }}>{error}</p>}

        <table>
          <thead>
            <tr>
              <th>Username</th>
              <th>Role</th>
              <th>Created</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id}>
                <td>
                  <strong>{u.username}</strong>
                  {u.username === me && <span style={{ color: '#888', fontSize: 12, marginLeft: 6 }}>(you)</span>}
                </td>
                <td>
                  <span className={u.role === 'admin' ? 'badge badge-scheduled' : ''}
                        style={{ padding: '2px 8px', borderRadius: 4, fontSize: 12, background: u.role === 'admin' ? '#e3f2fd' : '#fff3cd', color: u.role === 'admin' ? '#1565c0' : '#856404' }}>
                    {u.role}
                  </span>
                </td>
                <td style={{ color: '#888', fontSize: 13 }}>
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  {resetId === u.id ? (
                    <>
                      <input type="text" placeholder="New password" value={resetPwd} onChange={e => setResetPwd(e.target.value)} style={{ width: 140 }} />{' '}
                      <button className="btn btn-sm btn-primary" onClick={() => handleReset(u.id)}>Save</button>{' '}
                      <button className="btn btn-sm" onClick={() => { setResetId(null); setResetPwd('') }}>Cancel</button>
                    </>
                  ) : (
                    <>
                      <button className="btn btn-sm" onClick={() => { setResetId(u.id); setResetPwd('') }}>Reset password</button>{' '}
                      {u.username !== me && (
                        <button className="btn btn-sm btn-danger" onClick={() => handleDelete(u)}>×</button>
                      )}
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <p style={{ color: '#888', fontSize: 13, marginTop: 16 }}>
          <strong>Sales</strong> users can only access the iPad sales page (<a href="/sales">/sales</a>).<br/>
          <strong>Admin</strong> users have full access including this page.
        </p>
      </div>
    </>
  )
}
