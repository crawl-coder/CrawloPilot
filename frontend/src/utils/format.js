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
    active: '运行中',
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

export function formatTime(time) {
  if (!time) return '-'
  return new Date(time).toLocaleString('zh-CN')
}

export function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

export function formatRelativeTime(time) {
  if (!time) return '-'
  const diff = Date.now() - new Date(time).getTime()
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
