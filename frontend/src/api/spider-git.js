import request from './request'

/**
 * 爬虫 Git 管理 API
 */

// 克隆仓库
export function gitClone(spiderId, data) {
  return request.post(`/spiders/${spiderId}/git/clone`, data)
}

// 拉取代码
export function gitPull(spiderId, data = {}) {
  return request.post(`/spiders/${spiderId}/git/pull`, data)
}

// 推送代码
export function gitPush(spiderId, data = {}) {
  return request.post(`/spiders/${spiderId}/git/push`, data)
}

// 获取分支列表
export function gitGetBranches(spiderId) {
  return request.get(`/spiders/${spiderId}/git/branches`)
}

// 分支操作
export function gitBranchOperation(spiderId, data) {
  return request.post(`/spiders/${spiderId}/git/branch`, data)
}

// 获取提交历史
export function gitGetCommits(spiderId, limit = 20) {
  return request.get(`/spiders/${spiderId}/git/commits`, {
    params: { limit }
  })
}

// 获取仓库状态
export function gitGetStatus(spiderId) {
  return request.get(`/spiders/${spiderId}/git/status`)
}
