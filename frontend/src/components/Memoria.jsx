import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getMemories, createMemory, updateMemory, deleteMemory } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: 14 }

export default function Memoria() {
  const toast = useToast()
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [editId, setEditId] = useState(null)
  const [editText, setEditText] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: memories = [], isLoading } = useQuery({ queryKey: ['memories'], queryFn: getMemories })

  const createMut = useMutation({
    mutationFn: createMemory,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memories'] }); setText(''); toast('Saved') },
    onError: () => toast('Error saving', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, fact }) => updateMemory(id, fact),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memories'] }); setEditId(null); toast('Updated') },
    onError: () => toast('Error updating', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteMemory,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['memories'] }); setConfirmDelete(null); toast('Forgotten') },
    onError: () => toast('Error deleting', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!text.trim()) return
    createMut.mutate(text.trim())
  }

  const startEdit = (m) => { setEditId(m.id); setEditText(m.fact); setConfirmDelete(null) }
  const saveEdit = () => { if (editText.trim()) updateMut.mutate({ id: editId, fact: editText.trim() }) }

  return (
    <div>

      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28 }}>
        <input
          type="text"
          placeholder="Add fact..."
          value={text}
          onChange={e => setText(e.target.value)}
          style={{ ...inputStyle, flex: 1 }}
        />
        <button type="submit" disabled={createMut.isPending || !text.trim()}
          style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '10px 18px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 500 }}>
          + Save
        </button>
      </form>

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Loading...</p> : (
        memories.length === 0 ? (
          <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No memories saved.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {memories.map(m => (
              <div key={m.id}
                style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '11px 0', borderBottom: '1px solid var(--border-dim)' }}
                onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
                onMouseLeave={e => e.currentTarget.style.opacity = '1'}
              >
                {editId === m.id ? (
                  <div style={{ flex: 1, display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                    <textarea
                      value={editText}
                      onChange={e => setEditText(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); saveEdit() } if (e.key === 'Escape') setEditId(null) }}
                      style={{ ...inputStyle, flex: 1, resize: 'vertical', minHeight: 60, lineHeight: 1.5 }}
                      autoFocus
                    />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <button onClick={saveEdit} disabled={updateMut.isPending}
                        style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '4px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>✓</button>
                      <button onClick={() => setEditId(null)}
                        style={{ background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '4px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }}>✕</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <span
                      style={{ flex: 1, fontSize: 14, color: 'var(--text)', lineHeight: 1.5, cursor: 'pointer' }}
                      onClick={() => startEdit(m)}
                      title="Click to edit"
                    >{m.fact}</span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11, whiteSpace: 'nowrap', marginTop: 3 }}>
                      {new Date(m.date).toLocaleDateString('en-GB')}
                    </span>
                    {confirmDelete === m.id ? (
                      <span style={{ display: 'flex', gap: 4 }}>
                        <button onClick={() => deleteMut.mutate(m.id)}
                          style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✓</button>
                        <button onClick={() => setConfirmDelete(null)}
                          style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: '0 4px', fontSize: 14 }}>✗</button>
                      </span>
                    ) : (
                      <button onClick={() => { setConfirmDelete(m.id); setEditId(null) }}
                        style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: '0 4px', fontSize: 16, lineHeight: 1 }}>✕</button>
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
