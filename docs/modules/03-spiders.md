> 📖 模块导航：[导读](README.md) ｜ [docs 首页](../README.md)
> 🔗 上一篇：[项目管理](02-projects.md)
> 🔗 下一篇：[部署执行](04-execution.md)

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
- `git_*`：Git 工作流字段（仓库地址/认证方式/分支；秘密字段加密落库、API 不回传）
- `git_credential_id`：引用的共享 Git 凭据（凭据池，见 `git_credential` 表）

## 后端实现（`backend/app/api/v1/spiders.py`）

| 接口 | 说明 |
|------|------|
| `GET/POST/PUT/DELETE /spiders` | CRUD（创建支持 use_my_git_credential / git_credential_id 凭据来源） |
| `POST /spiders/{id}/run` | 运行（body 可选，无节点=本地执行） |
| `POST /spiders/{id}/stop` | 停止（按 task_id 或停止全部运行中） |
| `POST /spiders/{id}/upload` | ZIP/TAR 代码包上传解压 |
| `GET /spiders/{id}/files/tree` | 代码文件树 |
| `GET/POST /spiders/{id}/files/content` | 读取/保存文件内容 |
| `POST /spiders/{id}/files/create` | 创建文件/目录 |
| `DELETE /spiders/{id}/files` | 删除文件 |
| `GET /spiders/{id}/git/status` `GET .../git/branches` | 仓库状态 / 分支列表 |
| `POST /spiders/{id}/git/clone` | 克隆（支持 http/https/ssh，完整仓库含 .git） |
| `POST /spiders/{id}/git/commit` `.../git/push` `.../git/pull` `.../git/checkout` | 提交 / 推送 / 拉取 / 切分支 |

### Git 工作流与凭据

- Git 来源爬虫保留完整 `.git`，详情页可直接提交/推送/拉取/切分支；
- 认证凭据单次命令注入（密码拼 URL / SSH 私钥临时文件），不写回 `.git/config`；
- 凭据三级来源：**共享凭据池**（git_credential_id）> **个人凭据**（use_my_git_credential
  自动填充）> 手动内联；内联秘密字段（git_password/git_ssh_key/git_passphrase）
  Fernet 加密落库，详情接口不回传。

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

### 代码生命周期（控制面为唯一代码源）

**核心模型**：控制面 A 是爬虫代码的唯一源头（git 工作区），
节点只是"每次运行时的执行副本"。代码变更一律在控制面完成并提交，
节点上的修改不会同步回控制面、也不会被平台提交。

#### 代码存放位置

```text
克隆/上传时 → 控制面 uploads/project_{id}/spider_{id}/（保留 .git）
   ↑ 唯一代码源，所有编辑/提交/推送在此进行
```

#### 代码分发到节点（每次运行按需分发）

| 模式 | 分发方式 | 节点上的代码 |
|------|----------|--------------|
| SSH | A 打包 tar.gz → SFTP 上传 → 远程解压 | `/opt/crawlopilot/workspace/{task_id}/`（含 .git） |
| Docker | A 遍历代码（排除 `.git`）→ 构建镜像 COPY | 镜像内 `/app`，容器运行 |
| Agent | A 打包 tar.gz → agent 经 `/tasks/{id}/code` 下载 | 节点临时目录 |

节点上的代码是**运行副本**：

- 修改不会同步回控制面（下次运行重新从 A 分发，修改即丢失）；
- Docker 构建明确排除 `.git`（避免镜像膨胀与密钥泄露风险）；
- 同一份代码可在多个节点运行：每建一个任务/调度并选择节点，
  即从 A 分发一次最新代码，节点之间互不影响。

#### 代码修改与 Git 提交流程

```text
1. 在控制面修改代码（Web 在线编辑器，或克隆到本地开发）
2. 爬虫详情页 Git 操作：提交 → 推送 → 拉取 → 切分支（git_service）
3. 下次运行任务 → A 自动分发最新代码到所选节点
```

**不要**在节点上改代码——那是只读执行沙箱，改动不持久、无法通过
平台提交推送。所有变更回到控制面代码目录统一管理。

## 前端实现

- `frontend/src/views/Spiders.vue`：爬虫列表（卡片/列表视图、搜索、创建向导）
- `frontend/src/views/SpiderDetail.vue`：
  - 代码结构 tab：文件树 + 代码预览/编辑（高亮、行号、横向/纵向滚动）
  - 运行记录 tab：该爬虫的任务列表（跳执行详情、重试）
  - 运行对话框：本地 / 指定节点（SSH/Docker/Agent）
- 运行成功后自动跳转到执行详情页
