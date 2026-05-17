import { useQuery } from '@tanstack/react-query'
import { getResumen } from '../api'

function BarraProgreso({ total, estimacion, alerta }) {
  const pct = estimacion > 0 ? Math.min((total / estimacion) * 100, 100) : 0
  return (
    <div style={{ background: '#2a2a2a', borderRadius: 4, height: 8, width: '100%' }}>
      <div style={{
        width: `${pct}%`, height: '100%', borderRadius: 4,
        background: alerta ? '#e74c3c' : '#3498db',
        transition: 'width 0.3s'
      }} />
    </div>
  )
}

export default function ResumenMes() {
  const { data, isLoading } = useQuery({ queryKey: ['resumen'], queryFn: getResumen, refetchInterval: 30000 })

  if (isLoading) return <p style={{ color: '#888' }}>Cargando...</p>

  const variable = data.categorias.filter(c => c.tipo === 'variable')
  const fijo = data.categorias.filter(c => c.tipo === 'fijo')

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 24 }}>
        <h2 style={{ margin: 0 }}>Mes actual</h2>
        <span style={{ fontSize: 24, fontWeight: 700 }}>{data.total.toFixed(2)}€</span>
      </div>

      {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => (
        <div key={label} style={{ marginBottom: 24 }}>
          <h3 style={{ color: '#888', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 12px' }}>{label}</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {cats.map(c => (
              <div key={c.id}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4, fontSize: 14 }}>
                  <span style={{ color: c.alerta ? '#e74c3c' : '#eee' }}>{c.nombre}</span>
                  <span style={{ color: '#aaa' }}>
                    <span style={{ color: c.alerta ? '#e74c3c' : '#fff', fontWeight: 600 }}>{c.total.toFixed(0)}€</span>
                    {c.estimacion > 0 && ` / ${c.estimacion.toFixed(0)}€`}
                  </span>
                </div>
                {c.estimacion > 0 && <BarraProgreso total={c.total} estimacion={c.estimacion} alerta={c.alerta} />}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
