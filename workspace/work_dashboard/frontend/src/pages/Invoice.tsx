import { useEffect, useState } from 'react'
import { api, BalanceSummary, Job } from '../api'

export default function Invoice() {
  const [balance, setBalance] = useState<BalanceSummary | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [payments, setPayments] = useState<any[]>([])

  useEffect(() => {
    api.getBalance().then(setBalance).catch(console.error)
    api.getJobs().then(setJobs).catch(console.error)
    api.getPayments().then(setPayments).catch(console.error)
  }, [])

  if (!balance) return <p>Loading…</p>

  const completed = jobs.filter(j => j.status === 'completed')
  const scheduled = jobs.filter(j => j.status === 'scheduled')

  const jobTotal = (j: Job) => j.billing_type === 'hourly' && j.hours ? j.cost * j.hours : j.cost

  const completedTotal = completed.reduce((t, j) => t + jobTotal(j), 0)
  const scheduledTotal = scheduled.reduce((t, j) => t + jobTotal(j), 0)
  const depositsTotal = payments.reduce((t, p) => t + parseFloat(p.amount), 0)

  const today = new Date().toLocaleDateString('en-US', {
    year: 'numeric', month: 'long', day: 'numeric',
  })

  return (
    <>
      <style>{`
        @media print {
          .app-nav, .invoice-actions { display: none !important; }
          .page { padding: 0 !important; }
          body { background: white !important; }
        }
        .invoice-actions {
          display: flex;
          gap: 8px;
          margin-bottom: 16px;
          justify-content: flex-end;
        }
        .invoice-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-end;
          margin-bottom: 24px;
          padding-bottom: 16px;
          border-bottom: 2px solid #333;
        }
        .invoice-header h1 {
          margin: 0;
          font-size: 32px;
        }
        .invoice-header .meta {
          text-align: right;
          color: #555;
          font-size: 14px;
        }
        .invoice-section {
          margin-bottom: 28px;
          page-break-inside: avoid;
        }
        .invoice-section h2 {
          margin: 0 0 8px 0;
          font-size: 18px;
          padding-bottom: 4px;
          border-bottom: 1px solid #ddd;
        }
        .invoice-section .subtotal {
          margin-top: 6px;
          text-align: right;
          font-weight: 600;
          font-size: 14px;
        }
        .invoice-totals {
          margin-top: 32px;
          padding-top: 16px;
          border-top: 2px solid #333;
          display: flex;
          justify-content: flex-end;
        }
        .invoice-totals table {
          width: auto;
          min-width: 320px;
        }
        .invoice-totals td {
          padding: 6px 12px;
        }
        .invoice-totals tr.balance td {
          font-size: 18px;
          font-weight: 700;
          border-top: 1px solid #333;
          padding-top: 10px;
        }
      `}</style>

      <div className="invoice-header">
        <h1>Invoice</h1>
        <div className="meta">
          <div><strong>Date:</strong> {today}</div>
        </div>
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

      <div className="invoice-section">
        <h2>Completed ({completed.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Property</th>
              <th>Description</th>
              <th>Type</th>
              <th className="r">Cost</th>
            </tr>
          </thead>
          <tbody>
            {completed.map(j => (
              <tr key={j.id}>
                <td>{j.property_address}</td>
                <td>{j.description}</td>
                <td>{j.billing_type}{j.billing_type === 'hourly' && j.hours ? ` (${j.hours}h @ $${j.cost})` : ''}</td>
                <td className="r">${jobTotal(j).toLocaleString()}</td>
              </tr>
            ))}
            {completed.length === 0 && (
              <tr><td colSpan={4} style={{ color: '#888', textAlign: 'center' }}>None</td></tr>
            )}
          </tbody>
        </table>
        <div className="subtotal">Subtotal: ${completedTotal.toLocaleString()}</div>
      </div>

      <div className="invoice-section">
        <h2>Scheduled ({scheduled.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Property</th>
              <th>Description</th>
              <th>Type</th>
              <th className="r">Cost</th>
            </tr>
          </thead>
          <tbody>
            {scheduled.map(j => (
              <tr key={j.id}>
                <td>{j.property_address}</td>
                <td>{j.description}</td>
                <td>{j.billing_type}{j.billing_type === 'hourly' && j.hours ? ` (${j.hours}h @ $${j.cost})` : ''}</td>
                <td className="r">${jobTotal(j).toLocaleString()}</td>
              </tr>
            ))}
            {scheduled.length === 0 && (
              <tr><td colSpan={4} style={{ color: '#888', textAlign: 'center' }}>None</td></tr>
            )}
          </tbody>
        </table>
        <div className="subtotal">Subtotal: ${scheduledTotal.toLocaleString()}</div>
      </div>

      <div className="invoice-section">
        <h2>Deposits ({payments.length})</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th className="r">Amount</th>
              <th>Note</th>
            </tr>
          </thead>
          <tbody>
            {payments.map(p => (
              <tr key={p.id}>
                <td>{p.date}</td>
                <td className="r">${parseFloat(p.amount).toLocaleString()}</td>
                <td>{p.note}</td>
              </tr>
            ))}
            {payments.length === 0 && (
              <tr><td colSpan={3} style={{ color: '#888', textAlign: 'center' }}>None</td></tr>
            )}
          </tbody>
        </table>
        <div className="subtotal">Subtotal: ${depositsTotal.toLocaleString()}</div>
      </div>

      <div className="invoice-totals">
        <table>
          <tbody>
            <tr>
              <td>Completed</td>
              <td className="r">${balance.completed.toLocaleString()}</td>
            </tr>
            <tr>
              <td>Scheduled</td>
              <td className="r">${balance.scheduled.toLocaleString()}</td>
            </tr>
            <tr>
              <td>Deposits</td>
              <td className="r">−${balance.deposits.toLocaleString()}</td>
            </tr>
            <tr className="balance">
              <td>Balance Due</td>
              <td
                className="r"
                style={{ color: balance.balance >= 0 ? '#28a745' : '#dc3545' }}
              >
                ${balance.balance.toLocaleString()}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  )
}
