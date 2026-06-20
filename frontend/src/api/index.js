import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 300_000,
})

export const fetchStocks = () => api.get('/stocks').then(r => r.data.stocks)
export const addStock = (symbol, name = null) => api.post('/stocks', { symbol, name }).then(r => r.data)
export const deleteStock = symbol => api.delete(`/stocks/${symbol}`).then(r => r.data)

export const createPrediction = (symbol, opts = {}) => api.post('/predictions', { symbol, ...opts }).then(r => r.data)
export const fetchPredictions = (symbol, limit = 50, offset = 0) =>
  api.get('/predictions', { params: { symbol, limit, offset } }).then(r => r.data)
export const fetchLatestPrediction = symbol =>
  api.get('/predictions/latest', { params: { symbol } }).then(r => r.data)
export const fetchPredictionDetail = id => api.get(`/predictions/${id}`).then(r => r.data)
export const deletePrediction = id => api.delete(`/predictions/${id}`).then(r => r.data)
