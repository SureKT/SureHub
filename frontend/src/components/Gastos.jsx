import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getExpenses, getCategories, createExpense, updateExpense, deleteExpense, getMonths } from '../api'
import { useToast } from './Toast'
import ImportarModal from './ImportarModal'

const formatDate = (dateStr) =>
  new Date(dateStr).toLocaleDateString('es-ES', { day: '2-digit', month: 'short' })

const SOURCE_STYLE = {
  telegram:  { bg: 'var(--green-bg)',  color: 'var(--green)',  label: 'tg' },
  import:    { bg: 'var(--orange-bg)', color: 'var(--orange)', label: 'imp' },
  recurring: { bg: 'var(--purple-bg)', color: 'var(--purple)', label: 'rec' },
}

function SourceBadge({ source }) {
  const s = SOURCE_STYLE[source] || SOURCE_STYLE.manual
  return (
    <span style={{ background: s.bg, color: s.color, padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 600, letterSpacing: 0.3 }}>
      {s.label}
    </span>
  )
}

function exportCSV(expenses, filename = 'expenses.csv') {
  const cols = ['id', 'date', 'description', 'category', 'amount', 'source']
  const rows = expenses.map(e => [
    e.id,
    new Date(e.date).toLocaleDateString('es-ES'),
    (e.description || '').replace(/"/g, '""'),
    (e.category?.name || '').replace(/"/g, '""'),
    e.amount.toFixed(2),
    e.source,
  ])
  const csv = [cols, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14 }
const filterInputStyle = { background: 'var(--surface2)', border: '1px solid var(--border-dim)', color: 'var(--text-dim)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', fontSize: 12 }
const btnStyle = { background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '8px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 500 }
const btnSecStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: 'var(--text-dim)', padding: '4px 8px', cursor: 'pointer', fontSize: 15, lineHeight: 1 }

function AddForm({ categories, onSuccess }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({ amount: '', description: '', category_id: '', date: '' })

  const mut = useMutation({
    mutationFn: createExpense,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      qc.invalidateQueries({ queryKey: ['evolution'] })
      qc.invalidateQueries({ queryKey: ['months'] })
      setForm({ amount: '', description: '', category_id: '', date: '' })
      toast('Expense added')
      onSuccess?.()
    },
    onError: () => toast('Error adding expense', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.amount) return
    mut.mutate({
      amount: parseFloat(form.amount),
      description: form.description || null,
      category_id: form.category_id ? parseInt(form.category_id) : null,
      date: form.date || null,
    })
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <input type="number" step="0.01" placeholder="Amount €" value={form.amount}
        onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
        style={{ ...inputStyle, width: 110 }} required />
      <input type="text" placeholder="Description" value={form.description}
        onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
        style={{ ...inputStyle, flex: 1, minWidth: 140 }} />
      <select value={form.category_id} onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))} style={inputStyle}>
        <option value="">No category</option>
        {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
      </select>
      <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
        style={{ ...inputStyle, colorScheme: 'dark' }} />
      <button type="submit" disabled={mut.isPending} style={btnStyle}>+ Add</button>
    </form>
  )
}

function EditRow({ expense, categories, onDone }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({
    amount: expense.amount,
    description: expense.description || '',
    category_id: expense.category?.id || '',
    date: expense.date ? expense.date.slice(0, 10) : '',
  })

  const mut = useMutation({
    mutationFn: (data) => updateExpense(expense.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      qc.invalidateQueries({ queryKey: ['evolution'] })
      toast('Expense updated')
      onDone()
    },
    onError: () => toast('Error updating', 'error'),
  })

  const save = () => mut.mutate({
    amount: parseFloat(form.amount),
    description: form.description || null,
    category_id: form.category_id ? parseInt(form.category_id) : null,
    date: form.date || null,
  })

  return (
    <tr style={{ background: 'var(--surface2)' }}>
      <td style={{ padding: '6px 8px' }}>
        <input type="date" value={form.date} onChange={e => setForm(f => ({ ...f, date: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, colorScheme: 'dark', width: 130 }} />
      </td>
      <td style={{ padding: '6px 8px' }}>
        <input type="text" value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, width: '100%' }} autoFocus />
      </td>
      <td style={{ padding: '6px 8px' }}>
        <select value={form.category_id} onChange={e => setForm(f => ({ ...f, category_id: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13 }}>
          <option value="">No category</option>
          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </td>
      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
        <input type="number" step="0.01" value={form.amount} onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, width: 80, textAlign: 'right' }} />
      </td>
      <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
        <button onClick={save} disabled={mut.isPending} style={{ ...btnStyle, padding: '4px 10px', fontSize: 13, color: 'var(--bg)' }}>✓</button>
        <button onClick={onDone} style={{ ...btnSecStyle, marginLeft: 4, padding: '4px 8px', fontSize: 13 }}>✕</button>
      </td>
    </tr>
  )
}

export default function Gastos() {
  const toast = useToast()
  const qc = useQueryClient()

  const [filters, setFilters] = useState({ month: '', category_id: '', search: '', from_date: '', to_date: '' })
  const [showImport, setShowImport] = useState(false)
  const [page, setPage] = useState(1)
  const [order, setOrder] = useState('date')
  const [asc, setAsc] = useState(false)
  const [editId, setEditId] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [exporting, setExporting] = useState(false)
  const PER_PAGE = 30

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: getCategories })
  const { data: months = [] } = useQuery({ queryKey: ['months'], queryFn: getMonths })

  const monthParams = filters.month ? { year: parseInt(filters.month.split('-')[0]), month: parseInt(filters.month.split('-')[1]) } : {}
  const rangeParams = !filters.month && (filters.from_date || filters.to_date)
    ? { from_date: filters.from_date || undefined, to_date: filters.to_date || undefined }
    : {}
  const queryParams = {
    ...monthParams,
    ...rangeParams,
    category_id: filters.category_id || undefined,
    search: filters.search || undefined,
    page,
    per_page: PER_PAGE,
    order,
    asc,
  }

  const { data, isLoading } = useQuery({
    queryKey: ['expenses', queryParams],
    queryFn: () => getExpenses(queryParams),
    placeholderData: (prev) => prev,
  })

  const expenses = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / PER_PAGE)

  const deleteMut = useMutation({
    mutationFn: deleteExpense,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['expenses', queryParams] })
      const prev = qc.getQueryData(['expenses', queryParams])
      qc.setQueryData(['expenses', queryParams], old => old
        ? { ...old, total: old.total - 1, items: old.items.filter(e => e.id !== id) }
        : old)
      setConfirmDelete(null)
      return { prev }
    },
    onError: (err, id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['expenses', queryParams], ctx.prev)
      toast('Error deleting', 'error')
    },
    onSuccess: () => toast('Expense deleted'),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      qc.invalidateQueries({ queryKey: ['evolution'] })
      qc.invalidateQueries({ queryKey: ['months'] })
    },
  })

  const setFilter = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
  }

  const toggleSort = (col) => {
    if (order === col) setAsc(a => !a)
    else { setOrder(col); setAsc(false) }
    setPage(1)
  }

  const SortIcon = ({ col }) => {
    if (order !== col) return <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>↕</span>
    return <span style={{ color: 'var(--accent)', marginLeft: 4 }}>{asc ? '↑' : '↓'}</span>
  }

  return (
    <div>
      <AddForm categories={categories} />

      {showImport && <ImportarModal onClose={() => setShowImport(false)} />}

      {/* Filters */}
      <div style={{ borderTop: '1px solid var(--border-dim)', paddingTop: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <button onClick={() => setShowImport(true)}
            style={{ ...btnSecStyle, fontSize: 12, padding: '5px 10px', marginRight: 4 }}>
            Import ING
          </button>
          <select value={filters.month} onChange={e => setFilter('month', e.target.value)} style={{ ...filterInputStyle, fontSize: 12 }}>
            <option value="">All months</option>
            {months.map(m => <option key={`${m.year}-${m.month}`} value={`${m.year}-${m.month}`}>{m.label}</option>)}
          </select>
          <select value={filters.category_id} onChange={e => setFilter('category_id', e.target.value)} style={{ ...filterInputStyle, fontSize: 12 }}>
            <option value="">All categories</option>
            {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input type="text" placeholder="Search..." value={filters.search}
            onChange={e => setFilter('search', e.target.value)}
            style={{ ...filterInputStyle, fontSize: 12, flex: 1, minWidth: 120 }} />
          <input type="date" value={filters.from_date}
            onChange={e => { setFilter('from_date', e.target.value); if (e.target.value) setFilter('month', '') }}
            style={{ ...filterInputStyle, fontSize: 12, colorScheme: 'dark' }} title="From" />
          <input type="date" value={filters.to_date}
            onChange={e => { setFilter('to_date', e.target.value); if (e.target.value) setFilter('month', '') }}
            style={{ ...filterInputStyle, fontSize: 12, colorScheme: 'dark' }} title="To" />
          {(filters.month || filters.category_id || filters.search || filters.from_date || filters.to_date) && (
            <button onClick={() => { setFilters({ month: '', category_id: '', search: '', from_date: '', to_date: '' }); setPage(1) }}
              style={{ ...btnSecStyle, fontSize: 12, padding: '5px 10px' }}>
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Count + export */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {total} expense{total !== 1 ? 's' : ''}
        </div>
        {total > 0 && (
          <button
            disabled={exporting}
            onClick={async () => {
              setExporting(true)
              try {
                const all = await getExpenses({ ...queryParams, page: 1, per_page: 5000 })
                const mon = filters.month || 'all'
                exportCSV(all.items, `expenses-${mon}.csv`)
              } finally { setExporting(false) }
            }}
            style={{ ...btnSecStyle, fontSize: 11, padding: '4px 10px' }}>
            {exporting ? '...' : 'Export CSV'}
          </button>
        )}
      </div>

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Loading...</p> : (
        <>
          <div className="table-wrap">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 540 }}>
            <thead>
              <tr style={{ color: 'var(--text-dim)', textAlign: 'left', borderBottom: '1px solid var(--border)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                <th style={th} onClick={() => toggleSort('date')} role="button">
                  Date<SortIcon col="date" />
                </th>
                <th style={th} onClick={() => toggleSort('description')} role="button">
                  Description<SortIcon col="description" />
                </th>
                <th style={th}>Category</th>
                <th style={{ ...th, textAlign: 'right' }} onClick={() => toggleSort('amount')} role="button">
                  Amount<SortIcon col="amount" />
                </th>
                <th style={{ ...th, width: 80 }} />
              </tr>
            </thead>
            <tbody>
              {expenses.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '24px', color: 'var(--text-dim)', textAlign: 'center' }}>No results</td></tr>
              )}
              {expenses.map(e => editId === e.id ? (
                <EditRow key={e.id} expense={e} categories={categories} onDone={() => setEditId(null)} />
              ) : (
                <tr key={e.id} style={{ borderBottom: '1px solid var(--border-dim)' }}
                  onMouseEnter={ev => ev.currentTarget.style.background = 'var(--surface2)'}
                  onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}>
                  <td style={{ ...td, color: 'var(--text-dim)', fontSize: 13 }}>{formatDate(e.date)}</td>
                  <td style={td}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {e.description || <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      {['telegram', 'import', 'recurring'].includes(e.source) && <SourceBadge source={e.source} />}
                    </span>
                  </td>
                  <td style={td}>
                    {e.category
                      ? <span style={{ background: 'var(--surface3)', color: 'var(--text-dim)', padding: '2px 8px', borderRadius: 10, fontSize: 12 }}>{e.category.name}</span>
                      : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>no category</span>}
                  </td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>{e.amount.toFixed(2)}€</td>
                  <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button onClick={() => setEditId(e.id)} style={btnDangerStyle} title="Edit">✎</button>
                    {confirmDelete === e.id ? (
                      <>
                        <button onClick={() => deleteMut.mutate(e.id)} style={{ ...btnDangerStyle, color: 'var(--red)' }} title="Confirm">✓</button>
                        <button onClick={() => setConfirmDelete(null)} style={btnDangerStyle} title="Cancel">✕</button>
                      </>
                    ) : (
                      <button onClick={() => setConfirmDelete(e.id)} style={btnDangerStyle} title="Delete">✕</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, marginTop: 20 }}>
              <button onClick={() => setPage(1)} disabled={page === 1} style={btnSecStyle}>«</button>
              <button onClick={() => setPage(p => p - 1)} disabled={page === 1} style={btnSecStyle}>‹</button>
              <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>{page} / {totalPages}</span>
              <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages} style={btnSecStyle}>›</button>
              <button onClick={() => setPage(totalPages)} disabled={page === totalPages} style={btnSecStyle}>»</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

const th = { padding: '8px 12px', fontWeight: 500, cursor: 'pointer', userSelect: 'none' }
const td = { padding: '10px 12px', color: 'var(--text)' }
