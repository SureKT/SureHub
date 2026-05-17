import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getCategorias, importarPreview, importarConfirmar } from '../api'
import { useToast } from './Toast'

export default function ImportarModal({ onClose }) {
  const toast = useToast()
  const qc = useQueryClient()
  const fileRef = useRef()
  const [rows, setRows] = useState(null)
  const [loading, setLoading] = useState(false)

  const { data: categorias = [] } = useQuery({ queryKey: ['categorias'], queryFn: getCategorias })

  const handleFile = async (e) => {
    const file = e.target.files[0]
    if (!file) return
    setLoading(true)
    try {
      const preview = await importarPreview(file)
      setRows(preview.map(r => ({ ...r, incluir: true })))
    } catch {
      toast('Error al procesar archivo. ¿Es un XLS de ING?', 'error')
    }
    setLoading(false)
  }

  const confirmarMut = useMutation({
    mutationFn: () => {
      const toSave = rows.filter(r => r.incluir).map(({ fecha, descripcion, cantidad, categoria_id }) => ({ fecha, descripcion, cantidad, categoria_id }))
      return importarConfirmar(toSave)
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      qc.invalidateQueries({ queryKey: ['evolucion'] })
      qc.invalidateQueries({ queryKey: ['meses'] })
      toast(`${data.importados} gastos importados`)
      onClose()
    },
    onError: () => toast('Error al importar', 'error'),
  })

  const incluidos = rows ? rows.filter(r => r.incluir).length : 0
  const totalImporte = rows ? rows.filter(r => r.incluir).reduce((s, r) => s + r.cantidad, 0) : 0
  const allChecked = rows && rows.every(r => r.incluir)

  const toggleAll = (val) => setRows(rs => rs.map(r => ({ ...r, incluir: val })))
  const toggleRow = (i, val) => setRows(rs => rs.map((r, j) => j === i ? { ...r, incluir: val } : r))
  const setCat = (i, val) => setRows(rs => rs.map((r, j) => j === i ? { ...r, categoria_id: val ? parseInt(val) : null } : r))

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: '#1a1a1a', borderRadius: 12, padding: 24, width: '100%', maxWidth: 860, maxHeight: '90vh', display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2 style={{ margin: 0, fontSize: 17 }}>Importar desde ING</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: 20, lineHeight: 1 }}>✕</button>
        </div>

        {!rows ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <p style={{ color: '#888', marginBottom: 20, fontSize: 14 }}>
              Exporta tus movimientos desde ING Direct → Mis cuentas → Movimientos → Exportar XLS
            </p>
            <input ref={fileRef} type="file" accept=".xls,.xlsx" onChange={handleFile} style={{ display: 'none' }} />
            <button onClick={() => fileRef.current.click()} disabled={loading}
              style={{ background: '#3498db', border: 'none', color: '#fff', padding: '12px 28px', borderRadius: 8, cursor: 'pointer', fontSize: 14 }}>
              {loading ? 'Procesando...' : 'Seleccionar archivo XLS'}
            </button>
          </div>
        ) : (
          <>
            <div style={{ color: '#666', fontSize: 13 }}>
              <span style={{ color: '#aaa' }}>{incluidos}</span> de {rows.length} filas —&nbsp;
              <span style={{ color: '#fff', fontWeight: 600 }}>{totalImporte.toFixed(2)}€</span>
            </div>

            <div style={{ overflowY: 'auto', flex: 1 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead style={{ position: 'sticky', top: 0, background: '#1a1a1a' }}>
                  <tr style={{ color: '#555', borderBottom: '1px solid #333' }}>
                    <th style={{ padding: '6px 8px', width: 32 }}>
                      <input type="checkbox" checked={allChecked} onChange={e => toggleAll(e.target.checked)} />
                    </th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Fecha</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Descripción</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>ING</th>
                    <th style={{ padding: '6px 8px', textAlign: 'left', fontWeight: 500 }}>Categoría</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right', fontWeight: 500 }}>Importe</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #222', opacity: row.incluir ? 1 : 0.35 }}>
                      <td style={{ padding: '5px 8px' }}>
                        <input type="checkbox" checked={row.incluir} onChange={e => toggleRow(i, e.target.checked)} />
                      </td>
                      <td style={{ padding: '5px 8px', color: '#777', whiteSpace: 'nowrap' }}>{row.fecha?.slice(0, 10)}</td>
                      <td style={{ padding: '5px 8px', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={row.descripcion}>
                        {row.descripcion}
                      </td>
                      <td style={{ padding: '5px 8px', color: '#555', fontSize: 11, whiteSpace: 'nowrap' }}>{row.ing_categoria}</td>
                      <td style={{ padding: '5px 8px' }}>
                        <select value={row.categoria_id || ''} onChange={e => setCat(i, e.target.value)}
                          style={{ background: '#111', border: '1px solid #2a2a2a', color: row.categoria_id ? '#ccc' : '#555', padding: '3px 6px', borderRadius: 4, fontSize: 12, maxWidth: 130 }}>
                          <option value="">Sin categoría</option>
                          {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
                        </select>
                      </td>
                      <td style={{ padding: '5px 8px', textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{row.cantidad.toFixed(2)}€</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', paddingTop: 8, borderTop: '1px solid #222' }}>
              <button onClick={() => setRows(null)}
                style={{ background: '#2a2a2a', border: '1px solid #444', color: '#aaa', padding: '9px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                Cambiar archivo
              </button>
              <button onClick={onClose}
                style={{ background: 'transparent', border: '1px solid #333', color: '#888', padding: '9px 18px', borderRadius: 8, cursor: 'pointer', fontSize: 13 }}>
                Cancelar
              </button>
              <button onClick={() => confirmarMut.mutate()} disabled={incluidos === 0 || confirmarMut.isPending}
                style={{ background: incluidos > 0 ? '#3498db' : '#1a2a35', border: 'none', color: '#fff', padding: '9px 20px', borderRadius: 8, cursor: incluidos > 0 ? 'pointer' : 'default', fontSize: 13 }}>
                {confirmarMut.isPending ? 'Importando...' : `Importar ${incluidos} gastos`}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
