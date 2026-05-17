import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMemorias, createMemoria, deleteMemoria } from '../api'
import { useToast } from './Toast'

export default function Memoria() {
  const toast = useToast()
  const qc = useQueryClient()
  const [texto, setTexto] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: memorias = [], isLoading } = useQuery({ queryKey: ['memorias'], queryFn: getMemorias })

  const createMut = useMutation({
    mutationFn: createMemoria,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memorias'] })
      setTexto('')
      toast('Guardado en memoria')
    },
    onError: () => toast('Error al guardar', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMemoria,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['memorias'] })
      setConfirmDelete(null)
      toast('Olvidado')
    },
    onError: () => toast('Error al borrar', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!texto.trim()) return
    createMut.mutate(texto.trim())
  }

  return (
    <div>
      <p style={{ color: '#666', fontSize: 13, margin: '0 0 20px' }}>
        Hechos que Claude recuerda en cada conversación de Telegram.
      </p>

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
        <input
          type="text"
          placeholder="Añadir hecho..."
          value={texto}
          onChange={e => setTexto(e.target.value)}
          style={{ flex: 1, background: '#1a1a1a', border: '1px solid #333', color: '#eee', padding: '10px 14px', borderRadius: 6, fontSize: 14 }}
        />
        <button type="submit" disabled={createMut.isPending || !texto.trim()}
          style={{ background: '#3498db', border: 'none', color: '#fff', padding: '10px 18px', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
          + Guardar
        </button>
      </form>

      {isLoading ? <p style={{ color: '#888' }}>Cargando...</p> : (
        memorias.length === 0 ? (
          <p style={{ color: '#444', fontSize: 14 }}>Sin memoria guardada. Añade hechos relevantes sobre ti.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {memorias.map(m => (
              <div key={m.id} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '12px 14px', background: '#1a1a1a', borderRadius: 8 }}>
                <span style={{ color: '#555', fontSize: 11, whiteSpace: 'nowrap', marginTop: 2 }}>#{m.id}</span>
                <span style={{ flex: 1, fontSize: 14, color: '#ddd', lineHeight: 1.5 }}>{m.hecho}</span>
                <span style={{ color: '#444', fontSize: 11, whiteSpace: 'nowrap', marginTop: 2 }}>
                  {new Date(m.fecha).toLocaleDateString('es-ES')}
                </span>
                {confirmDelete === m.id ? (
                  <span style={{ display: 'flex', gap: 4 }}>
                    <button onClick={() => deleteMut.mutate(m.id)}
                      style={{ background: 'none', border: 'none', color: '#e74c3c', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✓</button>
                    <button onClick={() => setConfirmDelete(null)}
                      style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✕</button>
                  </span>
                ) : (
                  <button onClick={() => setConfirmDelete(m.id)}
                    style={{ background: 'none', border: 'none', color: '#444', cursor: 'pointer', padding: '0 4px', fontSize: 16 }}>✕</button>
                )}
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}
