import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCategories, importPreview, importConfirm } from '../api'
import { useToast } from './Toast'

export default function ImportarModal({ onClose }) {
  const toast = useToast()
  const qc = useQueryClient()
  const fileRef = useRef()
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(false)

  const { data: categories = [] } = useQuery({ queryKey: ['categories'], queryFn: getCategories })

  const handleFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    try {
      const preview = await importPreview(file)
      setRows(preview.map(r => ({ ...r, include: true })))
    } catch {
      toast('Error processing file. Is it an ING XLS?', 'error')
    }
    setLoading(false)
  }

  const confirmMut = useMutation({
    mutationFn: () => {
      const toSave = rows.filter(r => r.include).map(({ date, description, amount, category_id }) => ({ date, description, amount, category_id }))
      return importConfirm(toSave)
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['expenses'] })
      qc.invalidateQueries({ queryKey: ['summary'] })
      qc.invalidateQueries({ queryKey: ['evolution'] })
      qc.invalidateQueries({ queryKey: ['months'] })
      toast(`${data.imported} expenses imported`)
      onClose()
    },
    onError: () => toast('Error importing', 'error'),
  })

  const included = rows ? rows.filter(r => r.include).length : 0
  const totalAmount = rows ? rows.filter(r => r.include).reduce((s, r) => s + r.amount, 0) : 0
  const allChecked = rows && rows.every(r => r.include)

  const toggleAll = (val) => setRows(rs => rs.map(r => ({ ...r, include: val })))
  const toggleRow = (i, val) => setRows(rs => rs.map((r, j) => j === i ? { ...r, include: val } : r))
  const setCat = (i, val) => setRows(rs => rs.map((r, j) => j === i ? { ...r, category_id: val ? parseInt(val) : null } : r))

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: '#1a1a1a', borderRadius: 12, padding: 24, width: '100%', maxWidth: 860, maxHeight: '90vh', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Import from ING</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>✕</button>
        </div>

        {!rows ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <p style={{ color: '#888', marginBottom: 20, fontSize: 14 }}>
              Export your transactions from ING Direct → My accounts → Movements → Export XLS
            </p>
            <input ref={fileRef} type="file" accept=".xls,.xlsx" onChange={handleFile} style={{ display: 'none' }} />
            <button onClick={() => fileRef.current.click()} disabled={loading}
              style={{ background: 'var(--accent)', border: 'none', color: 'var(--bg)', padding: '12px 28px', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}>
              {loading ? 'Processing...' : 'Select XLS file'}
            </button>
          </div>
        ) : (
          <>
            <div style={{ color: '#666', fontSize: 13 }}>
              <span style={{ color: '#aaa' }}>{included}</span> of {rows.length} rows —&nbsp;
              <span style={{ color: '#fff', fontWeight: 600 }}>{totalAmount.toFixed(2)}€</span>
            </div>

            <div style={{ overflowY: 'auto', flex: 1 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead style={{ position: 'sticky', top: 0, background: '#1a1a1a' }}>
                  <tr style={{ color: '#555', borderBottom: '1px solid #333' }}>
                    <th style={{ padding: '6px 8px', width: 32 }}>
                      <input type="checkbox" checked={allChecked} onChange={e => toggleAll(e.target.checked)} />
                    </th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Date</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Description</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>ING</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Category</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500 }}>Amount</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222', opacity: row.include ? 1 : 0.35 }}>
                      <td style={{ padding: '5px 8px' }}>
                        <input type="checkbox" checked={row.include} onChange={e => toggleRow(i, e.target.checked)} />
                      </td>
                      <td style={{ padding: '5px 8px', color: '#777', whiteSpace: 'nowrap' }}>{row.date?.slice(0, 10)}</td>
                      <td style={{ padding: '5px 8px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.description}>
                        {row.description}
                      </td>
                      <td style={{ padding: '5px 8px', color: '#555', fontSize: 11, whiteSpace: 'nowrap' }}>{row.ing_category}</td>
                      <td style={{ padding: '5px 8px' }}>
                        <select value={row.category_id || ''} onChange={e => setCat(i, e.target.value)}
                          style={{ background: '#111', border: '1px solid #2a2a2a', color: row.category_id ? '#ccc' : '#555', padding: '3px 6px', borderRadius: 4, fontSize: 12, maxWidth: 130 }}>
                          <option value="">No category</option>
                          {categories.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                      </td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{row.amount.toFixed(2)}€</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid #222' }}>
              <button onClick={() => setRows(null)}
                style={{ background: '#2a2a2a', border: '1px solid #444', color: '#aaa', padding: '9px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                Change file
              </button>
              <button onClick={onClose}
                style={{ background: 'transparent', border: '1px solid #333', color: '#888', padding: '9px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                Cancel
              </button>
              <button onClick={() => confirmMut.mutate()} disabled={included === 0 || confirmMut.isPending}
                style={{ background: included > 0 ? 'var(--accent)' : 'var(--surface2)', border: 'none', color: included > 0 ? 'var(--bg)' : '#aaa', padding: '9px 20px', borderRadius: 8, cursor: included > 0 ? 'pointer' : 'default', fontSize: 13 }}>
                {confirmMut.isPending ? 'Importing...' : `Import ${included} expenses`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
