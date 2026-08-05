import request from './request'

// 监控数据 API（v1 仅保留健康检查与仪表盘）
export function getHealthStatus() {
  return request.get('/monitoring/health')
}

export function getDashboardData() {
  return request.get('/monitoring/dashboard')
}
