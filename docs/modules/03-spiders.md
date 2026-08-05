# 爬虫管理

## 职责

爬虫是运行单元：一个爬虫对应一份代码目录 + 一个入口文件 + 一个爬虫名称。
支持代码在线浏览/编辑、运行、停止、查看运行记录。

## 数据模型（`spider`）

关键字段：

- `spider_type`：crawlo / scrapy / selenium / playwright / requests / custom
- `status`：**启用态**（draft / active / disabled / error），与任务运行态分离
- `entry_file`：入口文件（默认 run.py）
- `spider_name`：传给 crawlo 的爬虫名称
- `run_count / success_count / error_count / last_run_at / last_run_status`：运行统计
- `git_*`：Git 相关字段（V1 保留字段，功能已裁剪）

## 后端实现（`backend/app/api/v1/spiders.py`）

| 接口 | 说明 |
|------|------|
| `GET/POST/PUT/DELETE /spiders` | CRUD |
| `POST /spiders/{id}/run` | 运行（body 可选，无节点=本地执行） |
| `POST /spiders/{id}/stop` | 停止（按 task_id 或停止全部运行中） |
| `GET /spiders/{id}/files/tree` | 代码文件树 |
| `GET/POST /spiders/{id}/files/content` | 读取/保存文件内容 |
| `POST /spiders/{id}/files/create` | 创建文件/目录 |
| `DELETE /spiders/{id}/files` | 删除文件 |

### 运行分发逻辑

`run_spider` 创建任务后按节点类型分发：

```text
无节点 → 本地执行（LocalExecutor）
node.connect_type = ssh    → SshExecutor
node.connect_type = docker → DockerExecutor
node.connect_type = agent  → 任务保持 PENDING，等 agent 领取
```

### 代码目录规范

```text
uploads/project_{id}/spider_{id}/
├── crawlo.cfg              # 必须：指定 settings 模块
├── run.py                  # 入口
└── <package>/              # 爬虫包（spiders/ 目录）
```

缺少 `crawlo.cfg` 时 crawler 无法定位 `SPIDER_MODULES`，运行会报
`Spider not found in registry`。

## 前端实现

- `frontend/src/views/Spiders.vue`：爬虫列表（卡片/列表视图、搜索、创建向导）
- `frontend/src/views/SpiderDetail.vue`：
  - 代码结构 tab：文件树 + 代码预览/编辑（高亮、行号、横向/纵向滚动）
  - 运行记录 tab：该爬虫的任务列表（跳执行详情、重试）
  - 运行对话框：本地 / 指定节点（SSH/Docker/Agent）
- 运行成功后自动跳转到执行详情页
