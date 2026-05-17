import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMemorias, createMemoria, updateMemoria, deleteMemoria } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: '#1a1a1a', border: '1px solid #333', color: '#eee', padding: '10px 14px', borderRadius: 6, fontSize: 14 }

export default function Memoria() {
  const toast = useToast()
  const qc = useQueryClient()
  const [texto, setTexto] = useState('')
  const [editId, setEditId] = useState(null)
  const [editTexto, setEditTexto] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: memorias = [], isLoading } = useQuery({ queryKey: ['memorias'], queryFn: getMemorias })

  const createMut = useMutation({
    mutationFn: createMemoria,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memorias'] }); setTexto(''); toast('Guardado') },
    onError: () => toast('Error al guardar', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, hecho }) => updateMemoria(id, hecho),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memorias'] }); setEditId(null); toast('Actualizado') },
    onError: () => toast('Error al actualizar', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMemoria,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memorias'] }); setConfirmDelete(null); toast('Olvidado') },
    onError: () => toast('Error al borrar', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!texto.trim()) return
    createMut.mutate(texto.trim())
  }

  const startEdit = (m) => { setEditId(m.id); setEditTexto(m.hecho); setConfirmDelete(null) }
  const saveEdit = () => { if (editTexto.trim()) updateMut.mutate({ id: editId, hecho: editTexto.trim() }) }

  return (
    <div>
      <p style={{ color: '#555', fontSize: 13, margin: '0 0 20px' }}>
        Hechos que Claude recuerda en cada conversación de Telegram.
      </p>

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
        <input
          type="text"
          placeholder="Añadir hecho..."
          value={texto}
          onChange={e => setTexto(e.target.value)}
          style={{ ...inputStyle, flex: 1 }}
        />
        <button type="submit" disabled={createMut.isPending || !texto.trim()}
          style={{ background: '#3498db', border: 'none', color: '#fff', padding: '10px 18px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
          + Guardar
        </button>
      </form>

      {isLoading ? <p style={{ color: '#888' }}>Cargando...</p> : (
        memorias.length === 0 ? (
          <p style={{ color: '#444', fontSize: 14 }}>Sin memoria guardada.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {memorias.map(m => (
              <div key={m.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '11px 14px', background: '#1a1a1a', borderRadius: 8 }}>
                <span style={{ color: '#444', fontSize: 11, whiteSpace: 'nowrap', marginTop: 3, minWidth: 28 }}>#{m.id}</span>

                {editId === m.id ? (
                  <div style={{ flex: 1, display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                    <textarea
                      value={editTexto}
                      onChange={e => setEditTexto(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit() } if (e.key === 'Escape') setEditId(null) }}
                      style={{ ...inputStyle, flex: 1, resize: 'vertical', minHeight: 60, lineHeight: 1.5 }}
                      autoFocus
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <button onClick={saveEdit} disabled={updateMut.isPending}
                        style={{ background: '#3498db', border: 'none', color: '#fff', padding: '4px 10px', borderRadius: 5, cursor: 'pointer', fontSize: 13 }}>✓</button>
                      <button onClick={() => setEditId(null)}
                        style={{ background: '#2a2a2a', border: '1px solid #444', color: '#ccc', padding: '4px 10px', borderRadius: 5, cursor: 'pointer', fontSize: 13 }}>✕</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <span
                      style={{ flex: 1, fontSize: 14, color: '#ddd', lineHeight: 1.5, cursor: 'pointer' }}
                      onClick={() => startEdit(m)}
                      title="Click para editar"
                    >{m.hecho}</span>
                    <span style={{ color: '#333', fontSize: 11, whiteSpace: 'nowrap', marginTop: 3 }}>
                      {new Date(m.fecha).toLocaleDateString('es-ES')}
                    </span>
                    {confirmDelete === m.id ? (
                      <span style={{ display: 'flex', gap: 4 }}>
                        <button onClick={() => deleteMut.mutate(m.id)}
                          style={{ background: 'none', border: 'none', color: '#e74c3c', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✓</button>
                        <button onClick={() => setConfirmDelete(null)}
                          style={{ background: 'none', border: 'none', color: '#555', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✕</button>
                      </span>
                    ) : (
                      <button onClick={() => { setConfirmDelete(m.id); setEditId(null) }}
                        style={{ background: 'none', border: 'none', color: '#333', cursor: 'pointer', padding: '0 4px', fontSize: 16, lineHeight: 1 }}>✕</button>
                    )}
                  </>
                )}
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
