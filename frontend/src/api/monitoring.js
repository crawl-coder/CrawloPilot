import request from './request'

// 监控数据 API
export function getSystemMetrics() {
  return request.get('/monitoring/system')
}

export function getSpiderMetrics(params) {
  return request.get('/monitoring/spiders', { params })
}

export function getScheduleMetrics() {
  return request.get('/monitoring/schedules')
}

export function getDeploymentMetrics() {
  return request.get('/monitoring/deployments')
}

export function getNodeMetrics() {
  return request.get('/monitoring/nodes')
}

export function getTaskQueueMetrics() {
  return request.get('/monitoring/tasks/queue')
}

export function getHealthStatus() {
  return request.get('/monitoring/health')
}

export function getDashboardData() {
  return request.get('/monitoring/dashboard')
}

// 告警管理 API
export function getAlertRules(params) {
  return request.get('/alerts/rules', { params })
}

export function createAlertRule(data) {
  return request.post('/alerts/rules', data)
}

export function updateAlertRule(id, data) {
  return request.put(`/alerts/rules/${id}`, data)
}

export function deleteAlertRule(id) {
  return request.delete(`/alerts/rules/${id}`)
}

export function getActiveAlerts(params) {
  return request.get('/alerts/active', { params })
}

export function getAlertHistory(params) {
  return request.get('/alerts/history', { params })
}

export function getAlertStats() {
  return request.get('/alerts/stats')
}

export function testNotification(channel) {
  return request.post('/alerts/test-notification', null, { params: { channel } })
}

export function resolveAlert(alertId) {
  return request.post(`/alerts/alerts/${alertId}/resolve`)
}
