import request from './request'

// 代理池 API
export function addProxy(data) {
  return request.post('/proxy-pool/proxies', data)
}

export function batchAddProxies(data) {
  return request.post('/proxy-pool/proxies/batch', data)
}

export function getProxies(params) {
  return request.get('/proxy-pool/proxies', { params })
}

export function checkProxies(params) {
  return request.post('/proxy-pool/proxies/check', null, { params })
}

export function getAvailableProxy(params) {
  return request.get('/proxy-pool/proxies/available', { params })
}

export function getProxyStats(params) {
  return request.get('/proxy-pool/stats', { params })
}

export function deleteProxy(id) {
  return request.delete(`/proxy-pool/proxies/${id}`)
}

// API 管理 API
export function createApiConfig(data) {
  return request.post('/api-management/configs', data)
}

export function getApiConfigs(params) {
  return request.get('/api-management/configs', { params })
}

export function getApiConfig(id) {
  return request.get(`/api-management/configs/${id}`)
}

export function getApiStats(params) {
  return request.get('/api-management/stats', { params })
}

export function getApiTrend(params) {
  return request.get('/api-management/trend', { params })
}
