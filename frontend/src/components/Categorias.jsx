import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCategorias, createCategoria, updateCategoria, deleteCategoria } from '../api'

export default function Categorias() {
  const qc = useQueryClient()
  const { data: categorias = [], isLoading } = useQuery({ queryKey: ['categorias'], queryFn: getCategorias })
  const [form, setForm] = useState({ nombre: '', tipo: 'variable', estimacion_mensual: '' })
  const [editId, setEditId] = useState(null)
  const [editVal, setEditVal] = useState('')

  const createMut = useMutation({
    mutationFn: createCategoria,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categorias'] }); setForm({ nombre: '', tipo: 'variable', estimacion_mensual: '' }) }
  })

  const updateMut = useMutation({
    mutationFn: ({ id, val }) => updateCategoria(id, { estimacion_mensual: parseFloat(val) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categorias'] }); qc.invalidateQueries({ queryKey: ['resumen'] }); setEditId(null) }
  })

  const deleteMut = useMutation({
    mutationFn: deleteCategoria,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['categorias'] }); qc.invalidateQueries({ queryKey: ['resumen'] }) }
  })

  const submit = (e) => {
    e.preventDefault()
    createMut.mutate({ ...form, estimacion_mensual: parseFloat(form.estimacion_mensual) || 0 })
  }

  const variable = categorias.filter(c => c.tipo === 'variable')
  const fijo = categorias.filter(c => c.tipo === 'fijo')

  return (
    <div>
      <h2 style={{ marginBottom: 20 }}>Categorías</h2>

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
        <input placeholder="Nombre" value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))} style={inputStyle} required />
        <select value={form.tipo} onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))} style={inputStyle}>
          <option value="variable">Variable</option>
          <option value="fijo">Fijo</option>
        </select>
        <input type="number" step="0.01" placeholder="Presupuesto €/mes" value={form.estimacion_mensual}
          onChange={e => setForm(f => ({ ...f, estimacion_mensual: e.target.value }))} style={inputStyle} />
        <button type="submit" style={btnStyle}>+ Añadir</button>
      </form>

      {isLoading ? <p style={{ color: '#888' }}>Cargando...</p> : (
        [['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => (
          <div key={label} style={{ marginBottom: 24 }}>
            <h3 style={{ color: '#888', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 12px' }}>{label}</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {cats.map(c => (
                <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: '#1a1a1a', borderRadius: 6 }}>
                  <span style={{ flex: 1, fontSize: 14 }}>{c.nombre}</span>
                  {editId === c.id ? (
                    <>
                      <input type="number" step="0.01" value={editVal} onChange={e => setEditVal(e.target.value)}
                        style={{ ...inputStyle, width: 100 }} autoFocus />
                      <button onClick={() => updateMut.mutate({ id: c.id, val: editVal })} style={btnStyle}>✓</button>
                      <button onClick={() => setEditId(null)} style={btnSecStyle}>✕</button>
                    </>
                  ) : (
                    <>
                      <span style={{ color: '#aaa', fontSize: 14 }}>{c.estimacion_mensual.toFixed(0)}€/mes</span>
                      <button onClick={() => { setEditId(c.id); setEditVal(c.estimacion_mensual) }} style={btnSecStyle}>Editar</button>
                      <button onClick={() => deleteMut.mutate(c.id)} style={btnDangerStyle}>✕</button>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))
      )}
    </div>
  )
}

const inputStyle = { background: '#111', border: '1px solid #333', color: '#eee', padding: '8px 12px', borderRadius: 6, fontSize: 14 }
const btnStyle = { background: '#3498db', border: 'none', color: '#fff', padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnSecStyle = { background: '#2a2a2a', border: '1px solid #444', color: '#ccc', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: '#666', padding: '6px 8px', cursor: 'pointer', fontSize: 16 }
