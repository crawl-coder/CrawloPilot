import request from './request'

/**
 * 项目 Git 操作 API
 */

// ==================== Git Operations ====================

/**
 * 克隆 Git 仓库
 */
export function gitClone(projectId, data) {
  return request({
    url: `/projects/${projectId}/git/clone`,
    method: 'post',
    data
  })
}

/**
 * 拉取远程更新
 */
export function gitPull(projectId, data = {}) {
  return request({
    url: `/projects/${projectId}/git/pull`,
    method: 'post',
    data
  })
}

/**
 * 推送到远程仓库
 */
export function gitPush(projectId, data = {}) {
  return request({
    url: `/projects/${projectId}/git/push`,
    method: 'post',
    data
  })
}

/**
 * 获取分支列表
 */
export function gitGetBranches(projectId, remote = false) {
  return request({
    url: `/projects/${projectId}/git/branches`,
    method: 'get',
    params: { remote }
  })
}

/**
 * 创建或切换分支
 */
export function gitBranchOperation(projectId, data) {
  return request({
    url: `/projects/${projectId}/git/branch`,
    method: 'post',
    data
  })
}

/**
 * 获取提交历史
 */
export function gitGetCommits(projectId, maxCount = 50) {
  return request({
    url: `/projects/${projectId}/git/commits`,
    method: 'get',
    params: { max_count: maxCount }
  })
}

/**
 * 获取标签列表
 */
export function gitGetTags(projectId) {
  return request({
    url: `/projects/${projectId}/git/tags`,
    method: 'get'
  })
}

/**
 * 创建标签
 */
export function gitCreateTag(projectId, data) {
  return request({
    url: `/projects/${projectId}/git/tag`,
    method: 'post',
    data
  })
}

/**
 * 获取仓库状态
 */
export function gitGetStatus(projectId) {
  return request({
    url: `/projects/${projectId}/git/status`,
    method: 'get'
  })
}

/**
 * 提交更改
 */
export function gitCommit(projectId, data) {
  return request({
    url: `/projects/${projectId}/git/commit`,
    method: 'post',
    data
  })
}

// ==================== File Upload Operations ====================

/**
 * 上传代码包
 */
export function uploadCodePackage(projectId, formData) {
  return request({
    url: `/projects/${projectId}/upload`,
    method: 'post',
    data: formData,
    headers: {
      'Content-Type': 'multipart/form-data'
    },
    timeout: 60000  // 上传超时60秒
  })
}

/**
 * 列出上传的文件
 */
export function listUploadedFiles(projectId) {
  return request({
    url: `/projects/${projectId}/uploads`,
    method: 'get'
  })
}

/**
 * 删除上传的文件
 */
export function deleteUploadedFile(projectId, filename) {
  return request({
    url: `/projects/${projectId}/uploads/${filename}`,
    method: 'delete'
  })
}
