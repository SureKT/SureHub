import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRecurrentes, createRecurrente, updateRecurrente, deleteRecurrente, generarRecurrentes, getCategorias } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14 }
const btnStyle = { background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '8px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
const btnSecStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: 'var(--text-dim)', padding: '4px 8px', cursor: 'pointer', fontSize: 15 }

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
      <p style={{ color: 'var(--text-dim)', fontSize: 13, margin: '0 0 20px' }}>
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
          <span style={{ color: 'var(--text-dim)', fontSize: 13 }}>Día</span>
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
              <div style={{ color: 'var(--text-dim)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Total mensual</div>
              <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>{totalMensual.toFixed(2)}€</div>
            </div>
            {pendientes.length > 0 && (
              <div>
                <div style={{ color: 'var(--text-dim)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Pendientes</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--orange)' }}>{pendientes.length}</div>
              </div>
            )}
          </div>
          <button
            onClick={() => generarMut.mutate()}
            disabled={generarMut.isPending || pendientes.length === 0}
            style={{
              ...btnStyle,
              background: pendientes.length > 0 ? 'var(--accent)' : 'var(--surface2)',
              opacity: pendientes.length === 0 ? 0.5 : 1,
            }}>
            {generarMut.isPending ? 'Generando...' : pendientes.length > 0
              ? `Generar ${pendientes.length} este mes`
              : 'Todo generado'}
          </button>
        </div>
      )}

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Cargando...</p> : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {activos.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>Sin recurrentes. Añade subscripciones, alquiler, etc.</p>}
            {activos.map(r => (
              <div key={r.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border-dim)', flexWrap: 'wrap' }}>
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
                      <span style={{ background: 'var(--surface3)', color: 'var(--text-dim)', padding: '2px 8px', borderRadius: 10, fontSize: 11 }}>
                        {r.categoria_nombre}
                      </span>
                    )}
                    <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>día {r.dia}</span>
                    <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text)', minWidth: 70, textAlign: 'right' }}>
                      {r.cantidad.toFixed(2)}€
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 600,
                      background: r.generado_este_mes ? 'var(--green-bg)' : 'var(--orange-bg)',
                      color: r.generado_este_mes ? 'var(--green)' : 'var(--orange)',
                    }}>
                      {r.generado_este_mes ? 'generado' : 'pendiente'}
                    </span>
                    <button onClick={() => { setEditId(r.id); setEditForm({ nombre: r.nombre, cantidad: r.cantidad, categoria_id: r.categoria_id, dia: r.dia }) }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 15, padding: '4px 8px', lineHeight: 1 }}
                      title="Editar">✎</button>
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
            <div style={{ marginTop: 16, color: 'var(--text-muted)', fontSize: 13 }}>
              {inactivos.length} inactivo{inactivos.length > 1 ? 's' : ''}
            </div>
          )}
        </>
      )}
    </div>
  )
}
