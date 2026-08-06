import request from './request'

/**
 * 定时任务调度 API
 */

// 调度列表（可按项目/爬虫/状态筛选）
export function getSchedules(params) {
  return request.get('/schedules', { params })
}

// 创建调度（同一爬虫 upsert，V1 一对一）
export function createSchedule(data) {
  return request.post('/schedules', data)
}

// 更新调度
export function updateSchedule(scheduleId, data) {
  return request.put(`/schedules/${scheduleId}`, data)
}

// 删除调度
export function deleteSchedule(scheduleId) {
  return request.delete(`/schedules/${scheduleId}`)
}

// 启用/停用
export function enableSchedule(scheduleId) {
  return request.post(`/schedules/${scheduleId}/enable`)
}

export function disableSchedule(scheduleId) {
  return request.post(`/schedules/${scheduleId}/disable`)
}

// 立即执行一次
export function runScheduleNow(scheduleId) {
  return request.post(`/schedules/${scheduleId}/run-now`)
}

// 预览下次运行时间
export function previewSchedule(params) {
  return request.get('/schedules/preview', { params })
}

// 调度运行历史
export function getScheduleHistory(scheduleId, params) {
  return request.get(`/schedules/${scheduleId}/history`, { params })
}
