# 项目 Git 管理和本地上传功能文档

## 功能概述

为 CrawloPilot 项目管理添加了完整的 Git 操作和本地代码上传功能。

## 后端 API 列表

### Git 操作 API

所有API路径前缀: `/api/v1/projects/{project_id}`

| 方法 | 路径 | 功能 | 请求体 |
|------|------|------|--------|
| POST | `/git/clone` | 克隆远程仓库 | `GitCloneRequest` |
| POST | `/git/pull` | 拉取远程更新 | `GitPullRequest` |
| POST | `/git/push` | 推送到远程 | `GitPushRequest` |
| GET | `/git/branches` | 获取分支列表 | - |
| POST | `/git/branch` | 创建/切换分支 | `GitBranchRequest` |
| GET | `/git/commits` | 获取提交历史 | - |
| GET | `/git/tags` | 获取标签列表 | - |
| POST | `/git/tag` | 创建标签 | `GitTagRequest` |
| GET | `/git/status` | 获取仓库状态 | - |
| POST | `/git/commit` | 提交更改 | `GitCommitRequest` |

### 文件上传 API

| 方法 | 路径 | 功能 | 请求体 |
|------|------|------|--------|
| POST | `/upload` | 上传代码包 | `multipart/form-data` |
| GET | `/uploads` | 列出上传文件 | - |
| DELETE | `/uploads/{filename}` | 删除上传文件 | - |

## 使用示例

### 1. 克隆 Git 仓库

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/git/clone \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "git_url": "https://github.com/username/repo.git",
    "branch": "main",
    "username": "your_username",
    "password": "your_password_or_token"
  }'
```

### 2. 拉取更新

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/git/pull \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "remote": "origin",
    "branch": "main"
  }'
```

### 3. 获取提交历史

```bash
curl -X GET http://localhost:8000/api/v1/projects/1/git/commits?max_count=20 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. 创建分支

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/git/branch \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "create",
    "branch_name": "feature/new-spider",
    "start_point": "main"
  }'
```

### 5. 提交更改

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/git/commit \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Add new spider for product scraping",
    "files": ["spiders/product_spider.py"]
  }'
```

### 6. 上传代码包

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@/path/to/your/project.zip"
```

支持的文件格式:
- `.zip`
- `.tar`
- `.tar.gz`
- `.tar.bz2`

### 7. 查看上传的文件

```bash
curl -X GET http://localhost:8000/api/v1/projects/1/uploads \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Python 测试脚本

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"
TOKEN = "YOUR_JWT_TOKEN"
PROJECT_ID = 1

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 1. 克隆仓库
clone_data = {
    "git_url": "https://github.com/example/repo.git",
    "branch": "main"
}
response = requests.post(
    f"{BASE_URL}/projects/{PROJECT_ID}/git/clone",
    headers=headers,
    json=clone_data
)
print(f"克隆仓库: {response.json()}")

# 2. 获取提交历史
response = requests.get(
    f"{BASE_URL}/projects/{PROJECT_ID}/git/commits",
    headers=headers
)
commits = response.json()['data']
print(f"提交历史: {len(commits)} 条")
for commit in commits[:5]:
    print(f"  - {commit['short_hash']}: {commit['message']}")

# 3. 获取分支列表
response = requests.get(
    f"{BASE_URL}/projects/{PROJECT_ID}/git/branches",
    headers=headers
)
print(f"分支: {response.json()['data']}")

# 4. 获取仓库状态
response = requests.get(
    f"{BASE_URL}/projects/{PROJECT_ID}/git/status",
    headers=headers
)
print(f"仓库状态: {response.json()['data']}")

# 5. 上传代码包
import aiohttp
import asyncio

async def upload_file():
    data = aiohttp.FormData()
    data.add_field('file',
                   open('project.zip', 'rb'),
                   filename='project.zip',
                   content_type='application/zip')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/projects/{PROJECT_ID}/upload",
            headers={"Authorization": f"Bearer {TOKEN}"},
            data=data
        ) as response:
            print(f"上传结果: {await response.json()}")

# asyncio.run(upload_file())
```

## 前端集成示例 (Vue 3)

```vue
<template>
  <div class="git-management">
    <!-- Git 克隆 -->
    <el-card>
      <template #header>克隆仓库</template>
      <el-form :model="cloneForm">
        <el-form-item label="仓库地址">
          <el-input v-model="cloneForm.git_url" placeholder="https://github.com/user/repo.git" />
        </el-form-item>
        <el-form-item label="分支">
          <el-input v-model="cloneForm.branch" placeholder="main" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="cloneForm.username" />
        </el-form-item>
        <el-form-item label="密码/Token">
          <el-input v-model="cloneForm.password" type="password" />
        </el-form-item>
        <el-button type="primary" @click="handleClone">克隆</el-button>
      </el-form>
    </el-card>

    <!-- 提交历史 -->
    <el-card>
      <template #header>提交历史</template>
      <el-timeline>
        <el-timeline-item
          v-for="commit in commits"
          :key="commit.hash"
          :timestamp="commit.date"
        >
          <strong>{{ commit.short_hash }}</strong>: {{ commit.message }}
          <br/>
          <small>{{ commit.author }}</small>
        </el-timeline-item>
      </el-timeline>
    </el-card>

    <!-- 文件上传 -->
    <el-card>
      <template #header>上传代码包</template>
      <el-upload
        action="#"
        :http-request="handleUpload"
        :before-upload="beforeUpload"
        accept=".zip,.tar,.gz"
      >
        <el-button type="primary">选择文件</el-button>
        <template #tip>
          <div class="el-upload__tip">
            支持 .zip, .tar, .tar.gz 格式
          </div>
        </template>
      </el-upload>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { gitClone, gitGetCommits, uploadCodePackage } from '@/api/project-git'
import { ElMessage } from 'element-plus'

const projectId = 1
const cloneForm = ref({
  git_url: '',
  branch: 'main',
  username: '',
  password: ''
})
const commits = ref([])

const handleClone = async () => {
  try {
    const res = await gitClone(projectId, cloneForm.value)
    ElMessage.success('克隆成功')
    loadCommits()
  } catch (error) {
    ElMessage.error('克隆失败: ' + error.message)
  }
}

const loadCommits = async () => {
  try {
    const { gitGetCommits } = await import('@/api/project-git')
    const res = await gitGetCommits(projectId)
    commits.value = res.data
  } catch (error) {
    console.error('加载提交历史失败:', error)
  }
}

const handleUpload = async (file) => {
  try {
    const formData = new FormData()
    formData.append('file', file.file)
    
    const res = await uploadCodePackage(projectId, formData)
    ElMessage.success('上传成功')
  } catch (error) {
    ElMessage.error('上传失败: ' + error.message)
  }
}

const beforeUpload = (file) => {
  const allowedTypes = [
    'application/zip',
    'application/x-tar',
    'application/gzip'
  ]
  const isAllowed = allowedTypes.includes(file.type) || 
                    file.name.endsWith('.zip') ||
                    file.name.endsWith('.tar') ||
                    file.name.endsWith('.gz')
  
  if (!isAllowed) {
    ElMessage.error('只支持 .zip, .tar, .gz 格式')
    return false
  }
  
  const isLt100M = file.size / 1024 / 1024 < 100
  if (!isLt100M) {
    ElMessage.error('文件大小不能超过 100MB')
    return false
  }
  
  return true
}

onMounted(() => {
  loadCommits()
})
</script>
```

## 存储结构

```
uploads/
└── project_{id}/
    ├── 20240411_123456_abc12345.zip          # 上传的原始文件
    ├── 20240411_123456_abc12345_extracted/    # 解压后的代码
    │   ├── spiders/
    │   ├── items.py
    │   └── ...
    └── code/                                   # Git 仓库目录
        ├── .git/
        ├── spiders/
        └── ...
```

## 注意事项

1. **Git 认证**: 
   - 建议使用 Personal Access Token 而不是密码
   - GitHub: Settings -> Developer settings -> Personal access tokens
   - GitLab: User Settings -> Access Tokens

2. **文件大小限制**: 
   - 默认限制 100MB
   - 可在 Nginx 配置中修改 `client_max_body_size`

3. **安全考虑**:
   - 密码不会存储在数据库中
   - Git 凭据存储在仓库目录的 `.git-credentials` 文件中
   - 建议定期清理不需要的上传文件

4. **性能优化**:
   - 克隆时使用浅克隆 (`depth=1`) 加快速度
   - 大文件上传建议使用异步任务处理

## API 文档

启动后端后访问: http://localhost:8000/docs

查找 **projects-git-upload** 标签查看所有 Git 和上传相关的 API。
