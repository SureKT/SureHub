import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getDiaryCollections, getDiaryEntries, createDiaryEntry, updateDiaryEntry, deleteDiaryEntry } from '../api'
import { useToast } from './Toast'

function formatDateLong(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })
}

function formatYear(iso) {
  return iso ? new Date(iso).getFullYear() : ''
}

function localDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const pad = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`
}

export default function Timeline() {
  const toast = useToast()
  const qc = useQueryClient()
  const [editId, setEditId] = useState(null)
  const [editDraft, setEditDraft] = useState({})
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [newForm, setNewForm] = useState({ title: '', text: '', date: localDate(new Date().toISOString()), collection_id: '' })
  const [showNew, setShowNew] = useState(false)

  const { data: collections = [] } = useQuery({ queryKey: ['diary-collections'], queryFn: getDiaryCollections })
  const timelineCollections = collections.filter(c => c.type === 'timeline')

  const { data: entriesData = { items: [] } } = useQuery({
    queryKey: ['diary-entries-timeline'],
    queryFn: () => getDiaryEntries({ per_page: 200 }),
    refetchOnWindowFocus: false,
    select: (data) => ({
      ...data,
      items: (data.items || [])
        .filter(e => e.collection_type === 'timeline')
        .sort((a, b) => new Date(a.date) - new Date(b.date)),
    }),
  })
  const events = entriesData.items || []

  const createMut = useMutation({
    mutationFn: createDiaryEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      qc.invalidateQueries({ queryKey: ['diary-entries-timeline'] })
      setNewForm({ title: '', text: '', date: localDate(new Date().toISOString()), collection_id: '' })
      setShowNew(false)
      toast('Event added')
    },
    onError: () => toast('Error adding event', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateDiaryEntry(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      qc.invalidateQueries({ queryKey: ['diary-entries-timeline'] })
      setEditId(null)
      toast('Updated')
    },
    onError: () => toast('Error updating', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteDiaryEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['diary-entries'] })
      qc.invalidateQueries({ queryKey: ['diary-entries-timeline'] })
      setConfirmDelete(null)
      toast('Deleted')
    },
    onError: () => toast('Error deleting', 'error'),
  })

  const submitNew = (e) => {
    e.preventDefault()
    if (!newForm.title.trim()) return
    createMut.mutate({
      title: newForm.title,
      text: newForm.text || null,
      date: new Date(newForm.date).toISOString(),
      collection_id: newForm.collection_id ? parseInt(newForm.collection_id) : null,
    })
  }

  if (timelineCollections.length === 0 && events.length === 0) {
    return (
      <div>
        <div style={{ textAlign: 'center', padding: '48px 0' }}>
          <div style={{ fontSize: 32, color: 'var(--text-muted)', marginBottom: 12 }}>○</div>
          <div style={{ color: 'var(--text-dim)', fontSize: 14, fontWeight: 500 }}>No timeline collections</div>
          <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4, marginBottom: 24 }}>
            Create a collection with type "timeline" in Diary settings to add events.
          </div>
        </div>
      </div>
    )
  }

  let lastYear = null

  return (
    <div style={{ maxWidth: 640 }}>
      {/* Add event */}
      <div style={{ marginBottom: 32 }}>
        {!showNew ? (
          <button
            onClick={() => setShowNew(true)}
            style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '8px 18px', borderRadius: 'var(--radius-sm)', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}
          >+ Add event</button>
        ) : (
          <form onSubmit={submitNew} style={{ background: 'var(--surface2)', border: '1px solid var(--border-dim)', borderRadius: 'var(--radius)', padding: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              type="date"
              value={newForm.date}
              onChange={e => setNewForm(f => ({ ...f, date: e.target.value }))}
              style={{ fontSize: 13, padding: '5px 8px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)', colorScheme: 'dark', width: 'fit-content' }}
            />
            <input
              type="text"
              placeholder="Title *"
              value={newForm.title}
              onChange={e => setNewForm(f => ({ ...f, title: e.target.value }))}
              style={{ fontSize: 14, padding: '7px 10px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)' }}
              required autoFocus
            />
            <textarea
              placeholder="Details (optional)"
              value={newForm.text}
              onChange={e => setNewForm(f => ({ ...f, text: e.target.value }))}
              style={{ fontSize: 13, padding: '7px 10px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)', resize: 'vertical', minHeight: 60, fontFamily: 'inherit' }}
            />
            <select
              value={newForm.collection_id}
              onChange={e => setNewForm(f => ({ ...f, collection_id: e.target.value }))}
              style={{ fontSize: 13, padding: '5px 8px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text-dim)', borderRadius: 'var(--radius-sm)', width: 'fit-content' }}
            >
              <option value="">No collection</option>
              {timelineCollections.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <div style={{ display: 'flex', gap: 8 }}>
              <button type="submit" disabled={createMut.isPending} style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '7px 16px', borderRadius: 'var(--radius-sm)', fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>
                {createMut.isPending ? '…' : 'Add'}
              </button>
              <button type="button" onClick={() => setShowNew(false)} style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '7px 12px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer' }}>
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {events.length === 0 && (
        <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>No events yet. Add your first one above.</div>
      )}

      {/* Timeline */}
      <div style={{ position: 'relative', paddingLeft: 32 }}>
        {/* Vertical line */}
        <div style={{ position: 'absolute', left: 7, top: 0, bottom: 0, width: 1, background: 'var(--border-dim)' }} />

        {events.map((e, i) => {
          const year = formatYear(e.date)
          const showYear = year !== lastYear
          lastYear = year

          return (
            <div key={e.id}>
              {showYear && (
                <div style={{ position: 'relative', marginBottom: 8, marginTop: i > 0 ? 24 : 0 }}>
                  <div style={{ position: 'absolute', left: -32, top: '50%', transform: 'translateY(-50%)', width: 15, height: 15, borderRadius: '50%', background: 'var(--surface3)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <div style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--text-muted)' }} />
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 1.2, fontWeight: 500 }}>{year}</span>
                </div>
              )}

              <div style={{ position: 'relative', marginBottom: 16 }}>
                {/* Dot */}
                <div style={{ position: 'absolute', left: -29, top: 6, width: 9, height: 9, borderRadius: '50%', background: 'var(--accent-bg)', border: '1.5px solid var(--accent)' }} />

                {editId === e.id ? (
                  <div style={{ background: 'var(--surface2)', border: '1px solid var(--border-dim)', borderRadius: 'var(--radius)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <input type="date" value={localDate(editDraft.date)} onChange={ev => setEditDraft(d => ({ ...d, date: ev.target.value }))}
                      style={{ fontSize: 12, padding: '4px 8px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)', colorScheme: 'dark', width: 'fit-content' }} />
                    <input type="text" value={editDraft.title} onChange={ev => setEditDraft(d => ({ ...d, title: ev.target.value }))}
                      style={{ fontSize: 14, padding: '5px 8px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)' }} autoFocus />
                    <textarea value={editDraft.text} onChange={ev => setEditDraft(d => ({ ...d, text: ev.target.value }))}
                      style={{ fontSize: 13, padding: '5px 8px', background: 'var(--surface3)', border: '1px solid var(--border)', color: 'var(--text)', borderRadius: 'var(--radius-sm)', resize: 'vertical', minHeight: 50, fontFamily: 'inherit' }} />
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => updateMut.mutate({ id: e.id, data: { title: editDraft.title, text: editDraft.text || null, date: new Date(editDraft.date).toISOString() } })}
                        style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '5px 12px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer' }}>Save</button>
                      <button onClick={() => setEditId(null)} style={{ background: 'none', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '5px 10px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer' }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{ padding: '6px 0' }}
                    onMouseEnter={ev => ev.currentTarget.querySelector('.entry-actions').style.opacity = '1'}
                    onMouseLeave={ev => ev.currentTarget.querySelector('.entry-actions').style.opacity = '0'}
                  >
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text)' }}>{e.title}</span>
                      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{formatDateLong(e.date)}</span>
                      <span className="entry-actions" style={{ opacity: 0, transition: 'opacity 0.15s', display: 'flex', gap: 4, marginLeft: 4 }}>
                        <button onClick={() => { setEditId(e.id); setEditDraft({ title: e.title || '', text: e.text || '', date: localDate(e.date) }) }}
                          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: '0 4px' }}>✎</button>
                        {confirmDelete === e.id ? (
                          <>
                            <button onClick={() => deleteMut.mutate(e.id)} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 13 }}>✓</button>
                            <button onClick={() => setConfirmDelete(null)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 13 }}>✕</button>
                          </>
                        ) : (
                          <button onClick={() => setConfirmDelete(e.id)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: '0 4px' }}>✕</button>
                        )}
                      </span>
                    </div>
                    {e.text && <div style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 3, lineHeight: 1.5 }}>{e.text}</div>}
                    {e.collection_name && (
                      <span style={{ background: 'var(--surface3)', color: 'var(--text-muted)', fontSize: 10, padding: '1px 6px', borderRadius: 8, marginTop: 4, display: 'inline-block' }}>{e.collection_name}</span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
