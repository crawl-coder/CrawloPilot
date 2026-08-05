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
2. 确保基础镜像 `crawlopilot/base:1.7.2`（本地 wheel 构建，缺失时自动构建）
3. 流式构建任务镜像（`FROM base + COPY 代码`，秒级）
4. 创建容器执行入口文件，监控到 exited → 解析日志指标 → 回写 → 清理容器

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
