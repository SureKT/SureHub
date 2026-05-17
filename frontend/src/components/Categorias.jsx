import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCategorias, createCategoria, updateCategoria, deleteCategoria } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: '#111', border: '1px solid #333', color: '#eee', padding: '8px 12px', borderRadius: 6, fontSize: 14 }
const btnStyle = { background: '#3498db', border: 'none', color: '#fff', padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnSecStyle = { background: '#2a2a2a', border: '1px solid #444', color: '#ccc', padding: '6px 12px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: '#555', padding: '6px 8px', cursor: 'pointer', fontSize: 15 }

export default function Categorias() {
  const toast = useToast()
  const qc = useQueryClient()
  const [showInactivas, setShowInactivas] = useState(false)
  const { data: categorias = [], isLoading } = useQuery({
    queryKey: ['categorias', 'all'],
    queryFn: () => getCategorias({ solo_activas: false }),
  })
  const [form, setForm] = useState({ nombre: '', tipo: 'variable', estimacion_mensual: '' })
  const [editId, setEditId] = useState(null)
  const [editVal, setEditVal] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)

  const createMut = useMutation({
    mutationFn: createCategoria,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categorias'] })
      setForm({ nombre: '', tipo: 'variable', estimacion_mensual: '' })
      toast('Categoría creada')
    },
    onError: (e) => toast(e?.response?.data?.detail || 'Error al crear categoría', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateCategoria(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categorias'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      setEditId(null)
      toast('Actualizado')
    },
    onError: () => toast('Error al actualizar', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteCategoria,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categorias'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      setConfirmDelete(null)
      toast('Categoría eliminada')
    },
    onError: () => toast('Error al eliminar', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    createMut.mutate({ ...form, estimacion_mensual: parseFloat(form.estimacion_mensual) || 0 })
  }

  const activas = categorias.filter(c => c.activa)
  const inactivas = categorias.filter(c => !c.activa)
  const variable = activas.filter(c => c.tipo === 'variable')
  const fijo = activas.filter(c => c.tipo === 'fijo')

  const CatRow = ({ c }) => (
    <div key={c.id} style={{
      display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
      background: c.activa ? '#1a1a1a' : '#141414', borderRadius: 6,
      opacity: c.activa ? 1 : 0.6,
    }}>
      <span style={{ flex: 1, fontSize: 14, color: c.activa ? '#eee' : '#666' }}>{c.nombre}</span>
      {editId === c.id ? (
        <>
          <input type="number" step="0.01" value={editVal} onChange={e => setEditVal(e.target.value)}
            style={{ ...inputStyle, width: 100 }} autoFocus
            onKeyDown={e => { if (e.key === 'Enter') updateMut.mutate({ id: c.id, data: { estimacion_mensual: parseFloat(editVal) } }) }}
          />
          <button onClick={() => updateMut.mutate({ id: c.id, data: { estimacion_mensual: parseFloat(editVal) } })} style={btnStyle}>✓</button>
          <button onClick={() => setEditId(null)} style={btnSecStyle}>✕</button>
        </>
      ) : (
        <>
          <span style={{ color: '#555', fontSize: 13 }}>{c.estimacion_mensual > 0 ? `${c.estimacion_mensual.toFixed(0)}€/mes` : '—'}</span>
          <button onClick={() => { setEditId(c.id); setEditVal(c.estimacion_mensual) }} style={btnSecStyle} title="Editar presupuesto">Editar</button>
          <button
            onClick={() => updateMut.mutate({ id: c.id, data: { activa: !c.activa } })}
            style={{ ...btnSecStyle, color: c.activa ? '#888' : '#3498db', fontSize: 12, padding: '5px 10px' }}
            title={c.activa ? 'Desactivar' : 'Activar'}
          >
            {c.activa ? 'Desactivar' : 'Activar'}
          </button>
          {confirmDelete === c.id ? (
            <>
              <button onClick={() => deleteMut.mutate(c.id)} style={{ ...btnDangerStyle, color: '#e74c3c' }}>✓</button>
              <button onClick={() => setConfirmDelete(null)} style={btnDangerStyle}>✕</button>
            </>
          ) : (
            <button onClick={() => setConfirmDelete(c.id)} style={btnDangerStyle} title="Eliminar">✕</button>
          )}
        </>
      )}
    </div>
  )

  return (
    <div>
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
        <>
          {[['Variable', variable], ['Fijo', fijo]].map(([label, cats]) => (
            <div key={label} style={{ marginBottom: 24 }}>
              <h3 style={{ color: '#888', fontSize: 12, textTransform: 'uppercase', letterSpacing: 1, margin: '0 0 12px' }}>{label}</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {cats.length === 0 && <p style={{ color: '#444', fontSize: 13 }}>Sin categorías</p>}
                {cats.map(c => <CatRow key={c.id} c={c} />)}
              </div>
            </div>
          ))}

          {inactivas.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <button onClick={() => setShowInactivas(s => !s)}
                style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', fontSize: 13, padding: 0 }}>
                {showInactivas ? '▾' : '▸'} Inactivas ({inactivas.length})
              </button>
              {showInactivas && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 10 }}>
                  {inactivas.map(c => <CatRow key={c.id} c={c} />)}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
