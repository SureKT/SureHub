import axios from 'axios'

const api = axios.create({ baseURL: '/api/finanzas' })

export const getCategorias = (params = {}) => api.get('/categorias', { params }).then(r => r.data)
export const createCategoria = (data) => api.post('/categorias', data).then(r => r.data)
export const updateCategoria = (id, data) => api.patch(`/categorias/${id}`, data).then(r => r.data)
export const deleteCategoria = (id) => api.delete(`/categorias/${id}`)

export const getGastos = (params = {}) => api.get('/gastos', { params }).then(r => r.data)
export const createGasto = (data) => api.post('/gastos', data).then(r => r.data)
export const updateGasto = (id, data) => api.patch(`/gastos/${id}`, data).then(r => r.data)
export const deleteGasto = (id) => api.delete(`/gastos/${id}`)

export const getResumen = (params = {}) => api.get('/resumen', { params }).then(r => r.data)
export const getEvolucion = (meses = 12) => api.get('/evolucion', { params: { meses } }).then(r => r.data)
export const getMeses = () => api.get('/meses').then(r => r.data)
