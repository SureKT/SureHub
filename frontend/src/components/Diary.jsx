import { useState, useEffect, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDiaryCollections, getDiaryFields, getDiaryEntries, createDiaryEntry, updateDiaryEntry, deleteDiaryEntry } from '../api'
import { useToast } from './Toast'

function formatDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

function localDatetimeValue(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function Diary() {
  const toast = useToast()
  const qc = useQueryClient()
  const editorRef = useRef()

  const [selectedId, setSelectedId] = useState(null)
  const [filterCol, setFilterCol] = useState(null)
  const [draft, setDraft] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: collections = [] } = useQuery({ queryKey: ['diary-collections'], queryFn: getDiaryCollections })
  const { data: fields = [] } = useQuery({ queryKey: ['diary-fields'], queryFn: getDiaryFields })
  const { data: entriesData = { items: [], total: 0 } } = useQuery({
    queryKey: ['diary-entries', filterCol],
    queryFn: () => getDiaryEntries(filterCol ? { collection_id: filterCol } : {}),
    refetchOnWindowFocus: false,
  })
  const entries = entriesData.items || []

  const createMut = useMutation({
    mutationFn: createDiaryEntry,
    onSuccess: (e) => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      setSelectedId(e.id)
      setDraft(entryToDraft(e))
      toast('Entry created')
    },
    onError: () => toast('Error creating entry', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateDiaryEntry(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      toast('Saved')
    },
    onError: () => toast('Error saving', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteDiaryEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      setSelectedId(null)
      setDraft(null)
      setConfirmDelete(null)
      toast('Deleted')
    },
    onError: () => toast('Error deleting', 'error'),
  })

  const selectedEntry = entries.find(e => e.id === selectedId) || null

  useEffect(() => {
    if (selectedEntry && (!draft || draft._id !== selectedEntry.id)) {
      setDraft(entryToDraft(selectedEntry))
    }
  }, [selectedId, entries.length])

  function entryToDraft(e) {
    const metricMap = {}
    for (const m of (e.metrics || [])) metricMap[m.field_id] = m.value
    return {
      _id: e.id,
      title: e.title || '',
      text: e.text || '',
      date: localDatetimeValue(e.date),
      collection_id: e.collection_id || '',
      metrics: metricMap,
    }
  }

  function newEntry() {
    createMut.mutate({
      date: new Date().toISOString(),
      collection_id: filterCol || null,
    })
  }

  function saveDraft() {
    if (!draft || !selectedId) return
    const metrics = fields.filter(f => f.active).map(f => ({
      field_id: f.id,
      value: draft.metrics[f.id] || '',
    })).filter(m => m.value !== '')
    updateMut.mutate({
      id: selectedId,
      data: {
        title: draft.title || null,
        text: draft.text || null,
        date: draft.date ? new Date(draft.date).toISOString() : undefined,
        collection_id: draft.collection_id ? parseInt(draft.collection_id) : null,
        metrics,
      },
    })
  }

  const activeFields = fields.filter(f => f.active)

  return (
    <div style={{ display: 'flex', gap: 0, height: 'calc(100vh - 64px)', minHeight: 0 }}>

      {/* Left — entry list */}
      <div style={{
        width: 260, minWidth: 260, borderRight: '1px solid var(--border-dim)',
        display: 'flex', flexDirection: 'column', height: '100%',
      }}>
        {/* Filter + New */}
        <div style={{ padding: '0 0 12px 0', borderBottom: '1px solid var(--border-dim)', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <select
              value={filterCol || ''}
              onChange={e => { setFilterCol(e.target.value ? parseInt(e.target.value) : null); setSelectedId(null); setDraft(null) }}
              style={{ flex: 1, fontSize: 12, padding: '5px 8px', background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', borderRadius: 'var(--radius-sm)' }}
            >
              <option value="">All</option>
              {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <button
              onClick={newEntry}
              style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '5px 10px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
            >+</button>
          </div>
        </div>

        {/* Entry list */}
        <div style={{ flex: 1, overflowY: 'auto', paddingTop: 4 }}>
          {entries.length === 0 && (
            <div style={{ textAlign: 'center', padding: '32px 16px' }}>
              <div style={{ fontSize: 24, color: 'var(--text-muted)', marginBottom: 8 }}>○</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No entries yet</div>
            </div>
          )}
          {entries.map(e => {
            const isActive = e.id === selectedId
            const preview = e.text ? e.text.slice(0, 60).replace(/\n/g, ' ') : ''
            return (
              <div
                key={e.id}
                onClick={() => { setSelectedId(e.id); setConfirmDelete(null) }}
                style={{
                  padding: '10px 12px', cursor: 'pointer',
                  borderLeft: isActive ? '2px solid var(--accent)' : '2px solid transparent',
                  background: isActive ? 'var(--surface2)' : 'none',
                  borderBottom: '1px solid var(--border-dim)',
                  transition: 'background 0.1s',
                }}
                onMouseEnter={e2 => { if (!isActive) e2.currentTarget.style.background = 'var(--surface3)' }}
                onMouseLeave={e2 => { if (!isActive) e2.currentTarget.style.background = 'none' }}
              >
                <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>{formatDate(e.date)}</div>
                <div style={{ fontSize: 13, color: 'var(--text)', fontWeight: e.title ? 500 : 400, lineHeight: 1.3 }}>
                  {e.title || preview || <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>empty</span>}
                </div>
                {e.collection_name && (
                  <div style={{ marginTop: 4 }}>
                    <span style={{ background: 'var(--surface3)', color: 'var(--text-muted)', fontSize: 10, padding: '1px 6px', borderRadius: 8 }}>{e.collection_name}</span>
                  </div>
                )}
                {e.metrics?.length > 0 && (
                  <div style={{ marginTop: 3, fontSize: 10, color: 'var(--text-muted)' }}>
                    {e.metrics.length} metric{e.metrics.length > 1 ? 's' : ''}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Right — editor */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%', minWidth: 0 }}>
        {!selectedId || !draft ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 32, color: 'var(--text-muted)', marginBottom: 12 }}>○</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Select an entry or create a new one</div>
            </div>
          </div>
        ) : (
          <>
            {/* Editor toolbar */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '0 0 12px 24px',
              borderBottom: '1px solid var(--border-dim)', flexShrink: 0, flexWrap: 'wrap',
            }}>
              <input
                type="datetime-local"
                value={draft.date}
                onChange={e => setDraft(d => ({ ...d, date: e.target.value }))}
                style={{ fontSize: 12, padding: '4px 8px', color: 'var(--text-dim)', background: 'var(--surface2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', colorScheme: 'dark' }}
              />
              <select
                value={draft.collection_id}
                onChange={e => setDraft(d => ({ ...d, collection_id: e.target.value }))}
                style={{ fontSize: 12, padding: '4px 8px', background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', borderRadius: 'var(--radius-sm)' }}
              >
                <option value="">No collection</option>
                {collections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <div style={{ flex: 1 }} />
              {confirmDelete === selectedId ? (
                <>
                  <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Delete?</span>
                  <button onClick={() => deleteMut.mutate(selectedId)} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 13 }}>✓</button>
                  <button onClick={() => setConfirmDelete(null)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 13 }}>✕</button>
                </>
              ) : (
                <button onClick={() => setConfirmDelete(selectedId)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: '4px 8px' }}>✕</button>
              )}
              <button
                onClick={saveDraft}
                disabled={updateMut.isPending}
                style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '5px 14px', borderRadius: 'var(--radius-sm)', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
              >{updateMut.isPending ? '…' : 'Save'}</button>
            </div>

            {/* Editor content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }} ref={editorRef}>
              <input
                type="text"
                placeholder="Title (optional)"
                value={draft.title}
                onChange={e => setDraft(d => ({ ...d, title: e.target.value }))}
                style={{
                  width: '100%', background: 'none', border: 'none', outline: 'none',
                  fontSize: 22, fontWeight: 500, color: 'var(--text)', marginBottom: 16,
                  padding: 0,
                }}
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); editorRef.current?.querySelector('textarea')?.focus() } }}
              />
              <textarea
                placeholder="Write something…"
                value={draft.text}
                onChange={e => setDraft(d => ({ ...d, text: e.target.value }))}
                style={{
                  width: '100%', background: 'none', border: 'none', outline: 'none',
                  fontSize: 14, color: 'var(--text)', lineHeight: 1.8, resize: 'none',
                  minHeight: 200, padding: 0, fontFamily: 'inherit',
                }}
              />

              {/* Metrics */}
              {activeFields.length > 0 && (
                <div style={{ marginTop: 32, borderTop: '1px solid var(--border-dim)', paddingTop: 20 }}>
                  <div style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 14 }}>Metrics</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
                    {activeFields.map(f => (
                      <div key={f.id} style={{ minWidth: 120 }}>
                        <div style={{ color: 'var(--text-muted)', fontSize: 11, marginBottom: 5 }}>{f.name}</div>
                        {f.field_type === 'scale' ? (
                          <div style={{ display: 'flex', gap: 4 }}>
                            {[1,2,3,4,5,6,7,8,9,10].map(n => {
                              const active = parseInt(draft.metrics[f.id]) === n
                              return (
                                <button
                                  key={n}
                                  onClick={() => setDraft(d => ({ ...d, metrics: { ...d.metrics, [f.id]: active ? '' : String(n) } }))}
                                  style={{
                                    width: 24, height: 24, padding: 0, border: active ? '1.5px solid var(--accent)' : '1px solid var(--border)',
                                    borderRadius: 4, background: active ? 'var(--accent-bg)' : 'var(--surface2)',
                                    color: active ? 'var(--accent)' : 'var(--text-dim)', fontSize: 11, cursor: 'pointer',
                                  }}
                                >{n}</button>
                              )
                            })}
                          </div>
                        ) : (
                          <input
                            type={f.field_type === 'number' ? 'number' : 'text'}
                            step="0.1"
                            value={draft.metrics[f.id] || ''}
                            onChange={e => setDraft(d => ({ ...d, metrics: { ...d.metrics, [f.id]: e.target.value } }))}
                            placeholder={f.field_type === 'number' ? '0' : '…'}
                            style={{ width: 90, fontSize: 13, padding: '4px 8px', background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)' }}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
