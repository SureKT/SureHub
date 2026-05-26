import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCategories, createCategory, updateCategory, deleteCategory, getSummary } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14 }
const btnStyle = { background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '8px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
const btnSecStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '6px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: 'var(--text-dim)', padding: '6px 8px', cursor: 'pointer', fontSize: 15 }

export default function Categorias() {
  const toast = useToast()
  const qc = useQueryClient()
  const [showInactive, setShowInactive] = useState(false)

  const { data: categories = [], isLoading } = useQuery({
    queryKey: ['categories', 'all'],
    queryFn: () => getCategories({ active_only: false }),
  })
  const { data: summary } = useQuery({
    queryKey: ['summary'],
    queryFn: () => getSummary(),
    refetchInterval: 30000,
  })

  const [form, setForm] = useState({ name: '', type: 'variable', monthly_estimate: '' })
  const [editId, setEditId] = useState(null)
  const [editVal, setEditVal] = useState('')
  const [confirmDelete, setConfirmDelete] = useState(null)

  const summaryMap = Object.fromEntries((summary?.categories || []).map(r => [r.id, r]))

  const createMut = useMutation({
    mutationFn: createCategory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
      setForm({ name: '', type: 'variable', monthly_estimate: '' })
      toast('Category created')
    },
    onError: (e) => toast(e?.response?.data?.detail || 'Error creating category', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateCategory(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      setEditId(null)
      toast('Updated')
    },
    onError: () => toast('Error updating', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteCategory,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['categories'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      setConfirmDelete(null)
      toast('Category deleted')
    },
    onError: () => toast('Error deleting', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    createMut.mutate({ ...form, monthly_estimate: parseFloat(form.monthly_estimate) || 0 })
  }

  const active = categories.filter(c => c.active)
  const inactive = categories.filter(c => !c.active)
  const variable = active.filter(c => c.type === 'variable')
  const fixed = active.filter(c => c.type === 'fixed')

  const CatRow = ({ c }) => {
    const mes = summaryMap[c.id]
    const alert = mes?.alert
    return (
      <div
        style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0',
          borderBottom: '1px solid var(--border-dim)',
          opacity: c.active ? 1 : 0.55, flexWrap: 'wrap',
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = c.active ? '0.8' : '0.45'}
        onMouseLeave={e => e.currentTarget.style.opacity = c.active ? '1' : '0.55'}
      >
        <span style={{ flex: 1, fontSize: 14, color: alert ? 'var(--red)' : (c.active ? 'var(--text)' : 'var(--text-dim)'), minWidth: 100 }}>
          {c.name}
        </span>
        {mes && c.active && (
          <span style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums', color: alert ? 'var(--red)' : 'var(--text-dim)' }}>
            <span style={{ fontWeight: 600 }}>{mes.total.toFixed(2)}€</span>
            {c.monthly_estimate > 0 && (
              <span style={{ color: 'var(--text-muted)' }}> / {c.monthly_estimate.toFixed(0)}€</span>
            )}
          </span>
        )}
        {editId === c.id ? (
          <>
            <input type="number" step="0.01" value={editVal} onChange={e => setEditVal(e.target.value)}
              style={{ ...inputStyle, width: 90, fontSize: 13, padding: '4px 8px' }} autoFocus
              onKeyDown={e => { if (e.key === 'Enter') updateMut.mutate({ id: c.id, data: { monthly_estimate: parseFloat(editVal) } }) }}
            />
            <button onClick={() => updateMut.mutate({ id: c.id, data: { monthly_estimate: parseFloat(editVal) } })} style={{ ...btnStyle, padding: '4px 10px', fontSize: 13 }}>✓</button>
            <button onClick={() => setEditId(null)} style={{ ...btnSecStyle, padding: '4px 8px', fontSize: 13 }}>✕</button>
          </>
        ) : (
          <>
            <button
              onClick={() => { setEditId(c.id); setEditVal(c.monthly_estimate) }}
              style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 14, padding: '2px 6px', lineHeight: 1 }}
              title="Edit budget"
            >✎</button>
            <button
              onClick={() => updateMut.mutate({ id: c.id, data: { active: !c.active } })}
              style={{ background: 'none', border: 'none', color: c.active ? 'var(--text-dim)' : 'var(--accent)', cursor: 'pointer', fontSize: 11, padding: '2px 6px', letterSpacing: 0.3 }}
              title={c.active ? 'Deactivate' : 'Activate'}
            >
              {c.active ? '···' : 'activate'}
            </button>
            {confirmDelete === c.id ? (
              <>
                <button onClick={() => deleteMut.mutate(c.id)} style={{ ...btnDangerStyle, color: 'var(--red)' }}>✓</button>
                <button onClick={() => setConfirmDelete(null)} style={btnDangerStyle}>✕</button>
              </>
            ) : (
              <button onClick={() => setConfirmDelete(c.id)} style={btnDangerStyle} title="Delete">✕</button>
            )}
          </>
        )}
      </div>
    )
  }

  return (
    <div>
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
        <input placeholder="Name" value={form.name} onChange={e => setForm(f => ({ ...f, name: e.target.value }))} style={inputStyle} required />
        <select value={form.type} onChange={e => setForm(f => ({ ...f, type: e.target.value }))} style={inputStyle}>
          <option value="variable">Variable</option>
          <option value="fixed">Fixed</option>
        </select>
        <input type="number" step="0.01" placeholder="Budget €/mo" value={form.monthly_estimate}
          onChange={e => setForm(f => ({ ...f, monthly_estimate: e.target.value }))} style={inputStyle} />
        <button type="submit" style={btnStyle}>+ Add</button>
      </form>

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Loading...</p> : (
        <>
          {[['Variable', variable], ['Fixed', fixed]].map(([label, cats]) => (
            <div key={label} style={{ marginBottom: 24 }}>
              <h3 style={{ color: 'var(--text-muted)', fontSize: 10, textTransform: 'uppercase', letterSpacing: 1.2, margin: '0 0 10px' }}>{label}</h3>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {cats.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 13 }}>No categories</p>}
                {cats.map(c => <CatRow key={c.id} c={c} />)}
              </div>
            </div>
          ))}

          {inactive.length > 0 && (
            <div style={{ marginTop: 8 }}>
              <button onClick={() => setShowInactive(s => !s)}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: 13, padding: 0 }}>
                {showInactive ? '▾' : '▸'} Inactive ({inactive.length})
              </button>
              {showInactive && (
                <div style={{ display: 'flex', flexDirection: 'column', marginTop: 10 }}>
                  {inactive.map(c => <CatRow key={c.id} c={c} />)}
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
