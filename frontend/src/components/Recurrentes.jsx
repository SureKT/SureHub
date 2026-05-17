import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRecurrentes, createRecurrente, updateRecurrente, deleteRecurrente, generarRecurrentes, getCategorias } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: '#1a1a1a', border: '1px solid #333', color: '#eee', padding: '8px 12px', borderRadius: 6, fontSize: 14 }
const btnStyle = { background: '#3498db', border: 'none', color: '#fff', padding: '8px 14px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnSecStyle = { background: '#2a2a2a', border: '1px solid #444', color: '#ccc', padding: '6px 10px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: '#555', padding: '4px 8px', cursor: 'pointer', fontSize: 15 }

export default function Recurrentes() {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({ nombre: '', cantidad: '', categoria_id: '', dia: '1' })
  const [editId, setEditId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: recurrentes = [], isLoading } = useQuery({
    queryKey: ['recurrentes'],
    queryFn: () => getRecurrentes(),
    refetchInterval: 60000,
  })
  const { data: categorias = [] } = useQuery({ queryKey: ['categorias'], queryFn: getCategorias })

  const pendientes = recurrentes.filter(r => r.activo && !r.generado_este_mes)
  const totalMensual = recurrentes.filter(r => r.activo).reduce((s, r) => s + r.cantidad, 0)

  const createMut = useMutation({
    mutationFn: createRecurrente,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurrentes'] })
      setForm({ nombre: '', cantidad: '', categoria_id: '', dia: '1' })
      toast('Gasto recurrente añadido')
    },
    onError: (e) => toast(e?.response?.data?.detail || 'Error al crear', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateRecurrente(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurrentes'] })
      setEditId(null)
      toast('Actualizado')
    },
    onError: () => toast('Error al actualizar', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteRecurrente,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurrentes'] })
      setConfirmDelete(null)
      toast('Eliminado')
    },
    onError: () => toast('Error al eliminar', 'error'),
  })

  const generarMut = useMutation({
    mutationFn: generarRecurrentes,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['recurrentes'] })
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      if (data.total === 0) toast('Todos ya generados este mes')
      else toast(`${data.total} gasto${data.total > 1 ? 's' : ''} generado${data.total > 1 ? 's' : ''}`)
    },
    onError: () => toast('Error al generar', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.nombre || !form.cantidad) return
    createMut.mutate({
      nombre: form.nombre,
      cantidad: parseFloat(form.cantidad),
      categoria_id: form.categoria_id ? parseInt(form.categoria_id) : null,
      dia: parseInt(form.dia) || 1,
    })
  }

  const saveEdit = (id) => updateMut.mutate({ id, data: {
    nombre: editForm.nombre,
    cantidad: parseFloat(editForm.cantidad),
    categoria_id: editForm.categoria_id ? parseInt(editForm.categoria_id) : null,
    dia: parseInt(editForm.dia) || 1,
  }})

  const activos = recurrentes.filter(r => r.activo)
  const inactivos = recurrentes.filter(r => !r.activo)

  return (
    <div>
      <p style={{ color: '#555', fontSize: 13, margin: '0 0 20px' }}>
        Gastos que se generan automáticamente cada mes en la fecha indicada.
      </p>

      {/* Add form */}
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
        <input placeholder="Nombre (ej: Netflix)" value={form.nombre}
          onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
          style={{ ...inputStyle, flex: 2, minWidth: 130 }} required />
        <input type="number" step="0.01" placeholder="Importe €" value={form.cantidad}
          onChange={e => setForm(f => ({ ...f, cantidad: e.target.value }))}
          style={{ ...inputStyle, width: 110 }} required />
        <select value={form.categoria_id} onChange={e => setForm(f => ({ ...f, categoria_id: e.target.value }))} style={inputStyle}>
          <option value="">Sin categoría</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: '#666', fontSize: 13 }}>Día</span>
          <input type="number" min="1" max="28" value={form.dia}
            onChange={e => setForm(f => ({ ...f, dia: e.target.value }))}
            style={{ ...inputStyle, width: 60, textAlign: 'center' }} />
        </div>
        <button type="submit" style={btnStyle}>+ Añadir</button>
      </form>

      {/* Header stats + generate button */}
      {activos.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', gap: 20 }}>
            <div>
              <div style={{ color: '#555', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Total mensual</div>
              <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{totalMensual.toFixed(2)}€</div>
            </div>
            {pendientes.length > 0 && (
              <div>
                <div style={{ color: '#555', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Pendientes</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: '#f39c12' }}>{pendientes.length}</div>
              </div>
            )}
          </div>
          <button
            onClick={() => generarMut.mutate()}
            disabled={generarMut.isPending || pendientes.length === 0}
            style={{
              ...btnStyle,
              background: pendientes.length > 0 ? '#3498db' : '#1e2a35',
              opacity: pendientes.length === 0 ? 0.5 : 1,
            }}>
            {generarMut.isPending ? 'Generando...' : pendientes.length > 0
              ? `Generar ${pendientes.length} este mes`
              : 'Todo generado'}
          </button>
        </div>
      )}

      {isLoading ? <p style={{ color: '#888' }}>Cargando...</p> : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {activos.length === 0 && <p style={{ color: '#444', fontSize: 14 }}>Sin recurrentes. Añade subscripciones, alquiler, etc.</p>}
            {activos.map(r => (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', background: '#1a1a1a', borderRadius: 6, flexWrap: 'wrap' }}>
                {editId === r.id ? (
                  <>
                    <input value={editForm.nombre} onChange={e => setEditForm(f => ({ ...f, nombre: e.target.value }))}
                      style={{ ...inputStyle, flex: 2, minWidth: 100 }} autoFocus />
                    <input type="number" step="0.01" value={editForm.cantidad} onChange={e => setEditForm(f => ({ ...f, cantidad: e.target.value }))}
                      style={{ ...inputStyle, width: 90 }} />
                    <select value={editForm.categoria_id || ''} onChange={e => setEditForm(f => ({ ...f, categoria_id: e.target.value }))} style={{ ...inputStyle, fontSize: 13 }}>
                      <option value="">Sin categoría</option>
                      {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                    </select>
                    <input type="number" min="1" max="28" value={editForm.dia} onChange={e => setEditForm(f => ({ ...f, dia: e.target.value }))}
                      style={{ ...inputStyle, width: 60, textAlign: 'center' }} />
                    <button onClick={() => saveEdit(r.id)} style={btnStyle}>✓</button>
                    <button onClick={() => setEditId(null)} style={btnSecStyle}>✕</button>
                  </>
                ) : (
                  <>
                    <span style={{ flex: 1, fontSize: 14, minWidth: 100 }}>{r.nombre}</span>
                    {r.categoria_nombre && (
                      <span style={{ background: '#1e2a35', color: '#5aafdf', padding: '2px 8px', borderRadius: 10, fontSize: 11 }}>
                        {r.categoria_nombre}
                      </span>
                    )}
                    <span style={{ color: '#666', fontSize: 12 }}>día {r.dia}</span>
                    <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: '#fff', minWidth: 70, textAlign: 'right' }}>
                      {r.cantidad.toFixed(2)}€
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 600,
                      background: r.generado_este_mes ? '#1a2a1a' : '#2a1e0a',
                      color: r.generado_este_mes ? '#4caf50' : '#f39c12',
                    }}>
                      {r.generado_este_mes ? 'generado' : 'pendiente'}
                    </span>
                    <button onClick={() => { setEditId(r.id); setEditForm({ nombre: r.nombre, cantidad: r.cantidad, categoria_id: r.categoria_id, dia: r.dia }) }}
                      style={{ ...btnSecStyle, fontSize: 12, padding: '4px 10px' }}>
                      Editar
                    </button>
                    {confirmDelete === r.id ? (
                      <>
                        <button onClick={() => deleteMut.mutate(r.id)} style={{ ...btnDangerStyle, color: '#e74c3c' }}>✓</button>
                        <button onClick={() => setConfirmDelete(null)} style={btnDangerStyle}>✕</button>
                      </>
                    ) : (
                      <button onClick={() => setConfirmDelete(r.id)} style={btnDangerStyle}>✕</button>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>

          {inactivos.length > 0 && (
            <div style={{ marginTop: 16, color: '#444', fontSize: 13 }}>
              {inactivos.length} inactivo{inactivos.length > 1 ? 's' : ''}
            </div>
          )}
        </>
      )}
    </div>
  )
}
