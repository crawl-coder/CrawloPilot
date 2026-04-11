# 前端 401 问题诊断指南

## 问题现象
- 登录后访问页面，自动跳转到登录页
- 控制台显示 401 Unauthorized 错误
- Token 存在但验证失败

## 诊断步骤

### 1. 清除浏览器缓存
```javascript
// 在浏览器控制台 (F12) 执行
localStorage.clear()
sessionStorage.clear()
location.reload()
```

### 2. 重新登录
1. 访问 http://localhost:3000/login
2. 用户名: `admin`
3. 密码: `admin123`
4. 点击登录

### 3. 检查 Token
```javascript
// 在控制台执行
const token = localStorage.getItem('token')
console.log('Token 存在:', !!token)
if (token) {
  console.log('Token 长度:', token.length)
  console.log('Token 前50字符:', token.substring(0, 50))
  
  // 解析 JWT
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    console.log('Token Payload:', payload)
    console.log('用户 ID:', payload.sub)
    console.log('过期时间:', new Date(payload.exp * 1000))
  } catch (e) {
    console.error('Token 解析失败:', e)
  }
}
```

### 4. 测试 API 调用
```javascript
// 测试认证 API
const token = localStorage.getItem('token')
fetch('http://localhost:8000/api/v1/auth/me', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
})
.then(r => r.json())
.then(d => console.log('✅ /auth/me 成功:', d))
.catch(e => console.error('❌ /auth/me 失败:', e))

// 测试部署 API
fetch('http://localhost:8000/api/v1/deploys/', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
})
.then(r => r.json())
.then(d => console.log('✅ /deploys/ 成功:', d))
.catch(e => console.error('❌ /deploys/ 失败:', e))
```

### 5. 检查请求拦截器
```javascript
// 在控制台执行，查看每次请求
const originalFetch = window.fetch
window.fetch = function(...args) {
  console.log('📡 Fetch 请求:', args[0])
  console.log('  Headers:', args[1]?.headers)
  return originalFetch.apply(this, args)
}
```

## 常见问题

### 问题 1: Token 保存后立即消失
**原因**: 页面加载时某个 API 返回 401，触发了 token 清除
**解决**: 
1. 检查 Network 面板，看哪个请求最先返回 401
2. 确认后端 SECRET_KEY 配置一致

### 问题 2: Token 存在但验证失败
**原因**: 
- 后端 SECRET_KEY 不一致
- Token 已过期
- Token 格式错误

**解决**:
```javascript
// 检查 Token 是否过期
const token = localStorage.getItem('token')
const payload = JSON.parse(atob(token.split('.')[1]))
const isExpired = Date.now() > payload.exp * 1000
console.log('Token 是否过期:', isExpired)
```

### 问题 3: 某些页面 401，某些正常
**原因**: 不同 API 的认证配置不同
**解决**: 检查后端路由的依赖注入配置

## 后端验证

### 测试后端 JWT
```bash
cd /Users/oscar/projects/CrawloPilot
python diagnose_401.py
```

### 检查后端日志
```bash
tail -f logs/backend.log | grep -i "401\|auth\|token"
```

## 快速修复

如果以上都不行，执行：
```javascript
// 1. 清除所有数据
localStorage.clear()
sessionStorage.clear()

// 2. 硬刷新
location.href = 'http://localhost:3000/login?_=' + Date.now()

// 3. 重新登录
```
