/**
 * 通用格式化工具函数
 * 消除 8+ 文件中的重复定义
 */

export function getStatusType(status) {
  const map = {
    // 任务状态
    pending: 'info',
    running: 'warning',
    success: 'success',
    failed: 'danger',
    cancelled: 'info',
    paused: 'warning',
    timeout: 'danger',
    // 爬虫/项目状态
    draft: 'info',
    active: 'success',
    disabled: 'warning',
    error: 'danger',
    // 节点状态
    online: 'success',
    offline: 'info',
    draining: 'warning',
    // 部署状态
    completed: 'success',
    deploying: 'warning',
    // 通用
    passed: 'success',
    warning: 'warning'
  }
  return map[status] || 'info'
}

export function getStatusText(status) {
  const map = {
    pending: '待执行',
    running: '运行中',
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
    paused: '已暂停',
    timeout: '超时',
    draft: '草稿',
    active: '启用',
    disabled: '已禁用',
    error: '错误',
    online: '在线',
    offline: '离线',
    draining: '排空',
    completed: '已完成',
    deploying: '部署中',
    passed: '通过',
    warning: '警告'
  }
  return map[status] || status || '-'
}

/**
 * 解析后端时间：
 * - 普通业务时间（任务/爬虫/项目等）已是北京时间 naive（如 2026-08-10T22:01:58），
 *   无时区标记时按 +08:00（北京时间）解析，再按浏览器本地时区显示；
 * - 带时区标记（Z / ±hh:mm）的直接解析。
 * 注意：调度 run_at 仍是 UTC naive，需单独加 'Z' 解析（见 SpiderFormDialog）。
 */
export function parseDate(value) {
  if (!value) return null
  const s = String(value).trim()
  const hasTz = /(Z|[+-]\d{2}:?\d{2})$/.test(s)
  const iso = hasTz ? s : s.replace(' ', 'T') + '+08:00'
  return new Date(iso)
}

export function formatTime(time) {
  const d = parseDate(time)
  if (!d || isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN')
}

export function formatDate(dateStr) {
  const d = parseDate(dateStr)
  if (!d || isNaN(d.getTime())) return '-'
  return d.toLocaleString('zh-CN')
}

export function formatRelativeTime(time) {
  const d = parseDate(time)
  if (!d || isNaN(d.getTime())) return '-'
  const diff = Date.now() - d.getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}天前`
  return formatTime(time)
}

export function getSpiderTypeColor(type) {
  const map = {
    crawlo: '#722ED1',
    scrapy: '#FA8C16',
    selenium: '#1890FF',
    playwright: '#52C41A',
    requests: '#8C8C8C',
    custom: '#13C2C2'
  }
  return map[type] || '#8C8C8C'
}

export function getScoreColor(score) {
  if (score >= 80) return '#67C23A'
  if (score >= 60) return '#E6A23C'
  return '#F56C6C'
}
