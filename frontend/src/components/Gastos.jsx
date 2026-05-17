import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getGastos, getCategorias, createGasto } from '../api'

export default function Gastos() {
  const qc = useQueryClient()
  const { data: gastos = [], isLoading } = useQuery({ queryKey: ['gastos'], queryFn: () => getGastos(50) })
  const { data: categorias = [] } = useQuery({ queryKey: ['categorias'], queryFn: getCategorias })

  const [form, setForm] = useState({ cantidad: '', descripcion: '', categoria_id: '' })

  const mutation = useMutation({
    mutationFn: createGasto,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      setForm({ cantidad: '', descripcion: '', categoria_id: '' })
    }
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.cantidad) return
    mutation.mutate({
      cantidad: parseFloat(form.cantidad),
      descripcion: form.descripcion || null,
      categoria_id: form.categoria_id ? parseInt(form.categoria_id) : null,
    })
  }

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Gastos</h2>

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap' }}>
        <input
          type="number" step="0.01" placeholder="Cantidad €" value={form.cantidad}
          onChange={e => setForm(f => ({ ...f, cantidad: e.target.value }))}
          style={inputStyle} required
        />
        <input
          type="text" placeholder="Descripción" value={form.descripcion}
          onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
          style={{ ...inputStyle, flex: 2 }}
        />
        <select
          value={form.categoria_id}
          onChange={e => setForm(f => ({ ...f, categoria_id: e.target.value }))}
          style={inputStyle}
        >
          <option value="">Sin categoría</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <button type="submit" style={btnStyle}>+ Añadir</button>
      </form>

      {isLoading ? <p style={{ color: '#888' }}>Cargando...</p> : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
          <thead>
            <tr style={{ color: '#888', textAlign: 'left', borderBottom: '1px solid #333' }}>
              <th style={th}>Fecha</th>
              <th style={th}>Descripción</th>
              <th style={th}>Categoría</th>
              <th style={{ ...th, textAlign: 'right' }}>Cantidad</th>
            </tr>
          </thead>
          <tbody>
            {gastos.map(g => (
              <tr key={g.id} style={{ borderBottom: '1px solid #222' }}>
                <td style={td}>{new Date(g.fecha).toLocaleDateString('es-ES')}</td>
                <td style={td}>{g.descripcion || '—'}</td>
                <td style={td}>{g.categoria?.nombre || <span style={{ color: '#555' }}>sin categoría</span>}</td>
                <td style={{ ...td, textAlign: 'right', fontWeight: 600 }}>{g.cantidad.toFixed(2)}€</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

const inputStyle = { background: '#1a1a1a', border: '1px solid #333', color: '#eee', padding: '8px 12px', borderRadius: 6, fontSize: 14 }
const btnStyle = { background: '#3498db', border: 'none', color: '#fff', padding: '8px 16px', borderRadius: 6, cursor: 'pointer', fontSize: 14 }
const th = { padding: '8px 12px', fontWeight: 500 }
const td = { padding: '10px 12px', color: '#ddd' }
