import request from './request'

/**
 * 爬虫管理 API
 */

// 获取爬虫列表
export function getSpiders(params) {
  return request.get('/spiders', { params })
}

// 获取爬虫详情
export function getSpider(spiderId) {
  return request.get(`/spiders/${spiderId}`)
}

// 创建爬虫
export function createSpider(data) {
  return request.post('/spiders', data)
}

// 更新爬虫
export function updateSpider(spiderId, data) {
  return request.put(`/spiders/${spiderId}`, data)
}

// 删除爬虫
export function deleteSpider(spiderId) {
  return request.delete(`/spiders/${spiderId}`)
}

// 运行爬虫
export function runSpider(spiderId, data = {}) {
  return request.post(`/spiders/${spiderId}/run`, data)
}

// 停止爬虫
export function stopSpider(spiderId) {
  return request.post(`/spiders/${spiderId}/stop`)
}

// 从 Git 仓库克隆代码
export function cloneSpiderGit(spiderId) {
  return request.post(`/spiders/${spiderId}/git/clone`)
}

// 上传爬虫代码包（ZIP/TAR）
export function uploadSpiderCode(spiderId, file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post(`/spiders/${spiderId}/upload`, formData)
}

// 获取爬虫文件树
export function getSpiderFileTree(spiderId, path = '') {
  return request.get(`/spiders/${spiderId}/files/tree`, {
    params: { path }
  })
}

// 获取爬虫文件内容
export function getSpiderFileContent(spiderId, path) {
  return request.get(`/spiders/${spiderId}/files/content`, {
    params: { path }
  })
}

// 保存爬虫文件内容
export function saveSpiderFileContent(spiderId, path, content) {
  return request.post(`/spiders/${spiderId}/files/content`, {
    path,
    content
  })
}

// 创建爬虫文件或目录
export function createSpiderFileOrDir(spiderId, path, isDirectory = false) {
  return request.post(`/spiders/${spiderId}/files/create`, null, {
    params: { path, is_directory: isDirectory }
  })
}

// 删除爬虫文件或目录
export function deleteSpiderFileOrDir(spiderId, path) {
  return request.delete(`/spiders/${spiderId}/files`, {
    params: { path }
  })
}

// ==================== Git 工作流 ====================

// 获取仓库状态（分支/改动/领先落后）
export function getGitStatus(spiderId) {
  return request.get(`/spiders/${spiderId}/git/status`)
}

// 获取分支列表
export function getGitBranches(spiderId) {
  return request.get(`/spiders/${spiderId}/git/branches`)
}

// 提交全部改动
export function gitCommit(spiderId, message) {
  return request.post(`/spiders/${spiderId}/git/commit`, { message })
}

// 推送当前分支
export function gitPush(spiderId) {
  return request.post(`/spiders/${spiderId}/git/push`)
}

// 拉取当前分支
export function gitPull(spiderId) {
  return request.post(`/spiders/${spiderId}/git/pull`)
}

// 切换/新建分支
export function gitCheckout(spiderId, branch, create = false) {
  return request.post(`/spiders/${spiderId}/git/checkout`, { branch, create })
}
