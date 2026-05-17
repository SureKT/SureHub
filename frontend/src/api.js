import axios from 'axios'

const api = axios.create({ baseURL: '/api/finanzas' })

export const getCategorias = () => api.get('/categorias').then(r => r.data)
export const createCategoria = (data) => api.post('/categorias', data).then(r => r.data)
export const updateCategoria = (id, data) => api.patch(`/categorias/${id}`, data).then(r => r.data)
export const deleteCategoria = (id) => api.delete(`/categorias/${id}`)

export const getGastos = (n = 50) => api.get('/gastos', { params: { n } }).then(r => r.data)
export const createGasto = (data) => api.post('/gastos', data).then(r => r.data)

export const getResumen = () => api.get('/resumen').then(r => r.data)
