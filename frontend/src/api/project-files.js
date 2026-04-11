import request from './request'

/**
 * 项目文件管理 API
 */

// 获取文件树
export function getFileTree(projectId, path = '') {
  return request.get(`/projects/${projectId}/files/tree`, {
    params: { path }
  })
}

// 获取文件内容
export function getFileContent(projectId, path) {
  return request.get(`/projects/${projectId}/files/content`, {
    params: { path }
  })
}

// 保存文件内容
export function saveFileContent(projectId, path, content) {
  return request.post(`/projects/${projectId}/files/content`, {
    path,
    content
  })
}

// 创建文件或目录
export function createFileOrDir(projectId, path, isDirectory = false) {
  return request.post(`/projects/${projectId}/files/create`, {
    path,
    is_directory: isDirectory
  })
}

// 删除文件或目录
export function deleteFileOrDir(projectId, path) {
  return request.delete(`/projects/${projectId}/files`, {
    params: { path }
  })
}

// 重命名文件或目录
export function renameFileOrDir(projectId, oldPath, newName) {
  return request.put(`/projects/${projectId}/files/rename`, {
    old_path: oldPath,
    new_name: newName
  })
}
