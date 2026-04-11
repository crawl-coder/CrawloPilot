import request from './request'

// 数据质量检测 API
export function getQualityChecks(params) {
  return request.get('/data-quality/checks', { params })
}

export function createQualityCheck(data) {
  return request.post('/data-quality/checks', data)
}

export function getQualityStats(params) {
  return request.get('/data-quality/checks/stats', { params })
}

// 数据质量规则 API
export function getQualityRules(params) {
  return request.get('/data-quality/rules', { params })
}

export function createQualityRule(data) {
  return request.post('/data-quality/rules', data)
}

export function updateQualityRule(id, data) {
  return request.put(`/data-quality/rules/${id}`, data)
}

export function deleteQualityRule(id) {
  return request.delete(`/data-quality/rules/${id}`)
}

// 数据统计 API
export function getProjectStatistics(params) {
  return request.get('/data-quality/statistics/project', { params })
}

export function getSpiderStatistics(params) {
  return request.get('/data-quality/statistics/spider', { params })
}

export function getSummaryStatistics(params) {
  return request.get('/data-quality/statistics/summary', { params })
}

export function recordStatistics(params) {
  return request.post('/data-quality/statistics/record', null, { params })
}
