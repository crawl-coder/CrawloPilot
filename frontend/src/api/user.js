import request from './request'

/**
 * 用户管理 API
 */

// 获取角色列表
export function getRoles() {
  return request.get('/users/roles')
}

// 获取用户列表
export function getUsers(params) {
  return request.get('/users', { params })
}

// 获取用户详情
export function getUser(id) {
  return request.get(`/users/${id}`)
}

// 创建用户
export function createUser(data) {
  return request.post('/users', data)
}

// 更新用户
export function updateUser(id, data) {
  return request.put(`/users/${id}`, data)
}

// 删除用户
export function deleteUser(id) {
  return request.delete(`/users/${id}`)
}

// 重置密码
export function resetPassword(id, newPassword) {
  return request.post(`/users/${id}/reset-password`, null, {
    params: { new_password: newPassword }
  })
}

// 切换用户状态
export function toggleUserStatus(id) {
  return request.post(`/users/${id}/toggle-status`)
}
