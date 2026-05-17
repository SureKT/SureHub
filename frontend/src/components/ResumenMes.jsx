import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getResumen, getEvolucion, getMeses } from '../api'

const COLORS = ['#3498db','#2ecc71','#e74c3c','#f39c12','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']

function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  return (
    <div style={{ background: '#2a2a2a', borderRadius: 4, height: 5, width: '100%' }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: alerta ? '#e74c3c' : '#3498db', transition: 'width 0.3s' }} />
    </div>
  )
}

function KpiCard({ label, value, sub, color }) {
  return (
    <div style={{ background: '#1a1a1a', borderRadius: 8, padding: '14px 18px', flex: 1, minWidth: 120 }}>
      <div style={{ color: '#555', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || '#fff', fontVariantNumeric: 'tabular-nums' }}>{value}</div>
      {sub && <div style={{ color: '#555', fontSize: 12, marginTop: 4 }}>{sub}</div>}
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
  if (isError || !data) return <p style={{ color: '#e74c3c' }}>Error al cargar datos. ¿Está el backend arrancado?</p>

  const variable = data.categorias.filter(c => c.tipo === 'variable' && (c.total > 0 || c.estimacion > 0))
  const fijo = data.categorias.filter(c => c.tipo === 'fijo' && (c.total > 0 || c.estimacion > 0))
  const pieData = data.categorias.filter(c => c.total > 0).map(c => ({ name: c.nombre, value: c.total }))
  const topCat = pieData.length > 0 ? [...pieData].sort((a, b) => b.value - a.value)[0] : null

  // KPIs: compare with previous month from evol
  const evolLen = evol.length
  const totalActual = data.total
  const totalAnterior = evolLen >= 2 ? evol[evolLen - 2]?.total : null
  const diff = totalAnterior && totalAnterior > 0 ? ((totalActual - totalAnterior) / totalAnterior) * 100 : null

  const mesLabel = mesSelec ? `${mesSelec.mes.toString().padStart(2, '0')}/${mesSelec.anio}` : 'Mes actual'

  return (
    <div>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0, fontSize: 18 }}>{mesLabel}</h2>
          <select
            value={mesSelec ? `${mesSelec.anio}-${mesSelec.mes}` : ''}
            onChange={e => {
              if (!e.target.value) { setMesSelec(null); return }
              const [a, m] = e.target.value.split('-')
              setMesSelec({ anio: parseInt(a), mes: parseInt(m) })
            }}
            style={{ background: '#1a1a1a', border: '1px solid #2a2a2a', color: '#666', padding: '4px 8px', borderRadius: 6, fontSize: 12 }}
          >
            <option value="">Mes actual</option>
            {meses.map(m => (
              <option key={`${m.anio}-${m.mes}`} value={`${m.anio}-${m.mes}`}>{m.label}</option>
            ))}
          </select>
        </div>
      </div>

      {/* KPI cards */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 28, flexWrap: 'wrap' }}>
        <KpiCard
          label="Total"
          value={`${totalActual.toFixed(2)}€`}
        />
        {diff !== null && !mesSelec && (
          <KpiCard
            label="vs mes anterior"
            value={`${diff >= 0 ? '+' : ''}${diff.toFixed(1)}%`}
            sub={`${totalAnterior?.toFixed(0)}€ anterior`}
            color={diff > 10 ? '#e74c3c' : diff < -5 ? '#2ecc71' : '#aaa'}
          />
        )}
        {topCat && (
          <KpiCard
            label="Top categoría"
            value={topCat.name}
            sub={`${topCat.value.toFixed(2)}€`}
          />
        )}
        {!mesSelec && data.categorias.some(c => c.alerta) && (
          <KpiCard
            label="Alertas"
            value={`${data.categorias.filter(c => c.alerta).length} categorías`}
            color="#e74c3c"
          />
        )}
      </div>

      {/* Categorías */}
      {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => cats.length > 0 && (
        <div key={label} style={{ marginBottom: 24 }}>
          <h3 style={{ color: '#555', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, margin: '0 0 12px' }}>{label}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 14 }}>
                  <span style={{ color: c.alerta ? '#e74c3c' : '#ddd' }}>{c.nombre}</span>
                  <span style={{ color: '#aaa', fontSize: 13 }}>
                    <span style={{ color: c.alerta ? '#e74c3c' : '#fff', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{c.total.toFixed(2)}€</span>
                    {c.estimacion > 0 && <span style={{ color: '#444' }}> / {c.estimacion.toFixed(0)}€</span>}
                    {c.estimacion > 0 && !mesSelec && <span style={{ color: '#333', fontSize: 11 }}> (pred {c.prediccion.toFixed(0)}€)</span>}
                  </span>
                </div>
                {c.estimacion > 0 && <BarraProgreso total={c.total} estimacion={c.estimacion} alerta={c.alerta} />}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Charts */}
      <div className="charts-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24, marginTop: 32 }}>
        <div>
          <h3 style={{ color: '#555', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, margin: '0 0 16px' }}>Evolución 12 meses</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={evol} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fill: '#444', fontSize: 9 }} />
              <YAxis tick={{ fill: '#444', fontSize: 9 }} />
              <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#eee', fontSize: 12 }} formatter={v => `${v.toFixed(2)}€`} />
              <Bar dataKey="total" fill="#3498db" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {pieData.length > 0 && (
          <div>
            <h3 style={{ color: '#555', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, margin: '0 0 16px' }}>Por categoría</h3>
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
