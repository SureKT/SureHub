import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend } from 'recharts'
import { getResumen, getEvolucion, getMeses } from '../api'

const COLORS = ['#3498db','#2ecc71','#e74c3c','#f39c12','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4','#8bc34a','#ff5722','#607d8b']

function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  return (
    <div style={{ background: '#2a2a2a', borderRadius: 4, height: 6, width: '100%' }}>
      <div style={{ width: `${pct}%`, height: '100%', borderRadius: 4, background: alerta ? '#e74c3c' : '#3498db', transition: 'width 0.3s' }} />
    </div>
  )
}

export default function ResumenMes() {
  const [mesSelec, setMesSelec] = useState(null)

  const { data: meses = [] } = useQuery({ queryKey: ['meses'], queryFn: getMeses })
  const params = mesSelec ? { anio: mesSelec.anio, mes: mesSelec.mes } : {}
  const { data, isLoading } = useQuery({
    queryKey: ['resumen', mesSelec],
    queryFn: () => getResumen(params),
    refetchInterval: mesSelec ? false : 30000
  })
  const { data: evol = [] } = useQuery({ queryKey: ['evolucion'], queryFn: () => getEvolucion(12) })

  if (isLoading) return <p style={{ color: '#888' }}>Cargando...</p>

  const variable = data.categorias.filter(c => c.tipo === 'variable' && (c.total > 0 || c.estimacion > 0))
  const fijo = data.categorias.filter(c => c.tipo === 'fijo' && (c.total > 0 || c.estimacion > 0))
  const pieData = data.categorias.filter(c => c.total > 0).map(c => ({ name: c.nombre, value: c.total }))

  const mesLabel = mesSelec ? `${mesSelec.mes.toString().padStart(2,'0')}/${mesSelec.anio}` : 'Mes actual'

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <h2 style={{ margin: 0 }}>{mesLabel}</h2>
          <select
            value={mesSelec ? `${mesSelec.anio}-${mesSelec.mes}` : ''}
            onChange={e => {
              if (!e.target.value) { setMesSelec(null); return }
              const [a, m] = e.target.value.split('-')
              setMesSelec({ anio: parseInt(a), mes: parseInt(m) })
            }}
            style={{ background: '#1a1a1a', border: '1px solid #333', color: '#aaa', padding: '4px 8px', borderRadius: 6, fontSize: 13 }}
          >
            <option value="">Mes actual</option>
            {meses.map(m => (
              <option key={`${m.anio}-${m.mes}`} value={`${m.anio}-${m.mes}`}>{m.label}</option>
            ))}
          </select>
        </div>
        <span style={{ fontSize: 28, fontWeight: 700 }}>{data.total.toFixed(2)}€</span>
      </div>

      {/* Categorías */}
      {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => cats.length > 0 && (
        <div key={label} style={{ marginBottom: 24 }}>
          <h3 style={{ color: '#888', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 12px' }}>{label}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 14 }}>
                  <span style={{ color: c.alerta ? '#e74c3c' : '#eee' }}>{c.nombre}</span>
                  <span style={{ color: '#aaa', fontSize: 13 }}>
                    <span style={{ color: c.alerta ? '#e74c3c' : '#fff', fontWeight: 600 }}>{c.total.toFixed(2)}€</span>
                    {c.estimacion > 0 && <span style={{ color: '#555' }}> / {c.estimacion.toFixed(0)}€</span>}
                    {c.estimacion > 0 && !mesSelec && <span style={{ color: '#444', fontSize: 11 }}> (pred {c.prediccion.toFixed(0)}€)</span>}
                  </span>
                </div>
                {c.estimacion > 0 && <BarraProgreso total={c.total} estimacion={c.estimacion} alerta={c.alerta} />}
              </div>
            ))}
          </div>
        </div>
      ))}

      {/* Gráficas */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 32 }}>
        {/* Evolución mensual */}
        <div>
          <h3 style={{ color: '#888', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 16px' }}>Evolución 12 meses</h3>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart data={evol} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <XAxis dataKey="label" tick={{ fill: '#555', fontSize: 10 }} />
              <YAxis tick={{ fill: '#555', fontSize: 10 }} />
              <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#eee' }} formatter={v => `${v.toFixed(2)}€`} />
              <Bar dataKey="total" fill="#3498db" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Distribución por categoría */}
        {pieData.length > 0 && (
          <div>
            <h3 style={{ color: '#888', fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 16px' }}>Por categoría</h3>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie data={pieData} dataKey="value" cx="50%" cy="50%" outerRadius={70} label={false}>
                  {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333', color: '#eee' }} formatter={v => `${v.toFixed(2)}€`} />
                <Legend wrapperStyle={{ fontSize: 11, color: '#888' }} />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
