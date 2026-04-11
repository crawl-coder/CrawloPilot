import request from './request'

// 调度配置 API
export function getSchedules(params) {
  return request.get('/schedules', { params })
}

export function getSchedule(id) {
  return request.get(`/schedules/${id}`)
}

export function createSchedule(data) {
  return request.post('/schedules', data)
}

export function updateSchedule(id, data) {
  return request.put(`/schedules/${id}`, data)
}

export function deleteSchedule(id) {
  return request.delete(`/schedules/${id}`)
}

export function enableSchedule(id) {
  return request.post(`/schedules/${id}/enable`)
}

export function disableSchedule(id) {
  return request.post(`/schedules/${id}/disable`)
}

export function triggerSchedule(id) {
  return request.post(`/schedules/${id}/trigger`)
}

export function getScheduleDag(id) {
  return request.get(`/schedules/${id}/dag`)
}

// 任务实例 API
export function getTaskInstances(params) {
  return request.get('/task-instances', { params })
}

export function getTaskInstance(id) {
  return request.get(`/task-instances/${id}`)
}

export function getTasksBySchedule(scheduleId, limit = 50) {
  return request.get(`/task-instances/schedule/${scheduleId}`, { params: { limit } })
}

export function getRunningTasks() {
  return request.get('/task-instances/running')
}

export function getTaskStats(params) {
  return request.get('/task-instances/stats/summary', { params })
}

export function retryTask(id) {
  return request.post(`/task-instances/${id}/retry`)
}

export function stopTask(id) {
  return request.post(`/task-instances/${id}/stop`)
}

export function getTaskLogs(id) {
  return request.get(`/task-instances/${id}/logs`)
}

export function getRecentTasks(limit = 100) {
  return request.get('/task-instances/recent', { params: { limit } })
}
