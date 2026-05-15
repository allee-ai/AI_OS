import { useEffect, useState } from 'react'
import { api, BalanceSummary, Job } from '../api'
import SyncButton from '../components/SyncButton'

export default function Dashboard() {
  const [balance, setBalance] = useState<BalanceSummary | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [payments, setPayments] = useState<any[]>([])
  const [properties, setProperties] = useState<any[]>([])
  const [tab, setTab] = useState<'completed' | 'scheduled' | 'pending'>('scheduled')

  // Add job form
  const [showAdd, setShowAdd] = useState(false)
  const [newPropId, setNewPropId] = useState<number | ''>('')
  const [newDesc, setNewDesc] = useState('')
  const [newCost, setNewCost] = useState('')
  const [newType, setNewType] = useState<'flat' | 'hourly'>('flat')
  const [newHours, setNewHours] = useState('')
  const [newStatus, setNewStatus] = useState('pending')

  // Add deposit form
  const [showDeposit, setShowDeposit] = useState(false)
  const [depAmount, setDepAmount] = useState('')
  const [depDate, setDepDate] = useState('')
  const [depNote, setDepNote] = useState('')

  // Inline edit
  const [editId, setEditId] = useState<number | null>(null)
  const [editDesc, setEditDesc] = useState('')
  const [editCost, setEditCost] = useState('')
  const [editType, setEditType] = useState<'flat' | 'hourly'>('flat')
  const [editHours, setEditHours] = useState('')
  const [editStatus, setEditStatus] = useState('')

  const load = () => {
    api.getBalance().then(setBalance).catch(console.error)
    api.getJobs().then(setJobs).catch(console.error)
    api.getPayments().then(setPayments).catch(console.error)
    api.getProperties().then(setProperties).catch(console.error)
  }

  useEffect(load, [])

  if (!balance) return <p>Loading…</p>

  const jobTotal = (j: Job) => j.billing_type === 'hourly' && j.hours ? j.cost * j.hours : j.cost

  const filtered = jobs.filter(j => tab === 'pending' ? (j.status === 'pending' || j.status === 'pushed') : j.status === tab)
  const tabTotal = filtered.reduce((t, j) => t + jobTotal(j), 0)

  const handleAddJob = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPropId || !newDesc.trim()) return
    await api.createJob({
      property_id: newPropId as number,
      description: newDesc.trim(),
      cost: parseFloat(newCost) || 0,
      billing_type: newType,
      hours: parseFloat(newHours) || 0,
      status: newStatus,
    })
    setNewDesc(''); setNewCost(''); setNewHours(''); setShowAdd(false)
    load()
  }

  const handleAddDeposit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!depAmount || !depDate) return
    await api.createPayment({ amount: parseFloat(depAmount), date: depDate, note: depNote })
    setDepAmount(''); setDepDate(''); setDepNote(''); setShowDeposit(false)
    load()
  }

  const handleDeleteJob = async (id: number) => {
    await api.deleteJob(id)
    load()
  }

  const startEdit = (j: Job) => {
    setEditId(j.id)
    setEditDesc(j.description)
    setEditCost(String(j.cost))
    setEditType(j.billing_type)
    setEditHours(String(j.hours))
    setEditStatus(j.status)
  }

  const cancelEdit = () => setEditId(null)

  const saveEdit = async () => {
    if (!editId) return
    await api.updateJob(editId, {
      description: editDesc.trim(),
      cost: parseFloat(editCost) || 0,
      billing_type: editType,
      hours: parseFloat(editHours) || 0,
      status: editStatus,
    })
    setEditId(null)
    load()
  }

  const handleStatusChange = async (id: number, status: string) => {
    await api.updateJob(id, { status })
    load()
  }

  const handleDeletePayment = async (id: number) => {
    await api.deletePayment(id)
    load()
  }

  const handlePush = async (id: number) => {
    await api.updateJob(id, { status: 'pushed' })
    load()
  }

  return (
    <>
      <div className="topbar">
        <h1>Dashboard</h1>
      </div>

      <div className="cards">
        <div className="card">
          <div className="label">Deposits</div>
          <div className="value">${balance.deposits.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="label">Completed</div>
          <div className="value">${balance.completed.toLocaleString()}</div>
        </div>
        <div className="card">
          <div className="label">Scheduled</div>
          <div className="value">${balance.scheduled.toLocaleString()}</div>
        </div>
        <div className="card" style={{ borderLeft: `4px solid ${balance.balance >= 0 ? '#28a745' : '#dc3545'}` }}>
          <div className="label">Balance</div>
          <div className="value" style={{ color: balance.balance >= 0 ? '#28a745' : '#dc3545' }}>
            ${balance.balance.toLocaleString()}
          </div>
        </div>
      </div>

      {/* Job tabs */}
      <div className="section">
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'center' }}>
          {(['scheduled', 'pending', 'completed'] as const).map(s => (
            <button
              key={s}
              className={`btn btn-sm ${tab === s ? 'btn-primary' : ''}`}
              onClick={() => setTab(s)}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
          <span style={{ marginLeft: 'auto', fontSize: 13, color: '#666' }}>
            {filtered.length} tasks — ${tabTotal.toLocaleString()}
          </span>
          <button className="btn btn-sm" onClick={() => setShowAdd(!showAdd)}>+ Add</button>
        </div>

        {showAdd && (
          <form onSubmit={handleAddJob} style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12, padding: 12, background: '#f8f9fa', borderRadius: 6 }}>
            <select value={newPropId} onChange={e => setNewPropId(Number(e.target.value) || '')} required style={{ flex: '1 1 180px' }}>
              <option value="">Property…</option>
              {properties.map(p => <option key={p.id} value={p.id}>{p.address}</option>)}
            </select>
            <input placeholder="Description" value={newDesc} onChange={e => setNewDesc(e.target.value)} required style={{ flex: '2 1 200px' }} />
            <select value={newType} onChange={e => setNewType(e.target.value as any)} style={{ width: 90 }}>
              <option value="flat">Flat</option>
              <option value="hourly">Hourly</option>
            </select>
            <input type="number" placeholder={newType === 'flat' ? 'Price' : 'Rate/hr'} value={newCost} onChange={e => setNewCost(e.target.value)} style={{ width: 80 }} />
            {newType === 'hourly' && <input type="number" placeholder="Hours" value={newHours} onChange={e => setNewHours(e.target.value)} step="0.25" style={{ width: 70 }} />}
            <select value={newStatus} onChange={e => setNewStatus(e.target.value)} style={{ width: 110 }}>
              <option value="pending">Pending</option>
              <option value="scheduled">Scheduled</option>
              <option value="completed">Completed</option>
            </select>
            <button className="btn btn-sm btn-primary" type="submit">Save</button>
          </form>
        )}

        <table>
          <thead>
            <tr>
              <th>Property</th>
              <th>Description</th>
              <th>Type</th>
              <th className="r">Cost</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(j => editId === j.id ? (
              <tr key={j.id} style={{ background: '#f8f9fa' }}>
                <td>{j.property_address}</td>
                <td><input value={editDesc} onChange={e => setEditDesc(e.target.value)} style={{ width: '100%' }} /></td>
                <td>
                  <select value={editType} onChange={e => setEditType(e.target.value as any)} style={{ width: 80 }}>
                    <option value="flat">Flat</option>
                    <option value="hourly">Hourly</option>
                  </select>
                  {editType === 'hourly' && <input type="number" value={editHours} onChange={e => setEditHours(e.target.value)} step="0.25" style={{ width: 60, marginLeft: 4 }} placeholder="hrs" />}
                </td>
                <td><input type="number" value={editCost} onChange={e => setEditCost(e.target.value)} style={{ width: 80, textAlign: 'right' }} /></td>
                <td>
                  <select value={editStatus} onChange={e => setEditStatus(e.target.value)} style={{ width: 100 }}>
                    <option value="pending">Pending</option>
                    <option value="scheduled">Scheduled</option>
                    <option value="completed">Completed</option>
                  </select>
                </td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn btn-sm btn-primary" onClick={saveEdit}>Save</button>{' '}
                  <button className="btn btn-sm" onClick={cancelEdit}>Cancel</button>
                </td>
              </tr>
            ) : (
              <tr key={j.id}>
                <td>{j.property_address}</td>
                <td>{j.description}</td>
                <td>{j.billing_type}{j.billing_type === 'hourly' && j.hours ? ` (${j.hours}h @ $${j.cost})` : ''}</td>
                <td className="r">${jobTotal(j).toLocaleString()}</td>
                <td>{j.status === 'pushed' && <span className="badge badge-scheduled">Pushed</span>}</td>
                <td style={{ whiteSpace: 'nowrap' }}>
                  <button className="btn btn-sm" onClick={() => startEdit(j)} title="Edit">✎</button>{' '}
                  {tab === 'pending' && j.status !== 'pushed' && (
                    <button className="btn btn-sm" onClick={() => handlePush(j.id)} title="Push to Jake for approval">Push →</button>
                  )}
                  {tab === 'scheduled' && (
                    <button className="btn btn-sm" onClick={() => handleStatusChange(j.id, 'completed')} title="Complete">✓</button>
                  )}{' '}
                  <button className="btn btn-sm btn-danger" onClick={() => handleDeleteJob(j.id)} title="Delete">×</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Deposits */}
      <div className="section">
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 12 }}>
          <h2 style={{ margin: 0 }}>Deposits</h2>
          <button className="btn btn-sm" style={{ marginLeft: 'auto' }} onClick={() => setShowDeposit(!showDeposit)}>+ Add</button>
        </div>

        {showDeposit && (
          <form onSubmit={handleAddDeposit} style={{ display: 'flex', gap: 8, marginBottom: 12, padding: 12, background: '#f8f9fa', borderRadius: 6 }}>
            <input type="number" placeholder="Amount" value={depAmount} onChange={e => setDepAmount(e.target.value)} required style={{ width: 100 }} />
            <input type="text" placeholder="Date (e.g. 4/14)" value={depDate} onChange={e => setDepDate(e.target.value)} required style={{ width: 100 }} />
            <input type="text" placeholder="Note" value={depNote} onChange={e => setDepNote(e.target.value)} style={{ flex: 1 }} />
            <button className="btn btn-sm btn-primary" type="submit">Save</button>
          </form>
        )}

        <table>
          <thead>
            <tr><th>Date</th><th className="r">Amount</th><th>Note</th><th></th></tr>
          </thead>
          <tbody>
            {payments.map(p => (
              <tr key={p.id}>
                <td>{p.date}</td>
                <td className="r">${parseFloat(p.amount).toLocaleString()}</td>
                <td>{p.note}</td>
                <td><button className="btn btn-sm btn-danger" onClick={() => handleDeletePayment(p.id)}>×</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="app-footer">
        <SyncButton />
      </div>
    </>
  )
}
