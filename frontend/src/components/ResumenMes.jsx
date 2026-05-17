import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getResumen, getEvolucion, getMeses } from '../api'

const COLORS = ['#3498db','#2ecc71','#e74c3c','#f39c12','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']

function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  const color = alerta ? '#e74c3c' : pct > 75 ? '#f39c12' : '#3498db'
  return (
    <div style={{ background: '#222', borderRadius: 4, height: 4, width: '100%', marginTop: 5 }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: color, transition: 'width 0.3s' }} />
    </div>
  )
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div style={{ background: '#1a1a1a', borderRadius: 8, padding: '12px 16px', minWidth: 130 }}>
      <div style={{ color: '#555', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 5 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: color || '#fff', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && <div style={{ color: '#555', fontSize: 12, marginTop: 3 }}>{sub}</div>}
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

  if (isLoading) return <p style={{ color: '#888' }}>Cargando...</p>
  if (isError || !data) return <p style={{ color: '#e74c3c' }}>Error al cargar. ¿Está el backend arrancado?</p>

  const variable = data.categorias.filter(c => c.tipo === 'variable' && (c.total > 0 || c.estimacion > 0))
  const fijo = data.categorias.filter(c => c.tipo === 'fijo' && (c.total > 0 || c.estimacion > 0))
  const pieData = data.categorias.filter(c => c.total > 0).map(c => ({ name: c.nombre, value: c.total }))
  const topCat = pieData.length > 0 ? [...pieData].sort((a, b) => b.value - a.value)[0] : null

  const evolLen = evol.length
  const totalActual = data.total
  const totalAnterior = evolLen >= 2 ? evol[evolLen - 2]?.total : null
  const diff = totalAnterior && totalAnterior > 0 ? ((totalActual - totalAnterior) / totalAnterior) * 100 : null
  const alertas = data.categorias.filter(c => c.alerta)

  return (
    <div>
      {/* Month selector */}
      <div style={{ marginBottom: 20 }}>
        <select
          value={mesSelec ? `${mesSelec.anio}-${mesSelec.mes}` : ''}
          onChange={e => {
            if (!e.target.value) { setMesSelec(null); return }
            const [a, m] = e.target.value.split('-')
            setMesSelec({ anio: parseInt(a), mes: parseInt(m) })
          }}
          style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#aaa', padding: '6px 10px', borderRadius: 6, fontSize: 13 }}
        >
          <option value="">Mes actual</option>
          {meses.map(m => (
            <option key={`${m.anio}-${m.mes}`} value={`${m.anio}-${m.mes}`}>{m.label}</option>
          ))}
        </select>
      </div>

      {/* KPI cards */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 28, flexWrap: 'wrap' }}>
        <KpiCard label="Total" value={`${totalActual.toFixed(2)}€`} />
        {diff !== null && !mesSelec && (
          <KpiCard
            label="vs anterior"
            value={`${diff >= 0 ? '+' : ''}${diff.toFixed(1)}%`}
            sub={`${totalAnterior?.toFixed(0)}€ prev`}
            color={diff > 10 ? '#e74c3c' : diff < -5 ? '#2ecc71' : '#aaa'}
          />
        )}
        {topCat && (
          <KpiCard label="Top" value={topCat.name} sub={`${topCat.value.toFixed(0)}€`} />
        )}
        {alertas.length > 0 && (
          <KpiCard
            label="Alertas"
            value={alertas.length}
            sub={alertas.map(a => a.nombre).join(', ')}
            color="#e74c3c"
          />
        )}
      </div>

      {/* Categorías */}
      {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => cats.length > 0 && (
        <div key={label} style={{ marginBottom: 24 }}>
          <div style={{ color: '#444', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 10 }}>{label}</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14 }}>
                  <span style={{ color: c.alerta ? '#e74c3c' : '#ccc', display: 'flex', alignItems: 'center', gap: 8 }}>
                    {c.nombre}
                    {c.n_gastos > 0 && <span style={{ color: '#444', fontSize: 11 }}>{c.n_gastos}</span>}
                  </span>
                  <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                    <span style={{ color: c.alerta ? '#e74c3c' : '#fff', fontWeight: 600 }}>{c.total.toFixed(2)}€</span>
                    {c.estimacion > 0 && <span style={{ color: '#3a3a3a' }}> / {c.estimacion.toFixed(0)}€</span>}
                  </span>
                </div>
                {c.estimacion > 0 && <BarraProgreso total={c.total} estimacion={c.estimacion} alerta={c.alerta} />}
              </div>
            ))}
          </div>
        </div>
      ))}

      {variable.length === 0 && fijo.length === 0 && (
        <p style={{ color: '#444', fontSize: 14 }}>Sin gastos este mes.</p>
      )}

      {/* Charts */}
      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginTop: 32 }}>
        {evol.length > 1 && (
          <div>
            <div style={{ color: '#444', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>Evolución 12 meses</div>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={evol} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <XAxis dataKey="label" tick={{ fill: '#444', fontSize: 9 }} />
                <YAxis tick={{ fill: '#444', fontSize: 9 }} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#eee', fontSize: 12 }} formatter={v => `${v.toFixed(2)}€`} />
                <Bar dataKey="total" fill="#3498db" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {pieData.length > 0 && (
          <div>
            <div style={{ color: '#444', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 16 }}>Por categoría</div>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={65} label={false}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#eee', fontSize: 12 }} formatter={v => `${v.toFixed(2)}€`} />
                <Legend wrapperStyle={{ fontSize: 10, color: '#666' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
