import { useEffect, useState } from 'react'
import { api } from '../api'

interface PropertyOption {
  id: number
  address: string
}

export default function TenantPortal() {
  const [properties, setProperties] = useState<PropertyOption[]>([])
  const [propertyId, setPropertyId] = useState<number | ''>('')
  const [desc, setDesc] = useState('')
  const [urgency, setUrgency] = useState('medium')
  const [availability, setAvailability] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    api.getTenantProperties().then(setProperties).catch(console.error)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!propertyId || !desc.trim()) return
    const fullDesc = availability
      ? `${desc.trim()}\n\nAvailability: ${availability}`
      : desc.trim()
    await api.submitWorkOrder({ property_id: propertyId, description: fullDesc, urgency })
    setDesc('')
    setAvailability('')
    setSubmitted(true)
    setTimeout(() => setSubmitted(false), 4000)
  }

  return (
    <>
      <div className="topbar">
        <h1>Maintenance Request</h1>
      </div>

      <div className="section">
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, maxWidth: 500 }}>
          <label style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Property</label>
          <select
            value={propertyId}
            onChange={e => setPropertyId(Number(e.target.value) || '')}
            required
          >
            <option value="">Select your property…</option>
            {properties.map(p => (
              <option key={p.id} value={p.id}>{p.address}</option>
            ))}
          </select>

          <label style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Describe the issue</label>
          <textarea
            rows={4}
            placeholder="What's going on?"
            value={desc}
            onChange={e => setDesc(e.target.value)}
            required
          />

          <label style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Urgency</label>
          <select value={urgency} onChange={e => setUrgency(e.target.value)}>
            <option value="low">Low — when you get a chance</option>
            <option value="medium">Medium — soon</option>
            <option value="high">High — urgent</option>
          </select>

          <label style={{ fontSize: 12, fontWeight: 600, color: '#555' }}>Availability (optional)</label>
          <input
            type="text"
            placeholder="e.g. weekdays after 2pm, anytime Tues/Thurs"
            value={availability}
            onChange={e => setAvailability(e.target.value)}
          />

          <button className="btn btn-primary" type="submit" style={{ marginTop: 4 }}>Submit Request</button>
          {submitted && <p style={{ color: '#155724', fontWeight: 600 }}>Submitted — we'll be in touch.</p>}
        </form>
      </div>
    </>
  )
}
