import request from './request'

/**
 * 共享 Git 凭据（团队机器人凭据）API
 * 列表全员可读（脱敏），写操作仅 admin
 */

// 凭据列表（默认仅启用中的）
export function getGitCredentials(params) {
  return request.get('/git-credentials', { params })
}

// 创建凭据（admin）
export function createGitCredential(data) {
  return request.post('/git-credentials', data)
}

// 更新凭据（admin；秘密字段留空=保留原值）
export function updateGitCredential(id, data) {
  return request.put(`/git-credentials/${id}`, data)
}

// 删除凭据（admin；被爬虫引用时后端拒绝）
export function deleteGitCredential(id) {
  return request.delete(`/git-credentials/${id}`)
}
