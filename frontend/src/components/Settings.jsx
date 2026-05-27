import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { spotifyStatus, getDiaryFields, createDiaryField, updateDiaryField, deleteDiaryField, getDiaryCollections, createDiaryCollection, deleteDiaryCollection } from '../api'
import { useToast } from './Toast'

const LABEL = { color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, marginBottom: 12 }
const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14, width: '100%', maxWidth: 300 }
const btnSm = { background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: '2px 6px' }

export default function Settings() {
  const toast = useToast()
  const qc = useQueryClient()

  const [theme, setTheme] = useState(() => localStorage.getItem('theme') || 'dark')
  const [userId, setUserId] = useState(() => localStorage.getItem('telegram_user_id') || '')
  const [spotifyInfo, setSpotifyInfo] = useState(null)

  // Diary state
  const [newField, setNewField] = useState({ name: '', field_type: 'number' })
  const [newCol, setNewCol] = useState({ name: '', type: 'journal' })
  const [confirmDeleteField, setConfirmDeleteField] = useState(null)
  const [confirmDeleteCol, setConfirmDeleteCol] = useState(null)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('theme', theme)
  }, [theme])

  useEffect(() => {
    if (!userId.trim()) { setSpotifyInfo(null); return }
    spotifyStatus(userId.trim())
      .then(s => setSpotifyInfo(s))
      .catch(() => setSpotifyInfo(null))
  }, [userId])

  const handleUserIdBlur = () => localStorage.setItem('telegram_user_id', userId.trim())

  // Diary queries
  const { data: fields = [] } = useQuery({ queryKey: ['diary-fields'], queryFn: getDiaryFields })
  const { data: collections = [] } = useQuery({ queryKey: ['diary-collections'], queryFn: getDiaryCollections })

  const createFieldMut = useMutation({
    mutationFn: createDiaryField,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['diary-fields'] }); setNewField({ name: '', field_type: 'number' }); toast('Field added') },
    onError: () => toast('Error', 'error'),
  })
  const toggleFieldMut = useMutation({
    mutationFn: ({ id, active }) => updateDiaryField(id, { active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['diary-fields'] }),
  })
  const deleteFieldMut = useMutation({
    mutationFn: deleteDiaryField,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['diary-fields'] }); setConfirmDeleteField(null); toast('Field deleted') },
    onError: () => toast('Error', 'error'),
  })
  const createColMut = useMutation({
    mutationFn: createDiaryCollection,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['diary-collections'] }); setNewCol({ name: '', type: 'journal' }); toast('Collection added') },
    onError: () => toast('Error', 'error'),
  })
  const deleteColMut = useMutation({
    mutationFn: deleteDiaryCollection,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['diary-collections'] }); setConfirmDeleteCol(null); toast('Collection deleted') },
    onError: () => toast('Error', 'error'),
  })

  return (
    <div style={{ maxWidth: 520 }}>

      {/* Appearance */}
      <div style={{ marginBottom: 40 }}>
        <div style={LABEL}>Theme</div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[['dark', 'Dark'], ['light', 'Light (pastel)']].map(([val, label]) => (
            <button key={val} onClick={() => setTheme(val)} style={{
              padding: '7px 18px',
              border: theme === val ? '1.5px solid var(--accent)' : '1px solid var(--border)',
              borderRadius: 'var(--radius-sm)',
              background: theme === val ? 'var(--accent-bg)' : 'var(--surface2)',
              color: theme === val ? 'var(--accent)' : 'var(--text-dim)',
              fontSize: 13, cursor: 'pointer', fontWeight: theme === val ? 500 : 400,
            }}>{label}</button>
          ))}
        </div>
      </div>

      {/* Diary — Collections */}
      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: 32, marginBottom: 32 }}>
        <div style={LABEL}>Diary collections</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginBottom: 14 }}>
          {collections.map(c => (
            <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--border-dim)' }}>
              <span style={{ flex: 1, fontSize: 13, color: 'var(--text)' }}>{c.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface3)', padding: '1px 7px', borderRadius: 8 }}>{c.type}</span>
              {confirmDeleteCol === c.id ? (
                <>
                  <button onClick={() => deleteColMut.mutate(c.id)} style={{ ...btnSm, color: 'var(--red)' }}>✓</button>
                  <button onClick={() => setConfirmDeleteCol(null)} style={btnSm}>✕</button>
                </>
              ) : (
                <button onClick={() => setConfirmDeleteCol(c.id)} style={btnSm}>✕</button>
              )}
            </div>
          ))}
          {collections.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No collections yet</div>}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <input
            placeholder="Name"
            value={newCol.name}
            onChange={e => setNewCol(f => ({ ...f, name: e.target.value }))}
            style={{ ...inputStyle, maxWidth: 180, padding: '6px 10px', fontSize: 13 }}
          />
          <select value={newCol.type} onChange={e => setNewCol(f => ({ ...f, type: e.target.value }))}
            style={{ fontSize: 13, padding: '6px 10px', background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', borderRadius: 'var(--radius-sm)' }}>
            <option value="journal">journal</option>
            <option value="timeline">timeline</option>
          </select>
          <button
            onClick={() => { if (newCol.name.trim()) createColMut.mutate(newCol) }}
            style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '6px 14px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
          >+ Add</button>
        </div>
      </div>

      {/* Diary — Metric fields */}
      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: 32, marginBottom: 40 }}>
        <div style={LABEL}>Metric fields</div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0, marginBottom: 14 }}>
          {fields.map(f => (
            <div key={f.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: '1px solid var(--border-dim)', opacity: f.active ? 1 : 0.5 }}>
              <span style={{ flex: 1, fontSize: 13, color: 'var(--text)' }}>{f.name}</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)', background: 'var(--surface3)', padding: '1px 7px', borderRadius: 8 }}>{f.field_type}</span>
              <button
                onClick={() => toggleFieldMut.mutate({ id: f.id, active: !f.active })}
                style={{ ...btnSm, color: f.active ? 'var(--text-dim)' : 'var(--accent)', fontSize: 11 }}
                title={f.active ? 'Deactivate' : 'Activate'}
              >{f.active ? '···' : 'on'}</button>
              {confirmDeleteField === f.id ? (
                <>
                  <button onClick={() => deleteFieldMut.mutate(f.id)} style={{ ...btnSm, color: 'var(--red)' }}>✓</button>
                  <button onClick={() => setConfirmDeleteField(null)} style={btnSm}>✕</button>
                </>
              ) : (
                <button onClick={() => setConfirmDeleteField(f.id)} style={btnSm}>✕</button>
              )}
            </div>
          ))}
          {fields.length === 0 && <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No metric fields yet</div>}
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <input
            placeholder="Field name"
            value={newField.name}
            onChange={e => setNewField(f => ({ ...f, name: e.target.value }))}
            style={{ ...inputStyle, maxWidth: 180, padding: '6px 10px', fontSize: 13 }}
          />
          <select value={newField.field_type} onChange={e => setNewField(f => ({ ...f, field_type: e.target.value }))}
            style={{ fontSize: 13, padding: '6px 10px', background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', borderRadius: 'var(--radius-sm)' }}>
            <option value="number">number</option>
            <option value="text">text</option>
            <option value="scale">scale (1–10)</option>
          </select>
          <button
            onClick={() => { if (newField.name.trim()) createFieldMut.mutate(newField) }}
            style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '6px 14px', borderRadius: 'var(--radius-sm)', fontSize: 13, cursor: 'pointer', fontWeight: 500 }}
          >+ Add</button>
        </div>
      </div>

      {/* Spotify */}
      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: 32 }}>
        <div style={LABEL}>Telegram User ID</div>
        <div style={{ color: 'var(--text-muted)', fontSize: 12, marginBottom: 12 }}>
          Needed to link your Spotify OAuth token. Find it with @userinfobot on Telegram.
        </div>
        <input type="text" value={userId} onChange={e => setUserId(e.target.value)} onBlur={handleUserIdBlur}
          placeholder="e.g. 123456789" style={inputStyle} />
        <div style={{ marginTop: 8, fontSize: 12 }}>
          {spotifyInfo?.authenticated
            ? <span style={{ color: 'var(--green)' }}>✓ Spotify connected as {spotifyInfo.spotify_user}</span>
            : userId ? <span style={{ color: 'var(--text-muted)' }}>○ Not connected</span>
            : null}
        </div>
      </div>

    </div>
  )
}
