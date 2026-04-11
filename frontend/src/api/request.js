import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

// 请求拦截器
request.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
request.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    if (error.response) {
      switch (error.response.status) {
        case 401:
          const currentToken = localStorage.getItem('token')
          console.error('❌ 401 未授权错误')
          console.error('  请求 URL:', error.config?.url)
          console.error('  Token 存在:', !!currentToken)
          if (currentToken) {
            console.error('  Token 前50字符:', currentToken.substring(0, 50))
          }
          
          // 检查是否是旧的无效 token
          ElMessage.warning('登录已过期，请重新登录')
          localStorage.removeItem('token')
          
          // 延迟跳转，避免与其他路由冲突
          setTimeout(() => {
            if (window.location.pathname !== '/login') {
              window.location.href = '/login'
            }
          }, 1500)
          break
        case 403:
          ElMessage.error('权限不足')
          break
        case 404:
          ElMessage.error('请求的资源不存在')
          break
        case 500:
          console.error('服务器错误:', error.response.data)
          ElMessage.error('服务器错误: ' + (error.response.data.detail || '未知错误'))
          break
        default:
          ElMessage.error(error.response.data.detail || '请求失败')
      }
    } else if (error.request) {
      console.error('网络错误:', error.message)
      ElMessage.error('网络错误，请检查连接')
    }
    return Promise.reject(error)
  }
)

export default request
