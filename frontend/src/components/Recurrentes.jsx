import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getRecurring, createRecurring, updateRecurring, deleteRecurring, generateRecurring, getCategories } from '../api'
import { useToast } from './Toast'

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14 }
const btnStyle = { background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '8px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
const btnSecStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: 'var(--text-dim)', padding: '4px 8px', cursor: 'pointer', fontSize: 15 }

export default function Recurrentes() {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({ name: '', amount: '', category_id: '', day: '1' })
  const [editId, setEditId] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [confirmDelete, setConfirmDelete] = useState(null)

  const { data: recurring = [], isLoading } = useQuery({
    queryKey: ['recurring'],
    queryFn: () => getRecurring(),
    refetchInterval: 60000,
  })
  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: getCategories })

  const pending = recurring.filter(r => r.active && !r.generated_this_month)
  const monthlyTotal = recurring.filter(r => r.active).reduce((s, r) => s + r.amount, 0)

  const createMut = useMutation({
    mutationFn: createRecurring,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurring'] })
      setForm({ name: '', amount: '', category_id: '', day: '1' })
      toast('Recurring expense added')
    },
    onError: (e) => toast(e?.response?.data?.detail || 'Error creating', 'error'),
  })

  const updateMut = useMutation({
    mutationFn: ({ id, data }) => updateRecurring(id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurring'] })
      setEditId(null)
      toast('Updated')
    },
    onError: () => toast('Error updating', 'error'),
  })

  const deleteMut = useMutation({
    mutationFn: deleteRecurring,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['recurring'] })
      setConfirmDelete(null)
      toast('Deleted')
    },
    onError: () => toast('Error deleting', 'error'),
  })

  const generateMut = useMutation({
    mutationFn: generateRecurring,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['recurring'] })
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      if (data.total === 0) toast('All already generated this month')
      else toast(`${data.total} expense${data.total > 1 ? 's' : ''} generated`)
    },
    onError: () => toast('Error generating', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.name || !form.amount) return
    createMut.mutate({
      name: form.name,
      amount: parseFloat(form.amount),
      category_id: form.category_id ? parseInt(form.category_id) : null,
      day: parseInt(form.day) || 1,
    })
  }

  const saveEdit = (id) => updateMut.mutate({ id, data: {
    name: editForm.name,
    amount: parseFloat(editForm.amount),
    category_id: editForm.category_id ? parseInt(editForm.category_id) : null,
    day: parseInt(editForm.day) || 1,
  }})

  const activeList = recurring.filter(r => r.active)
  const inactiveList = recurring.filter(r => !r.active)

  return (
    <div>
      {/* Add form */}
      <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 28, flexWrap: 'wrap' }}>
        <input placeholder="Name (e.g. Netflix)" value={form.name}
          onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
          style={{ ...inputStyle, flex: 2, minWidth: 130 }} required />
        <input type="number" step="0.01" placeholder="Amount €" value={form.amount}
          onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
          style={{ ...inputStyle, width: 110 }} required />
        <select value={form.category_id} onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))} style={inputStyle}>
          <option value="">No category</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ color: 'var(--text-dim)', fontSize: 13 }}>Day</span>
          <input type="number" min="1" max="28" value={form.day}
            onChange={e => setForm(f => ({ ...f, day: e.target.value }))}
            style={{ ...inputStyle, width: 60, textAlign: 'center' }} />
        </div>
        <button type="submit" style={btnStyle}>+ Add</button>
      </form>

      {/* Header stats + generate button */}
      {activeList.length > 0 && (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20, flexWrap: 'wrap', gap: 10 }}>
          <div style={{ display: 'flex', gap: 20 }}>
            <div>
              <div style={{ color: 'var(--text-dim)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Monthly total</div>
              <div style={{ fontSize: 20, fontWeight: 700, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>{monthlyTotal.toFixed(2)}€</div>
            </div>
            {pending.length > 0 && (
              <div>
                <div style={{ color: 'var(--text-dim)', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.8 }}>Pending</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--orange)' }}>{pending.length}</div>
              </div>
            )}
          </div>
          <button
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending || pending.length === 0}
            style={{
              ...btnStyle,
              background: pending.length > 0 ? 'var(--accent)' : 'var(--surface2)',
              opacity: pending.length === 0 ? 0.5 : 1,
            }}>
            {generateMut.isPending ? 'Generating...' : pending.length > 0
              ? `Generate ${pending.length} this month`
              : 'All generated'}
          </button>
        </div>
      )}

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Loading...</p> : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            {activeList.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: 14 }}>No recurring expenses. Add subscriptions, rent, etc.</p>}
            {activeList.map(r => (
              <div key={r.id}
                style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0', borderBottom: '1px solid var(--border-dim)', flexWrap: 'wrap' }}
                onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
                onMouseLeave={e => e.currentTarget.style.opacity = '1'}
              >
                {editId === r.id ? (
                  <>
                    <input value={editForm.name} onChange={e => setEditForm(f => ({ ...f, name: e.target.value }))}
                      style={{ ...inputStyle, flex: 2, minWidth: 100 }} autoFocus />
                    <input type="number" step="0.01" value={editForm.amount} onChange={e => setEditForm(f => ({ ...f, amount: e.target.value }))}
                      style={{ ...inputStyle, width: 90 }} />
                    <select value={editForm.category_id || ''} onChange={e => setEditForm(f => ({ ...f, category_id: e.target.value }))} style={{ ...inputStyle, fontSize: 13 }}>
                      <option value="">No category</option>
                      {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                    <input type="number" min="1" max="28" value={editForm.day} onChange={e => setEditForm(f => ({ ...f, day: e.target.value }))}
                      style={{ ...inputStyle, width: 60, textAlign: 'center' }} />
                    <button onClick={() => saveEdit(r.id)} style={btnStyle}>✓</button>
                    <button onClick={() => setEditId(null)} style={btnSecStyle}>✕</button>
                  </>
                ) : (
                  <>
                    <span style={{ flex: 1, fontSize: 14, minWidth: 100 }}>{r.name}</span>
                    {r.category_name && (
                      <span style={{ background: 'var(--surface3)', color: 'var(--text-dim)', padding: '2px 8px', borderRadius: 10, fontSize: 11 }}>
                        {r.category_name}
                      </span>
                    )}
                    <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>day {r.day}</span>
                    <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text)', minWidth: 70, textAlign: 'right' }}>
                      {r.amount.toFixed(2)}€
                    </span>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 10, fontWeight: 600,
                      background: r.generated_this_month ? 'var(--green-bg)' : 'var(--orange-bg)',
                      color: r.generated_this_month ? 'var(--green)' : 'var(--orange)',
                    }}>
                      {r.generated_this_month ? 'generated' : 'pending'}
                    </span>
                    <button onClick={() => { setEditId(r.id); setEditForm({ name: r.name, amount: r.amount, category_id: r.category_id, day: r.day }) }}
                      style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 15, padding: '4px 8px', lineHeight: 1 }}
                      title="Edit">✎</button>
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

          {inactiveList.length > 0 && (
            <div style={{ marginTop: 16, color: 'var(--text-muted)', fontSize: 13 }}>
              {inactiveList.length} inactive
            </div>
          )}
        </>
      )}
    </div>
  )
}
