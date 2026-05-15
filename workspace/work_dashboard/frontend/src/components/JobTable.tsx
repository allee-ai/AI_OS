interface Props {
  title: string
  rows: string[][]
  onChange: () => void
}

export default function JobTable({ title, rows }: Props) {
  if (rows.length === 0) return null

  const total = rows.reduce((t, r) => t + (parseFloat(r[2]) || 0), 0)

  return (
    <div className="section">
      <h2>{title}</h2>
      <table>
        <thead>
          <tr>
            <th>Property</th>
            <th>Description</th>
            <th className="r">Cost</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              <td>{row[0]}</td>
              <td>{row[1]}</td>
              <td className="r">${parseFloat(row[2] || '0').toLocaleString()}</td>
            </tr>
          ))}
          <tr style={{ fontWeight: 700, borderTop: '2px solid #ddd' }}>
            <td></td>
            <td>Total</td>
            <td className="r">${total.toLocaleString()}</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}
