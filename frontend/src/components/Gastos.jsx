import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getGastos, getCategorias, createGasto, updateGasto, deleteGasto, getMeses } from '../api'
import { useToast } from './Toast'
import ImportarModal from './ImportarModal'

const FUENTE_STYLE = {
  telegram:   { bg: 'var(--green-bg)',  color: 'var(--green)',  label: 'tg' },
  importacion:{ bg: 'var(--orange-bg)', color: 'var(--orange)', label: 'imp' },
  recurrente: { bg: 'var(--purple-bg)', color: 'var(--purple)', label: 'rec' },
}

function FuenteBadge({ fuente }) {
  const s = FUENTE_STYLE[fuente] || FUENTE_STYLE.manual
  return (
    <span style={{ background: s.bg, color: s.color, padding: '1px 5px', borderRadius: 4, fontSize: 10, fontWeight: 600, letterSpacing: 0.3 }}>
      {s.label}
    </span>
  )
}

function exportCSV(gastos, filename = 'gastos.csv') {
  const cols = ['id', 'fecha', 'descripcion', 'categoria', 'cantidad', 'fuente']
  const rows = gastos.map(g => [
    g.id,
    new Date(g.fecha).toLocaleDateString('es-ES'),
    (g.descripcion || '').replace(/"/g, '""'),
    (g.categoria?.nombre || '').replace(/"/g, '""'),
    g.cantidad.toFixed(2),
    g.fuente,
  ])
  const csv = [cols, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n')
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename; a.click()
  URL.revokeObjectURL(url)
}

const inputStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text)', padding: '8px 12px', borderRadius: 'var(--radius-sm)', fontSize: 14 }
const btnStyle = { background: 'var(--accent)', border: 'none', color: '#fff', padding: '8px 14px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13, fontWeight: 600 }
const btnSecStyle = { background: 'var(--surface2)', border: '1px solid var(--border)', color: 'var(--text-dim)', padding: '6px 10px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: 13 }
const btnDangerStyle = { background: 'transparent', border: 'none', color: 'var(--text-muted)', padding: '4px 8px', cursor: 'pointer', fontSize: 15, lineHeight: 1 }

function AddForm({ categorias, onSuccess }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({ cantidad: '', descripcion: '', categoria_id: '', fecha: '' })

  const mut = useMutation({
    mutationFn: createGasto,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      qc.invalidateQueries({ queryKey: ['evolucion'] })
      qc.invalidateQueries({ queryKey: ['meses'] })
      setForm({ cantidad: '', descripcion: '', categoria_id: '', fecha: '' })
      toast('Gasto añadido')
      onSuccess?.()
    },
    onError: () => toast('Error al añadir gasto', 'error'),
  })

  const submit = (e) => {
    e.preventDefault()
    if (!form.cantidad) return
    mut.mutate({
      cantidad: parseFloat(form.cantidad),
      descripcion: form.descripcion || null,
      categoria_id: form.categoria_id ? parseInt(form.categoria_id) : null,
      fecha: form.fecha || null,
    })
  }

  return (
    <form onSubmit={submit} style={{ display: 'flex', gap: 8, marginBottom: 24, flexWrap: 'wrap', alignItems: 'flex-end' }}>
      <input type="number" step="0.01" placeholder="Cantidad €" value={form.cantidad}
        onChange={e => setForm(f => ({ ...f, cantidad: e.target.value }))}
        style={{ ...inputStyle, width: 110 }} required />
      <input type="text" placeholder="Descripción" value={form.descripcion}
        onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
        style={{ ...inputStyle, flex: 1, minWidth: 140 }} />
      <select value={form.categoria_id} onChange={e => setForm(f => ({ ...f, categoria_id: e.target.value }))} style={inputStyle}>
        <option value="">Sin categoría</option>
        {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
      </select>
      <input type="date" value={form.fecha} onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))}
        style={{ ...inputStyle, colorScheme: 'dark' }} />
      <button type="submit" disabled={mut.isPending} style={btnStyle}>+ Añadir</button>
    </form>
  )
}

function EditRow({ gasto, categorias, onDone }) {
  const toast = useToast()
  const qc = useQueryClient()
  const [form, setForm] = useState({
    cantidad: gasto.cantidad,
    descripcion: gasto.descripcion || '',
    categoria_id: gasto.categoria?.id || '',
    fecha: gasto.fecha ? gasto.fecha.slice(0, 10) : '',
  })

  const mut = useMutation({
    mutationFn: (data) => updateGasto(gasto.id, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      qc.invalidateQueries({ queryKey: ['evolucion'] })
      toast('Gasto actualizado')
      onDone()
    },
    onError: () => toast('Error al actualizar', 'error'),
  })

  const save = () => mut.mutate({
    cantidad: parseFloat(form.cantidad),
    descripcion: form.descripcion || null,
    categoria_id: form.categoria_id ? parseInt(form.categoria_id) : null,
    fecha: form.fecha || null,
  })

  return (
    <tr style={{ background: 'var(--surface2)' }}>
      <td style={{ padding: '6px 8px' }}>
        <input type="date" value={form.fecha} onChange={e => setForm(f => ({ ...f, fecha: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, colorScheme: 'dark', width: 130 }} />
      </td>
      <td style={{ padding: '6px 8px' }}>
        <input type="text" value={form.descripcion} onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, width: '100%' }} autoFocus />
      </td>
      <td style={{ padding: '6px 8px' }}>
        <select value={form.categoria_id} onChange={e => setForm(f => ({ ...f, categoria_id: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13 }}>
          <option value="">Sin categoría</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
      </td>
      <td style={{ padding: '6px 8px', textAlign: 'right' }}>
        <input type="number" step="0.01" value={form.cantidad} onChange={e => setForm(f => ({ ...f, cantidad: e.target.value }))}
          style={{ ...inputStyle, padding: '4px 8px', fontSize: 13, width: 80, textAlign: 'right' }} />
      </td>
      <td style={{ padding: '6px 8px', whiteSpace: 'nowrap' }}>
        <button onClick={save} disabled={mut.isPending} style={{ ...btnStyle, padding: '4px 10px', fontSize: 13 }}>✓</button>
        <button onClick={onDone} style={{ ...btnSecStyle, marginLeft: 4, padding: '4px 8px', fontSize: 13 }}>✕</button>
      </td>
    </tr>
  )
}

export default function Gastos() {
  const toast = useToast()
  const qc = useQueryClient()

  const [filters, setFilters] = useState({ mes: '', categoria_id: '', busqueda: '', desde: '', hasta: '' })
  const [showImportar, setShowImportar] = useState(false)
  const [page, setPage] = useState(1)
  const [orden, setOrden] = useState('fecha')
  const [asc, setAsc] = useState(false)
  const [editId, setEditId] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [exporting, setExporting] = useState(false)
  const PER_PAGE = 30

  const { data: categorias = [] } = useQuery({ queryKey: ['categorias'], queryFn: getCategorias })
  const { data: meses = [] } = useQuery({ queryKey: ['meses'], queryFn: getMeses })

  const mesParams = filters.mes ? { anio: parseInt(filters.mes.split('-')[0]), mes: parseInt(filters.mes.split('-')[1]) } : {}
  const rangoParams = !filters.mes && (filters.desde || filters.hasta)
    ? { desde: filters.desde || undefined, hasta: filters.hasta || undefined }
    : {}
  const queryParams = {
    ...mesParams,
    ...rangoParams,
    categoria_id: filters.categoria_id || undefined,
    busqueda: filters.busqueda || undefined,
    page,
    per_page: PER_PAGE,
    orden,
    asc,
  }

  const { data, isLoading } = useQuery({
    queryKey: ['gastos', queryParams],
    queryFn: () => getGastos(queryParams),
    placeholderData: (prev) => prev,
  })

  const gastos = data?.items || []
  const total = data?.total || 0
  const totalPages = Math.ceil(total / PER_PAGE)

  const deleteMut = useMutation({
    mutationFn: deleteGasto,
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: ['gastos', queryParams] })
      const prev = qc.getQueryData(['gastos', queryParams])
      qc.setQueryData(['gastos', queryParams], old => old
        ? { ...old, total: old.total - 1, items: old.items.filter(g => g.id !== id) }
        : old)
      setConfirmDelete(null)
      return { prev }
    },
    onError: (err, id, ctx) => {
      if (ctx?.prev) qc.setQueryData(['gastos', queryParams], ctx.prev)
      toast('Error al eliminar', 'error')
    },
    onSuccess: () => toast('Gasto eliminado'),
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ['gastos'] })
      qc.invalidateQueries({ queryKey: ['resumen'] })
      qc.invalidateQueries({ queryKey: ['evolucion'] })
      qc.invalidateQueries({ queryKey: ['meses'] })
    },
  })

  const setFilter = (key, val) => {
    setFilters(f => ({ ...f, [key]: val }))
    setPage(1)
  }

  const toggleSort = (col) => {
    if (orden === col) setAsc(a => !a)
    else { setOrden(col); setAsc(false) }
    setPage(1)
  }

  const SortIcon = ({ col }) => {
    if (orden !== col) return <span style={{ color: 'var(--text-muted)', marginLeft: 4 }}>↕</span>
    return <span style={{ color: 'var(--accent)', marginLeft: 4 }}>{asc ? '↑' : '↓'}</span>
  }

  return (
    <div>
      <AddForm categorias={categorias} />

      {showImportar && <ImportarModal onClose={() => setShowImportar(false)} />}

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <button onClick={() => setShowImportar(true)}
          style={{ ...btnSecStyle, fontSize: 12, padding: '6px 12px', marginRight: 4 }}>
          Importar ING
        </button>
        <select value={filters.mes} onChange={e => setFilter('mes', e.target.value)} style={{ ...inputStyle, fontSize: 13 }}>
          <option value="">Todos los meses</option>
          {meses.map(m => <option key={`${m.anio}-${m.mes}`} value={`${m.anio}-${m.mes}`}>{m.label}</option>)}
        </select>
        <select value={filters.categoria_id} onChange={e => setFilter('categoria_id', e.target.value)} style={{ ...inputStyle, fontSize: 13 }}>
          <option value="">Todas las categorías</option>
          {categorias.map(c => <option key={c.id} value={c.id}>{c.nombre}</option>)}
        </select>
        <input type="text" placeholder="Buscar descripción..." value={filters.busqueda}
          onChange={e => setFilter('busqueda', e.target.value)}
          style={{ ...inputStyle, fontSize: 13, flex: 1, minWidth: 130 }} />
        <input type="date" value={filters.desde}
          onChange={e => { setFilter('desde', e.target.value); if (e.target.value) setFilter('mes', '') }}
          style={{ ...inputStyle, fontSize: 12, colorScheme: 'dark' }} title="Desde" />
        <input type="date" value={filters.hasta}
          onChange={e => { setFilter('hasta', e.target.value); if (e.target.value) setFilter('mes', '') }}
          style={{ ...inputStyle, fontSize: 12, colorScheme: 'dark' }} title="Hasta" />
        {(filters.mes || filters.categoria_id || filters.busqueda || filters.desde || filters.hasta) && (
          <button onClick={() => { setFilters({ mes: '', categoria_id: '', busqueda: '', desde: '', hasta: '' }); setPage(1) }}
            style={{ ...btnSecStyle, fontSize: 12, padding: '6px 12px' }}>
            Limpiar
          </button>
        )}
      </div>

      {/* Count + export */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
        <div style={{ color: 'var(--text-dim)', fontSize: 12 }}>
          {total} gasto{total !== 1 ? 's' : ''}
        </div>
        {total > 0 && (
          <button
            disabled={exporting}
            onClick={async () => {
              setExporting(true)
              try {
                const all = await getGastos({ ...queryParams, page: 1, per_page: 5000 })
                const mes = filters.mes || 'todos'
                exportCSV(all.items, `gastos-${mes}.csv`)
              } finally { setExporting(false) }
            }}
            style={{ ...btnSecStyle, fontSize: 11, padding: '4px 10px' }}>
            {exporting ? '...' : 'Exportar CSV'}
          </button>
        )}
      </div>

      {isLoading ? <p style={{ color: 'var(--text-dim)' }}>Cargando...</p> : (
        <>
          <div className="table-wrap">
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14, minWidth: 540 }}>
            <thead>
              <tr style={{ color: 'var(--text-dim)', textAlign: 'left', borderBottom: '1px solid var(--border)', fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                <th style={th} onClick={() => toggleSort('fecha')} role="button">
                  Fecha<SortIcon col="fecha" />
                </th>
                <th style={th} onClick={() => toggleSort('descripcion')} role="button">
                  Descripción<SortIcon col="descripcion" />
                </th>
                <th style={th}>Categoría</th>
                <th style={{ ...th, textAlign: 'right' }} onClick={() => toggleSort('cantidad')} role="button">
                  Cantidad<SortIcon col="cantidad" />
                </th>
                <th style={{ ...th, width: 80 }} />
              </tr>
            </thead>
            <tbody>
              {gastos.length === 0 && (
                <tr><td colSpan={5} style={{ padding: '24px', color: 'var(--text-dim)', textAlign: 'center' }}>Sin resultados</td></tr>
              )}
              {gastos.map(g => editId === g.id ? (
                <EditRow key={g.id} gasto={g} categorias={categorias} onDone={() => setEditId(null)} />
              ) : (
                <tr key={g.id} style={{ borderBottom: '1px solid var(--border-dim)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--surface2)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                  <td style={{ ...td, color: 'var(--text-dim)', fontSize: 13 }}>{new Date(g.fecha).toLocaleDateString('es-ES')}</td>
                  <td style={td}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      {g.descripcion || <span style={{ color: 'var(--text-muted)' }}>—</span>}
                      {['telegram', 'importacion', 'recurrente'].includes(g.fuente) && <FuenteBadge fuente={g.fuente} />}
                    </span>
                  </td>
                  <td style={td}>
                    {g.categoria
                      ? <span style={{ background: 'var(--accent-bg)', color: 'var(--accent)', padding: '2px 8px', borderRadius: 10, fontSize: 12 }}>{g.categoria.nombre}</span>
                      : <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>sin categoría</span>}
                  </td>
                  <td style={{ ...td, textAlign: 'right', fontWeight: 600, fontVariantNumeric: 'tabular-nums', color: 'var(--text)' }}>{g.cantidad.toFixed(2)}€</td>
                  <td style={{ ...td, textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button onClick={() => setEditId(g.id)} style={btnDangerStyle} title="Editar">✎</button>
                    {confirmDelete === g.id ? (
                      <>
                        <button onClick={() => deleteMut.mutate(g.id)} style={{ ...btnDangerStyle, color: '#e74c3c' }} title="Confirmar">✓</button>
                        <button onClick={() => setConfirmDelete(null)} style={btnDangerStyle} title="Cancelar">✕</button>
                      </>
                    ) : (
                      <button onClick={() => setConfirmDelete(g.id)} style={btnDangerStyle} title="Eliminar">✕</button>
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
              <span style={{ color: '#666', fontSize: 13 }}>{page} / {totalPages}</span>
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
