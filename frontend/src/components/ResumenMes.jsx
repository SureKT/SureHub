import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getSummary, getEvolution, getMonths } from '../api'

const COLORS = [
  '#c8f0dc', // accent mint
  '#a78bfa', // purple
  '#fbbf24', // orange
  '#f87171', // red
  '#4ade80', // green
  '#9b9b97', // grey
  '#7dd3fc', // sky
  '#f9a8d4', // pink
  '#86efac', // light green
  '#c4b5fd', // light purple
  '#fca5a5', // light red
  '#fde68a', // light yellow
]

function ProgressBar({ total, estimate, alert }) {
  const pct = estimate > 0 ? Math.min((total / estimate) * 100, 100) : 0
  const color = alert ? 'var(--red)' : pct > 75 ? 'var(--orange)' : 'var(--accent)'
  return (
    <div style={{ background: 'var(--surface3)', borderRadius: 4, height: 4, width: '100%', marginTop: 5 }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.3s' }} />
    </div>
  )
}

export default function ResumenMes() {
  const [selectedMonth, setSelectedMonth] = useState(null)

  const { data: months = [] } = useQuery({ queryKey: ['months'], queryFn: getMonths })
  const params = selectedMonth ? { year: selectedMonth.year, month: selectedMonth.month } : {}
  const { data, isLoading, isError } = useQuery({
    queryKey: ['summary', selectedMonth],
    queryFn: () => getSummary(params),
    refetchInterval: selectedMonth ? false : 30000,
  })
  const { data: evolution = [] } = useQuery({ queryKey: ['evolution'], queryFn: () => getEvolution(12) })

  if (isLoading) return <p style={{ color: 'var(--text-dim)' }}>Loading...</p>
  if (isError || !data) return <p style={{ color: 'var(--red)' }}>Error loading data. Is the backend running?</p>

  const variable = data.categories.filter(c => c.type === 'variable' && (c.total > 0 || c.estimate > 0))
  const fixed = data.categories.filter(c => c.type === 'fixed' && (c.total > 0 || c.estimate > 0))
  const pieData = data.categories.filter(c => c.total > 0).map(c => ({ name: c.name, value: c.total }))
  const topCat = pieData.length > 0 ? [...pieData].sort((a, b) => b.value - a.value)[0] : null

  const evolLen = evolution.length
  const totalNow = data.total
  const totalPrev = evolLen >= 2 ? evolution[evolLen - 2]?.total : null
  const diff = totalPrev && totalPrev > 0 ? ((totalNow - totalPrev) / totalPrev) * 100 : null
  const alerts = data.categories.filter(c => c.alert)

  const metaItems = []
  if (diff !== null && !selectedMonth) {
    const diffColor = diff > 10 ? 'var(--red)' : diff < -5 ? 'var(--green)' : 'var(--text-dim)'
    metaItems.push(
      <span key="diff" style={{ color: diffColor }}>{diff >= 0 ? '+' : ''}{diff.toFixed(1)}% vs prev</span>
    )
  }
  if (topCat) {
    metaItems.push(
      <span key="top" style={{ color: 'var(--text-dim)' }}>Top: {topCat.name} {topCat.value.toFixed(0)}€</span>
    )
  }
  if (alerts.length > 0) {
    metaItems.push(
      <span key="alerts" style={{ color: 'var(--red)' }}>{alerts.length} alert{alerts.length > 1 ? 's' : ''}</span>
    )
  }

  return (
    <div>
      {/* Hero block */}
      <div style={{ marginBottom: 32 }}>
        <select
          value={selectedMonth ? `${selectedMonth.year}-${selectedMonth.month}` : ''}
          onChange={e => {
            if (!e.target.value) { setSelectedMonth(null); return }
            const [y, m] = e.target.value.split('-')
            setSelectedMonth({ year: parseInt(y), month: parseInt(m) })
          }}
          style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.5,
            cursor: 'pointer', padding: 0, marginBottom: 12,
            fontFamily: 'inherit', fontWeight: 500,
          }}
        >
          <option value="">Current month</option>
          {months.map(m => (
            <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>{m.label}</option>
          ))}
        </select>

        <div style={{
          fontSize: 48, fontWeight: 300, fontVariantNumeric: 'tabular-nums',
          color: 'var(--text)', letterSpacing: '-1px', lineHeight: 1,
        }}>
          {totalNow.toFixed(2)}€
        </div>

        {metaItems.length > 0 && (
          <div style={{ marginTop: 10, fontSize: 12, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            {metaItems.map((item, i) => (
              <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {i > 0 && <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>·</span>}
                {item}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Separator */}
      <div style={{ borderBottom: '1px solid var(--border-dim)', marginBottom: 24 }} />

      {/* Categories */}
      {[['Variable', variable], ['Fixed', fixed]].map(([label, cats]) => cats.length > 0 && (
        <div key={label} style={{ marginBottom: 24 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 10 }}>{label}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14 }}>
                  <span style={{ color: c.alert ? 'var(--red)' : 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {c.name}
                    {c.expense_count > 0 && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{c.expense_count}</span>}
                  </span>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                    <span style={{ color: c.alert ? 'var(--red)' : 'var(--text)', fontWeight: 500 }}>{c.total.toFixed(2)}€</span>
                    {c.estimate > 0 && <span style={{ color: 'var(--text-muted)' }}> / {c.estimate.toFixed(0)}€</span>}
                  </span>
                </div>
                {c.estimate > 0 && <ProgressBar total={c.total} estimate={c.estimate} alert={c.alert} />}
              </div>
            ))}
          </div>
        </div>
      ))}

      {variable.length === 0 && fixed.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <div style={{ fontSize: 32, marginBottom: 12, color: 'var(--text-muted)', lineHeight: 1 }}>○</div>
          <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500 }}>No expenses this month</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>Expenses will appear here once added</div>
        </div>
      )}

      {/* Charts */}
      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginTop: 40 }}>
        {evolution.length > 1 && (
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>12-month evolution</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={evolution} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="label" tick={{ fill: 'var(--text-muted)', fontSize: 9 }} />
                <YAxis tick={{ fill: 'var(--text-muted)', fontSize: 9 }} />
                <Tooltip contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', fontSize: 12 }} formatter={v => `${v.toFixed(2)}€`} />
                <Bar dataKey="total" fill="var(--accent)" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {pieData.length > 0 && (
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>By category</div>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={65} label={false}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', fontSize: 12 }} formatter={v => `${v.toFixed(2)}€`} />
                <Legend wrapperStyle={{ fontSize: 10, color: 'var(--text-dim)' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
