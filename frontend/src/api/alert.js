import request from './request'

// ==================== 告警规则 ====================

export function getAlertRules(params = {}) {
  return request.get('/alerts/rules', { params })
}

export function createAlertRule(data) {
  return request.post('/alerts/rules', data)
}

export function updateAlertRule(ruleId, data) {
  return request.put(`/alerts/rules/${ruleId}`, data)
}

export function deleteAlertRule(ruleId) {
  return request.delete(`/alerts/rules/${ruleId}`)
}

// ==================== 告警记录 ====================

export function getAlertRecords(params = {}) {
  return request.get('/alerts/records', { params })
}

export function acknowledgeAlertRecord(recordId) {
  return request.post(`/alerts/records/${recordId}/acknowledge`)
}

// ==================== 通知通道 ====================

export function getAlertChannels() {
  return request.get('/alerts/channels')
}

export function createAlertChannel(data) {
  return request.post('/alerts/channels', data)
}

export function updateAlertChannel(channelId, data) {
  return request.put(`/alerts/channels/${channelId}`, data)
}

export function deleteAlertChannel(channelId) {
  return request.delete(`/alerts/channels/${channelId}`)
}
