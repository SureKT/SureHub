import axios from 'axios'

const api = axios.create({ baseURL: '/api/finance' })
const memApi = axios.create({ baseURL: '/api/memory' })

export const getCategories = (params = {}) => api.get('/categories', { params }).then(r => r.data)
export const createCategory = (data) => api.post('/categories', data).then(r => r.data)
export const updateCategory = (id, data) => api.patch(`/categories/${id}`, data).then(r => r.data)
export const deleteCategory = (id) => api.delete(`/categories/${id}`)

export const getExpenses = (params = {}) => {
  // per_page cap raised on backend to 5000 for exports
  return api.get('/expenses', { params }).then(r => r.data)
}
export const createExpense = (data) => api.post('/expenses', data).then(r => r.data)
export const updateExpense = (id, data) => api.patch(`/expenses/${id}`, data).then(r => r.data)
export const deleteExpense = (id) => api.delete(`/expenses/${id}`)

export const getSummary = (params = {}) => api.get('/summary', { params }).then(r => r.data)
export const getEvolution = (months = 12) => api.get('/evolution', { params: { months } }).then(r => r.data)
export const getMonths = () => api.get('/months').then(r => r.data)

export const importPreview = (file) => {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/import/preview', fd).then(r => r.data)
}
export const importConfirm = (rows) => api.post('/import/confirm', rows).then(r => r.data)

export const getMemories = () => memApi.get('').then(r => r.data)
export const createMemory = (fact) => memApi.post('', { fact }).then(r => r.data)
export const updateMemory = (id, fact) => memApi.patch(`/${id}`, { fact }).then(r => r.data)
export const deleteMemory = (id) => memApi.delete(`/${id}`)

const spotifyApi = axios.create({ baseURL: '/api/spotify' })
export const spotifyStatus = (userId) => spotifyApi.get(`/status/${userId}`).then(r => r.data)
export const spotifyAnalyze = (userId) => spotifyApi.post(`/analyze/${userId}`).then(r => r.data)
export const spotifyAuthUrl = (userId) => `/api/spotify/auth?telegram_user_id=${userId}`

const recApi = axios.create({ baseURL: '/api/finance/recurring' })
export const getRecurring = (params = {}) => recApi.get('', { params }).then(r => r.data)
export const createRecurring = (data) => recApi.post('', data).then(r => r.data)
export const updateRecurring = (id, data) => recApi.patch(`/${id}`, data).then(r => r.data)
export const deleteRecurring = (id) => recApi.delete(`/${id}`)
export const generateRecurring = (params = {}) => recApi.post('/generate', null, { params }).then(r => r.data)
