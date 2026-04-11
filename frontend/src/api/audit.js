import request from './request'

// 审计日志 API
export function getAuditLogs(params) {
  return request.get('/audit/logs', { params })
}

export function getAuditStats(params) {
  return request.get('/audit/stats')
}

export function getUserActivity(userId, params) {
  return request.get(`/audit/user/${userId}/activity/`, { params })
}
