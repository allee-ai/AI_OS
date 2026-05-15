interface Props {
  rows: string[][]
  onChange: () => void
}

export default function PaymentTable({ rows }: Props) {
  const total = rows.reduce((t, r) => t + (parseFloat(r[1]) || 0), 0)

  return (
    <div className="section">
      <h2>Payments</h2>
      <table>
        <thead>
          <tr>
            <th>Date</th>
            <th className="r">Amount</th>
            <th>Note</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>{row[0]}</td>
              <td className="r">${parseFloat(row[1] || '0').toLocaleString()}</td>
              <td>{row[2]}</td>
            </tr>
          ))}
          <tr style={{ fontWeight: 700, borderTop: '2px solid #ddd' }}>
            <td>Total</td>
            <td className="r">${total.toLocaleString()}</td>
            <td></td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
