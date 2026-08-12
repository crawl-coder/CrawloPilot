import request from './request'

export function login(data) {
  const formData = new URLSearchParams()
  formData.append('username', data.username)
  formData.append('password', data.password)
  
  return request.post('/auth/login', formData, {
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    }
  })
}

export function register(data) {
  return request.post('/auth/register', data)
}

export function getCurrentUser() {
  return request.get('/auth/me')
}

// 获取个人 Git 凭据（脱敏）
export function getMyGitCredentials() {
  return request.get('/auth/me/git-credentials')
}

// 保存个人 Git 凭据（秘密字段留空=保留原值）
export function saveMyGitCredentials(data) {
  return request.put('/auth/me/git-credentials', data)
}

// 清除个人 Git 凭据
export function deleteMyGitCredentials() {
  return request.delete('/auth/me/git-credentials')
}

// 登录日志（admin 看全部，普通用户看自己）
export function getLoginLogs(params) {
  return request.get('/auth/login-logs', { params })
}
