import axios from 'axios'

const api = axios.create({ baseURL: '/api/finanzas' })
const memApi = axios.create({ baseURL: '/api/memoria' })

export const getCategorias = (params = {}) => api.get('/categorias', { params }).then(r => r.data)
export const createCategoria = (data) => api.post('/categorias', data).then(r => r.data)
export const updateCategoria = (id, data) => api.patch(`/categorias/${id}`, data).then(r => r.data)
export const deleteCategoria = (id) => api.delete(`/categorias/${id}`)

export const getGastos = (params = {}) => {
  const p = { ...params }
  // per_page cap raised on backend to 5000 for exports
  return api.get('/gastos', { params: p }).then(r => r.data)
}
export const createGasto = (data) => api.post('/gastos', data).then(r => r.data)
export const updateGasto = (id, data) => api.patch(`/gastos/${id}`, data).then(r => r.data)
export const deleteGasto = (id) => api.delete(`/gastos/${id}`)

export const getResumen = (params = {}) => api.get('/resumen', { params }).then(r => r.data)
export const getEvolucion = (meses = 12) => api.get('/evolucion', { params: { meses } }).then(r => r.data)
export const getMeses = () => api.get('/meses').then(r => r.data)

export const importarPreview = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/importar/preview', fd).then(r => r.data)
}
export const importarConfirmar = (rows) => api.post('/importar/confirmar', rows).then(r => r.data)

export const getMemorias = () => memApi.get('').then(r => r.data)
export const createMemoria = (hecho) => memApi.post('', { hecho }).then(r => r.data)
export const deleteMemoria = (id) => memApi.delete(`/${id}`)

const recApi = axios.create({ baseURL: '/api/finanzas/recurrentes' })
export const getRecurrentes = (params = {}) => recApi.get('', { params }).then(r => r.data)
export const createRecurrente = (data) => recApi.post('', data).then(r => r.data)
export const updateRecurrente = (id, data) => recApi.patch(`/${id}`, data).then(r => r.data)
export const deleteRecurrente = (id) => recApi.delete(`/${id}`)
export const generarRecurrentes = (params = {}) => recApi.post('/generar', null, { params }).then(r => r.data)
