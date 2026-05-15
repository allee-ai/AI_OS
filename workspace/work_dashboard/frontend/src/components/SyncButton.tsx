import { useState } from 'react'
import { api } from '../api'

export default function SyncButton() {
  const [state, setState] = useState<'idle' | 'syncing' | 'done' | 'error'>('idle')

  const handleSync = async () => {
    setState('syncing')
    try {
      const res = await api.sync()
      setState(res.ok ? 'done' : 'error')
      if (!res.ok) console.error(res.output)
    } catch {
      setState('error')
    }
    setTimeout(() => setState('idle'), 3000)
  }

  const label = {
    idle: 'Sync to VM',
    syncing: 'Syncing…',
    done: 'Synced ✓',
    error: 'Failed',
  }[state]

  return (
    <button className="btn btn-sm" onClick={handleSync} disabled={state === 'syncing'}>
      {label}
    </button>
  )
}
