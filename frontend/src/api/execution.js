/**
 * 任务执行 API
 */

import request from './request'

/**
 * 创建并执行任务
 */
export function createAndExecuteTask(data) {
  return request({
    url: '/execution/tasks',
    method: 'post',
    data
  })
}

/**
 * 停止任务
 */
export function stopTask(taskId) {
  return request({
    url: `/execution/tasks/${taskId}/stop`,
    method: 'post'
  })
}

/**
 * 暂停任务
 */
export function pauseTask(taskId) {
  return request({
    url: `/execution/tasks/${taskId}/pause`,
    method: 'post'
  })
}

/**
 * 恢复任务
 */
export function resumeTask(taskId) {
  return request({
    url: `/execution/tasks/${taskId}/resume`,
    method: 'post'
  })
}

/**
 * 获取任务状态
 */
export function getTaskStatus(taskId) {
  return request({
    url: `/execution/tasks/${taskId}/status`,
    method: 'get'
  })
}

/**
 * 获取任务日志
 */
export function getTaskLogs(taskId, tail = 100) {
  return request({
    url: `/execution/tasks/${taskId}/logs`,
    method: 'get',
    params: { tail }
  })
}

/**
 * 查询任务列表
 */
export function listTasks(params) {
  return request({
    url: '/execution/tasks',
    method: 'get',
    params
  })
}

/**
 * 删除任务
 */
export function deleteTask(taskId) {
  return request({
    url: `/execution/tasks/${taskId}`,
    method: 'delete'
  })
}

/**
 * 任务实例统计（task-instances API）
 */
export function getTaskStats(params) {
  return request({
    url: '/task-instances/stats/summary',
    method: 'get',
    params
  })
}

/**
 * 重试任务
 */
export function retryTask(taskId) {
  return request({
    url: `/task-instances/${taskId}/retry`,
    method: 'post'
  })
}
