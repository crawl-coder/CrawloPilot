# 部署执行

## 职责

把爬虫任务送到执行面并跑起来，负责状态记录、日志汇聚、指标解析与停止控制。

## 执行器契约

所有执行方式实现同一套接口（`execute_task / get_task_status / get_task_logs / stop_task`），
业务层按任务 `deploy_mode` 分发（`backend/app/api/v1/execution.py` 的
`_get_executor_for_task`）：

| deploy_mode | 实现文件 | 执行方式 |
|-------------|----------|----------|
| `local` | `services/local_executor.py` | 本机子进程（subprocess） |
| `ssh` | `services/ssh_executor.py` | SSH 上传代码 → 远程 nohup 运行 |
| `docker` | `services/docker_executor.py` | 直连 Docker API，任务镜像构建后运行容器 |
| `agent` | `services/agent_service.py` | 写入停止标记，agent 领取执行并回报 |

## 任务状态机

```text
pending → running → success
                  → failed
                  → timeout
                  → cancelled（手动停止）
running ↔ paused（仅本地模式）
```

任务字段（`task_instance`）：`process_id / deploy_mode / container_id / workspace /
started_at / finished_at / duration / pages_crawled / items_scraped / errors_count /
error_message / log_url`。

## 各执行器流程

### 本地（LocalExecutor）

1. 根据代码目录与入口文件构建命令（优先 crawlo 命令，其次 run.py，最后直接 python）
2. subprocess 启动，stdout 实时写入 `uploads/_task_logs/task_{id}.log`
3. 监控线程等待退出 → 解析指标 → 更新任务终态 → 回写爬虫统计
4. 支持 pause/resume（SIGSTOP/SIGCONT）

### SSH（SshExecutor）

1. SSH 连接（密码或私钥）→ 检查远程 Python → 建 workspace → 上传代码 → 装依赖
2. `nohup python run.py` 后台启动，记录远程 PID
3. 每 5 秒 `kill -0` 轮询存活，结束按日志关键字判断成功/失败
4. 日志/指标回写数据库

### Docker（DockerExecutor）

1. 连接节点 Docker API（`tcp://host:port` 或 `docker_host` 覆盖）
2. 构建任务镜像，**项目 Dockerfile 优先，缺失时回退内置模板**（见下文"构建策略"）
3. 创建容器（入口文件优先，否则尊重镜像 ENTRYPOINT/CMD）
4. 监控到 exited → 解析日志指标 → 回写 → 清理容器（镜像保留复用）

#### Docker 节点 vs 项目 Dockerfile

两者职责完全不同，可以理解为：

- **Docker 节点 = "在哪里跑"**：一个 Docker daemon 的连接端点（`tcp://host:2375`
  或本地 `unix:///var/run/docker.sock`），只提供运行环境，不关心跑什么。
- **项目 Dockerfile = "跑什么"**：定义任务镜像的内容（基础镜像、依赖、启动命令），
  由爬虫代码目录里的 `Dockerfile` 提供。

一个 Docker 节点可以被任意多个项目复用；同一个项目也可以部署到多个 Docker 节点。
节点不感知项目内容，项目不依赖节点配置。

#### 镜像构建策略（项目 Dockerfile 优先）

执行时按以下顺序解析：

1. **项目 Dockerfile 存在**（代码目录下 `Dockerfile` 或 `dockerfile`）：
   - 以项目 Dockerfile 作为构建定义（`FROM / COPY / RUN / ENTRYPOINT / CMD` 全部由项目决定）
   - 代码目录作为构建上下文整体传入
   - 构建失败时回退到内置模板，避免项目 Dockerfile 写错导致任务不可运行
2. **无项目 Dockerfile**（回退内置模板）：
   - 确保基础镜像 `crawlopilot/base:{CRAWLO_VERSION}` 存在（本地 wheel 构建，缺失时自动构建）
   - 生成 `FROM base + WORKDIR /app + COPY . /app + 安装 requirements.txt` 的模板

#### 镜像缓存

任务镜像 tag 为 `crawlo-project-{project_id}-{内容摘要前16位}`：

- 内容摘要是代码 + Dockerfile（或基础镜像 tag）的 md5，代码不变则 tag 不变
- 节点上已存在该 tag 时跳过构建，秒级复用（同一项目连续运行不需要重复 `pip install`）
- 代码或 requirements 变化 → 摘要变化 → 自动构建新镜像，旧镜像保留用于回滚

#### 启动命令

1. 爬虫配置了 `entry_file` → 精确执行 `python <entry_file>`（覆盖镜像默认启动）
2. 未配置 `entry_file` 且使用项目 Dockerfile → 不覆盖，尊重镜像 ENTRYPOINT/CMD
3. 未配置 `entry_file` 且使用内置模板 → 默认 `python run.py`

> 注意：使用项目 Dockerfile 时，镜像必须自带运行所需依赖与启动逻辑；
> 内置模板保证"零 Dockerfile 项目"开箱即用（自动装 requirements.txt）。

### Agent（AgentTaskService + 节点程序）

1. `run_spider` 创建 PENDING 任务，agent 轮询领取（`/nodes/agent/tasks`）
2. agent 下载代码包（`/nodes/agent/tasks/{id}/code`）→ 本地执行
3. 日志实时上报（`/nodes/agent/tasks/{id}/logs`），终态回报（`/report`）
4. 停止 = 控制端写入 `stop_requested` 标记，agent 轮询到后终止进程

详见 [节点管理](05-nodes.md) 与 [Agent 使用说明](../../agent/README.md)。

## 指标解析

从日志正则提取 `pages / items / errors`，兼容：

- 测试格式：`Crawled 5 pages, 20 items`
- crawlo 1.6：`'item_successful_count': 42`
- crawlo 1.7：`'crawlo:item_successful_count': 42`

## 任务完成后

无论哪种执行方式，任务终态都会：

1. 更新任务状态/时长/指标
2. 回写爬虫 `last_run_status / last_run_at / success_count / error_count`
3. 日志落盘保留（容器/agent 清理后仍可查询）

## 存储与日志保留

- 代码、上传包、任务日志统一存放在 `settings.UPLOAD_DIR`（默认相对路径 `uploads`，
  即 backend 工作目录下的 `uploads/`；**生产必须配置绝对路径**，如 `/data/crawlopilot/uploads`）：

  ```text
  {UPLOAD_DIR}/
  ├── project_{id}/spider_{id}/   # 爬虫代码
  └── _task_logs/task_{id}.log    # 任务日志
  ```

- 多实例控制面需把 `UPLOAD_DIR` 指向共享存储（NFS/EFS/云盘），保证代码与日志一致。
- 任务日志默认保留 30 天（`TASK_LOG_RETENTION_DAYS=0` 关闭），后台每天清理一次。
