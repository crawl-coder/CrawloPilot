# Git集成与文件上传

## 概述
项目管理模块提供完整的Git操作能力和本地代码上传功能。

## Git功能

### 1. 克隆仓库
```javascript
import { gitClone } from '@/api/project-git'

await gitClone(projectId, {
  url: 'https://github.com/user/repo.git',
  branch: 'main',  // 可选
  username: 'user',  // 私有仓库需要
  password: 'token'  // 私有仓库需要
})
```

**后端实现**:
- 使用GitPython库
- 支持HTTP/HTTPS/SSH协议
- 浅克隆加快速度 (`--depth 1`)
- 自动验证克隆结果

### 2. 拉取更新
```javascript
import { gitPull } from '@/api/project-git'

await gitPull(projectId, {
  remote: 'origin',
  branch: 'main'  // 可选
})
```

**功能**:
- 自动检测远程更新
- 显示更新的文件列表
- 冲突检测和提示

### 3. 推送代码
```javascript
import { gitPush } from '@/api/project-git'

await gitPush(projectId, {
  remote: 'origin',
  branch: 'main',
  username: 'user',
  password: 'token'
})
```

### 4. 分支管理

#### 获取分支列表
```javascript
import { gitGetBranches } from '@/api/project-git'

// 本地分支
const localBranches = await gitGetBranches(projectId, false)

// 远程分支
const remoteBranches = await gitGetBranches(projectId, true)
```

#### 切换分支
```javascript
import { gitCheckout } from '@/api/project-git'

await gitCheckout(projectId, {
  branch: 'develop',
  create: false  // true表示创建新分支
})
```

### 5. 提交历史
```javascript
import { gitGetCommits } from '@/api/project-git'

const commits = await gitGetCommits(projectId, {
  max_count: 50,  // 默认50条
  branch: 'main'  // 可选
})
```

**返回数据**:
```json
[
  {
    "hash": "abc123",
    "author": "John Doe",
    "email": "john@example.com",
    "message": "Fix bug #123",
    "date": "2026-04-11T10:30:00",
    "branch": "main"
  }
]
```

### 6. 标签管理

#### 获取标签列表
```javascript
import { gitGetTags } from '@/api/project-git'

const tags = await gitGetTags(projectId)
```

#### 创建标签
```javascript
import { gitCreateTag } from '@/api/project-git'

await gitCreateTag(projectId, {
  tag: 'v1.0.0',
  message: 'Release version 1.0.0'
})
```

### 7. 仓库状态
```javascript
import { gitStatus } from '@/api/project-git'

const status = await gitStatus(projectId)
// 返回: { branch, modified, untracked, staged, clean }
```

## 本地上传功能

### 1. 上传代码包
```javascript
import { uploadCodePackage } from '@/api/project-git'

const formData = new FormData()
formData.append('file', file)  // File对象

const result = await uploadCodePackage(projectId, formData)
```

**支持格式**:
- ZIP (.zip)
- TAR (.tar)
- GZIP (.tar.gz, .tgz)
- BZIP2 (.tar.bz2)

**文件大小限制**: 100MB

### 2. 自动解压
上传后自动解压到项目目录：
```
projects/
  └── {project_id}/
      └── code/
          └── {解压的文件}
```

### 3. 上传验证
- ✅ 文件类型验证
- ✅ 文件大小验证
- ✅ 压缩包完整性检查
- ✅ 解压后文件列表返回

## API端点

### Git操作
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/git/clone` | 克隆仓库 |
| POST | `/api/v1/projects/{id}/git/pull` | 拉取更新 |
| POST | `/api/v1/projects/{id}/git/push` | 推送代码 |
| GET | `/api/v1/projects/{id}/git/branches` | 获取分支列表 |
| POST | `/api/v1/projects/{id}/git/checkout` | 切换分支 |
| GET | `/api/v1/projects/{id}/git/commits` | 获取提交历史 |
| GET | `/api/v1/projects/{id}/git/tags` | 获取标签列表 |
| POST | `/api/v1/projects/{id}/git/create-tag` | 创建标签 |
| GET | `/api/v1/projects/{id}/git/status` | 仓库状态 |
| GET | `/api/v1/projects/{id}/git/info` | 仓库信息 |

### 文件上传
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/projects/{id}/upload` | 上传代码包 |
| GET | `/api/v1/projects/{id}/upload/history` | 上传历史 |
| GET | `/api/v1/projects/{id}/upload/files` | 文件列表 |

## 使用场景

### 场景1: 从GitHub导入项目
```javascript
// 1. 克隆仓库
await gitClone(projectId, {
  url: 'https://github.com/user/spider-project.git',
  branch: 'main'
})

// 2. 查看提交历史
const commits = await gitGetCommits(projectId)

// 3. 拉取最新代码
await gitPull(projectId)
```

### 场景2: 上传本地爬虫代码
```javascript
// 1. 选择ZIP文件
const file = fileInput.files[0]

// 2. 上传
const formData = new FormData()
formData.append('file', file)
const result = await uploadCodePackage(projectId, formData)

// 3. 查看解压后的文件
const files = await getProjectFiles(projectId)
```

### 场景3: 多分支开发
```javascript
// 1. 查看所有分支
const branches = await gitGetBranches(projectId, true)

// 2. 切换到开发分支
await gitCheckout(projectId, { branch: 'develop' })

// 3. 拉取最新代码
await gitPull(projectId, { branch: 'develop' })

// 4. 完成开发后推送
await gitPush(projectId, { branch: 'develop' })
```

## 安全注意事项

### 1. 认证信息
- ⚠️ 不要硬编码用户名和密码
- ✅ 使用环境变量或密钥管理
- ✅ 使用Personal Access Token代替密码

### 2. SSH密钥
对于SSH协议，需要配置SSH密钥：
```bash
# 生成SSH密钥
ssh-keygen -t ed25519 -C "your_email@example.com"

# 添加到SSH agent
ssh-add ~/.ssh/id_ed25519

# 配置Git使用SSH
git config core.sshCommand "ssh -i ~/.ssh/id_ed25519"
```

### 3. 文件上传安全
- ✅ 验证文件类型和大小
- ✅ 沙箱环境解压
- ✅ 扫描恶意文件
- ✅ 限制执行权限

## 错误处理

### 常见错误

#### 1. 克隆失败
```javascript
try {
  await gitClone(projectId, { url })
} catch (error) {
  if (error.response?.status === 400) {
    // 仓库不存在或认证失败
    ElMessage.error('仓库地址或认证信息有误')
  }
}
```

#### 2. 推送冲突
```javascript
try {
  await gitPush(projectId)
} catch (error) {
  if (error.detail?.includes('conflict')) {
    ElMessage.warning('推送冲突，请先拉取最新代码')
    await gitPull(projectId)
  }
}
```

#### 3. 上传失败
```javascript
try {
  await uploadCodePackage(projectId, formData)
} catch (error) {
  if (error.response?.status === 413) {
    ElMessage.error('文件太大，请压缩后重试')
  }
}
```

## 最佳实践

### 1. Git工作流
```
main (稳定) 
  ↑
  └── develop (开发)
        ↑
        └── feature/xxx (特性分支)
```

### 2. 提交规范
```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码格式
refactor: 重构
test: 测试
chore: 构建/工具
```

### 3. 标签命名
- 版本标签: `v1.0.0`, `v2.1.0`
- 里程碑: `milestone-phase1`
- 发布候选: `rc-1.0.0`

### 4. 上传建议
- 上传前排除 `node_modules/`, `__pycache__/` 等
- 使用 `.gitignore` 管理忽略文件
- 大文件考虑使用Git LFS

## 依赖

### 后端
```txt
GitPython==3.1.40  # Git操作库
```

### 前端
```javascript
// 无需额外依赖，使用原生FormData
```

## 相关文件
- 后端服务: `backend/app/services/git_service.py`
- 上传服务: `backend/app/services/upload_service.py`
- API路由: `backend/app/api/v1/project_git.py`
- 前端API: `frontend/src/api/project-git.js`
