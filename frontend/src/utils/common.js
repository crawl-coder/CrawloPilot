/**
 * CrawloPilot 公共工具函数
 * 跨页面共享的状态映射、格式化等纯函数
 */

// ==================== 爬虫状态 ====================

export const SPIDER_STATUS_MAP = {
  draft: { type: 'info', text: '草稿' },
  active: { type: 'success', text: '启用' },
  disabled: { type: 'warning', text: '已禁用' },
  error: { type: 'danger', text: '错误' }
}

export function getSpiderStatusType(status) {
  return SPIDER_STATUS_MAP[status]?.type || 'info'
}

export function getSpiderStatusText(status) {
  return SPIDER_STATUS_MAP[status]?.text || status
}

// ==================== 任务状态 ====================

export const TASK_STATUS_MAP = {
  pending: { type: 'info', text: '待执行' },
  running: { type: '', text: '运行中' },
  paused: { type: 'warning', text: '已暂停' },
  success: { type: 'success', text: '成功' },
  failed: { type: 'danger', text: '失败' },
  timeout: { type: 'warning', text: '超时' },
  cancelled: { type: 'info', text: '已取消' }
}

export function getTaskStatusType(status) {
  return TASK_STATUS_MAP[status]?.type || 'info'
}

export function getTaskStatusText(status) {
  return TASK_STATUS_MAP[status]?.text || status
}

// ==================== 爬虫类型颜色 ====================

export const SPIDER_TYPE_COLORS = {
  crawlo: '#722ED1',
  scrapy: '#FA8C16',
  selenium: '#1890FF',
  playwright: '#52C41A',
  requests: '#8C8C8C',
  custom: '#13C2C2'
}

export function getSpiderTypeColor(type) {
  return SPIDER_TYPE_COLORS[type] || '#8C8C8C'
}

// ==================== 时间格式化 ====================

/**
 * 格式化日期字符串为中文格式
 */
export function formatDateTime(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

/**
 * 格式化为相对时间（刚刚 / N分钟前 / N小时前 / N天前）
 */
export function formatRelativeTime(dateStr) {
  if (!dateStr) return '未运行'

  const now = new Date()
  const date = new Date(dateStr)
  const diff = Math.floor((now - date) / 1000) // 秒

  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)}分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)}小时前`
  if (diff < 604800) return `${Math.floor(diff / 86400)}天前`

  return formatDateTime(dateStr)
}

/**
 * 格式化秒数为可读时长
 */
export function formatDuration(seconds) {
  if (seconds >= 3600) {
    return `${Math.floor(seconds / 3600)}小时`
  } else if (seconds >= 60) {
    return `${Math.floor(seconds / 60)}分钟`
  }
  return `${seconds}秒`
}
