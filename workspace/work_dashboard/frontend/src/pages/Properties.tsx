import { useEffect, useState } from 'react'
import { api } from '../api'

interface Property {
  id: number
  address: string
  owner_name: string
  tenant_url_slug: string | null
  access_notes: string | null
}

export default function Properties() {
  const [props, setProps] = useState<Property[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [editId, setEditId] = useState<number | null>(null)

  // Form fields
  const [address, setAddress] = useState('')
  const [ownerName, setOwnerName] = useState('Jake')
  const [slug, setSlug] = useState('')
  const [notes, setNotes] = useState('')

  const load = () => { api.getProperties().then(setProps).catch(console.error) }
  useEffect(load, [])

  const resetForm = () => {
    setAddress(''); setOwnerName('Jake'); setSlug(''); setNotes('')
    setShowAdd(false); setEditId(null)
  }

  const startEdit = (p: Property) => {
    setEditId(p.id)
    setAddress(p.address)
    setOwnerName(p.owner_name)
    setSlug(p.tenant_url_slug || '')
    setNotes(p.access_notes || '')
    setShowAdd(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!address.trim()) return
    const data = {
      address: address.trim(),
      owner_name: ownerName.trim() || 'Jake',
      tenant_url_slug: slug.trim() || null,
      access_notes: notes.trim() || null,
    }
    if (editId) {
      await api.updateProperty(editId, data)
    } else {
      await api.createProperty(data)
    }
    resetForm()
    load()
  }

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this property?')) return
    try {
      await api.deleteProperty(id)
      load()
    } catch (err: any) {
      alert(err.message || 'Cannot delete — property has jobs')
    }
  }

  return (
    <>
      <div className="topbar">
        <h1>Properties</h1>
        <button className="btn btn-primary" onClick={() => { resetForm(); setShowAdd(true) }}>+ Add Property</button>
      </div>

      {showAdd && (
        <div className="section">
          <h2>{editId ? 'Edit Property' : 'New Property'}</h2>
          <form onSubmit={handleSubmit} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
            <div>
              <label style={{ fontSize: 11, color: '#888' }}>Address</label>
              <input value={address} onChange={e => setAddress(e.target.value)} placeholder="123 Main St" required />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#888' }}>Owner Name</label>
              <input value={ownerName} onChange={e => setOwnerName(e.target.value)} placeholder="Jake" />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#888' }}>Tenant URL Slug</label>
              <input value={slug} onChange={e => setSlug(e.target.value)} placeholder="123-main-st" />
            </div>
            <div>
              <label style={{ fontSize: 11, color: '#888' }}>Access Notes</label>
              <input value={notes} onChange={e => setNotes(e.target.value)} placeholder="Gate code, lockbox, etc." />
            </div>
            <div style={{ gridColumn: '1 / -1', display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" type="submit">{editId ? 'Save' : 'Add'}</button>
              <button className="btn" type="button" onClick={resetForm}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      <div className="section">
        <table>
          <thead>
            <tr>
              <th>Address</th>
              <th>Owner</th>
              <th>Tenant Slug</th>
              <th>Access Notes</th>
              <th style={{ width: 120 }}></th>
            </tr>
          </thead>
          <tbody>
            {props.map(p => (
              <tr key={p.id}>
                <td>{p.address}</td>
                <td>{p.owner_name}</td>
                <td>{p.tenant_url_slug || '—'}</td>
                <td>{p.access_notes || '—'}</td>
                <td style={{ display: 'flex', gap: 4 }}>
                  <button className="btn btn-sm" onClick={() => startEdit(p)}>Edit</button>
                  <button className="btn btn-sm btn-danger" onClick={() => handleDelete(p.id)}>Delete</button>
                </td>
              </tr>
            ))}
            {props.length === 0 && (
              <tr><td colSpan={5} style={{ color: '#888', textAlign: 'center', padding: 20 }}>No properties yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  )
}
