import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getResumen, getEvolucion, getMeses } from '../api'

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

function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  const color = alerta ? 'var(--red)' : pct > 75 ? 'var(--orange)' : 'var(--accent)'
  return (
    <div style={{ background: 'var(--surface3)', borderRadius: 4, height: 4, width: '100%', marginTop: 5 }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.3s' }} />
    </div>
  )
}

export default function ResumenMes() {
  const [mesSelec, setMesSelec] = useState(null)

  const { data: meses = [] } = useQuery({ queryKey: ['meses'], queryFn: getMeses })
  const params = mesSelec ? { anio: mesSelec.anio, mes: mesSelec.mes } : {}
  const { data, isLoading, isError } = useQuery({
    queryKey: ['resumen', mesSelec],
    queryFn: () => getResumen(params),
    refetchInterval: mesSelec ? false : 30000,
  })
  const { data: evol = [] } = useQuery({ queryKey: ['evolucion'], queryFn: () => getEvolucion(12) })

  if (isLoading) return <p style={{ color: 'var(--text-dim)' }}>Cargando...</p>
  if (isError || !data) return <p style={{ color: 'var(--red)' }}>Error al cargar. ¿Está el backend arrancado?</p>

  const variable = data.categorias.filter(c => c.tipo === 'variable' && (c.total > 0 || c.estimacion > 0))
  const fijo = data.categorias.filter(c => c.tipo === 'fijo' && (c.total > 0 || c.estimacion > 0))
  const pieData = data.categorias.filter(c => c.total > 0).map(c => ({ name: c.nombre, value: c.total }))
  const topCat = pieData.length > 0 ? [...pieData].sort((a, b) => b.value - a.value)[0] : null

  const evolLen = evol.length
  const totalActual = data.total
  const totalAnterior = evolLen >= 2 ? evol[evolLen - 2]?.total : null
  const diff = totalAnterior && totalAnterior > 0 ? ((totalActual - totalAnterior) / totalAnterior) * 100 : null
  const alertas = data.categorias.filter(c => c.alerta)

  const metaItems = []
  if (diff !== null && !mesSelec) {
    const diffColor = diff > 10 ? 'var(--red)' : diff < -5 ? 'var(--green)' : 'var(--text-dim)'
    metaItems.push(
      <span key="diff" style={{ color: diffColor }}>{diff >= 0 ? '+' : ''}{diff.toFixed(1)}% vs anterior</span>
    )
  }
  if (topCat) {
    metaItems.push(
      <span key="top" style={{ color: 'var(--text-dim)' }}>Top: {topCat.name} {topCat.value.toFixed(0)}€</span>
    )
  }
  if (alertas.length > 0) {
    metaItems.push(
      <span key="alertas" style={{ color: 'var(--red)' }}>{alertas.length} alerta{alertas.length > 1 ? 's' : ''}</span>
    )
  }

  return (
    <div>
      {/* Hero block */}
      <div style={{ marginBottom: 32 }}>
        <select
          value={mesSelec ? `${mesSelec.anio}-${mesSelec.mes}` : ''}
          onChange={e => {
            if (!e.target.value) { setMesSelec(null); return }
            const [a, m] = e.target.value.split('-')
            setMesSelec({ anio: parseInt(a), mes: parseInt(m) })
          }}
          style={{
            background: 'none', border: 'none', color: 'var(--text-muted)',
            fontSize: 11, textTransform: 'uppercase', letterSpacing: 1.5,
            cursor: 'pointer', padding: 0, marginBottom: 12,
            fontFamily: 'inherit', fontWeight: 500,
          }}
        >
          <option value="">Mes actual</option>
          {meses.map(m => (
            <option key={`${m.anio}-${m.mes}`} value={`${m.anio}-${m.mes}`}>{m.label}</option>
          ))}
        </select>

        <div style={{
          fontSize: 48, fontWeight: 300, fontVariantNumeric: 'tabular-nums',
          color: 'var(--text)', letterSpacing: '-1px', lineHeight: 1,
        }}>
          {totalActual.toFixed(2)}€
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

      {/* Categorías */}
      {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => cats.length > 0 && (
        <div key={label} style={{ marginBottom: 24 }}>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 10 }}>{label}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14 }}>
                  <span style={{ color: c.alerta ? 'var(--red)' : 'var(--text)', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {c.nombre}
                    {c.n_gastos > 0 && <span style={{ color: 'var(--text-muted)', fontSize: 11 }}>{c.n_gastos}</span>}
                  </span>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                    <span style={{ color: c.alerta ? 'var(--red)' : 'var(--text)', fontWeight: 500 }}>{c.total.toFixed(2)}€</span>
                    {c.estimacion > 0 && <span style={{ color: 'var(--text-muted)' }}> / {c.estimacion.toFixed(0)}€</span>}
                  </span>
                </div>
                {c.estimacion > 0 && <BarraProgreso total={c.total} estimacion={c.estimacion} alerta={c.alerta} />}
              </div>
            ))}
          </div>
        </div>
      ))}

      {variable.length === 0 && fijo.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <div style={{ fontSize: 32, marginBottom: 12, color: 'var(--text-muted)', lineHeight: 1 }}>○</div>
          <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500 }}>Sin gastos este mes</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>Los gastos aparecerán aquí cuando los añadas</div>
        </div>
      )}

      {/* Charts */}
      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginTop: 40 }}>
        {evol.length > 1 && (
          <div>
            <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>Evolución 12 meses</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={evol} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
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
            <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>Por categoría</div>
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
