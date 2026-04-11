# 紧急修复：浏览器缓存问题

## 问题诊断
- 前端代码已更新，但浏览器缓存了旧版本
- 请求直接访问 `http://127.0.0.1:8000` 而不是通过 Vite 代理 `http://localhost:3000`

## 立即执行（按顺序）

### 步骤 1: 完全停止服务
```bash
cd /Users/oscar/projects/CrawloPilot
./dev.sh --stop
```

### 步骤 2: 清除浏览器所有数据
在浏览器控制台 (F12) 执行：
```javascript
// 清除所有存储
localStorage.clear()
sessionStorage.clear()

// 清除所有 Service Workers
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(registrations => {
    registrations.forEach(reg => reg.unregister())
  })
}

// 清除所有 Cache Storage
caches.keys().then(names => names.forEach(name => caches.delete(name)))

console.log('✅ 所有缓存已清除')
```

### 步骤 3: 关闭浏览器
**完全关闭浏览器**（不是关闭标签页，是退出整个浏览器应用）

### 步骤 4: 重启服务
```bash
cd /Users/oscar/projects/CrawloPilot
./start-dev.sh
```

### 步骤 5: 重新打开浏览器
1. 打开浏览器
2. 访问 `http://localhost:3000`
3. **不要使用书签或历史记录，手动输入地址**
4. 登录并测试

## 如果还是不行

### 使用无痕模式测试
1. 打开浏览器无痕/隐私模式
   - Chrome: `Cmd + Shift + N` (Mac) 或 `Ctrl + Shift + N` (Windows)
   - Safari: `Cmd + Shift + N`
2. 访问 `http://localhost:3000`
3. 登录并测试

### 检查 Network 面板
在 Network 面板中查看请求 URL：
- ✅ 正确：`http://localhost:3000/api/v1/nodes/`
- ❌ 错误：`http://127.0.0.1:8000/api/v1/nodes/`

## 验证修复

在浏览器控制台执行：
```javascript
// 测试 API 调用
const token = localStorage.getItem('token')
fetch('/api/v1/nodes/', {
  headers: {
    'Authorization': 'Bearer ' + token
  }
})
.then(r => {
  console.log('状态码:', r.status)
  return r.json()
})
.then(d => console.log('✅ 成功:', d))
.catch(e => console.error('❌ 失败:', e))
```

如果返回 200，说明代理正常工作。
