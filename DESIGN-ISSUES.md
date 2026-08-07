# CrawloPilot 核心设计评估报告

> 评估时间：2026-08-07
> 评估范围：backend / agent / docs / tests
> 评估方法：代码审查（非运行时测试）

## 总体判断

设计哲学（控制面 / 执行面分离、执行器可插拔、本地优先）方向是对的，落地代码也能跑通主链路。但存在 **3 处高危死代码/安全漏洞**、**多处契约与文档不一致**、以及若干 **生产可用性硬伤**。下面分级列出。

---

## 一、严重缺陷（必须修，否则不能上生产）

### 1. `task_executor.py` 是死代码但被 lifespan 启动初始化

`backend/app/services/task_executor.py` 定义的 `TaskExecutor` 类与真正分发的四个执行器（local/ssh/docker/agent）完全脱节：

- 真实分发走 `backend/app/services/executor_registry.py` → `local_executor` / `ssh_executor` / `docker_executor` / `agent_service`
- 但 `backend/app/main.py` 仍然 `get_executor().initialize()`，每次启动都尝试连 Docker，失败时静默吞掉异常

更严重的是这个死代码本身是坏的：

- 引用 `settings.API_URL`、`settings.SPIDER_RUNNER_IMAGE`、`settings.API_SECRET_KEY` — 这些字段在 `backend/app/core/config.py` 里根本不存在，一旦真正调用 `execute_task` 立即 `AttributeError`
- `task_executor.py` 用了未创建过的 named volume `task-output-{task_id}`
- `_get_api_token` 返回 `settings.API_SECRET_KEY or "default-token"` — 硬编码默认值

**建议**：直接删除 `task_executor.py`，从 lifespan 移除 `get_executor()` 调用。

### 2. `SECRET_KEY` 默认值 + JWT/凭据加密共用一个密钥

`backend/app/core/config.py`：

```python
SECRET_KEY: str = "your-secret-key-change-in-production"
```

- 默认值就在源码里，生产忘改 = JWT 任何人可伪造 + 凭据 Fernet 加密形同虚设
- `backend/app/core/crypto.py` 用 `sha256(SECRET_KEY)` 派生 Fernet 密钥；`backend/app/core/security.py` 用同一个 `SECRET_KEY` 做 JWT 签名 — 两个安全职责共用一个密钥，违反密钥分离
- crypto.py 注释明确说"更换 SECRET_KEY 会导致历史密文无法解密" — 没有 rotation 路径

**建议**：启动时检测默认值就拒绝启动；JWT 与凭据加密拆成两个密钥（`JWT_SECRET_KEY` / `CREDENTIAL_ENCRYPTION_KEY`）。

### 3. Agent 鉴权 token 暴露在 URL query string

`agent/crawlo_agent.py`：

```python
res = self._request(
    "GET",
    f"/api/v1/nodes/agent/tasks?node_id={self.node_id}&token={self.token}",
)
```

`backend/app/api/v1/agent.py` 也确认接收方就这样取 token：

```python
async def agent_get_tasks(
    node_id: int,
    token: str,  # 直接从 query 参数取
```

- token 会出现在 nginx access log、反向代理日志、TCP 抓包里
- agent token 是长期凭证（无过期机制），泄漏后可冒充节点领取任务、上传恶意代码、回报假状态
- 同样的问题在 `/tasks/{id}/code`、`/tasks/{id}/status`、`/tasks/{id}/logs`、`/tasks/{id}/report` 全部存在

**建议**：改用 `Authorization: Bearer <token>` header；引入 token 过期 + 刷新。

### 4. tar 解包路径穿越漏洞（CVE-2007-4559 类）

`agent/crawlo_agent.py`：

```python
with tarfile.open(code_archive, "r:gz") as tar:
    try:
        tar.extractall(workspace, filter="data")
    except TypeError:
        # Python < 3.12 无 filter 参数
        tar.extractall(workspace)
```

- 项目声明支持 Python 3.10+，在 3.10/3.11 上 fallback 到无 filter 的 `extractall`
- 代码包是用户上传的，恶意 tar 可写到 `/etc/cron.d/`、`~/.ssh/authorized_keys` 等任意位置 → 服务器被接管
- 这是 Python 安全公告里反复警告的反模式

**建议**：所有 Python 版本都手动校验 `tar.getmembers()` 的 path 不含 `..` 且不是绝对路径。

### 5. SSH executor 的命令注入 + 自动信任主机 key

`backend/app/services/ssh_executor.py`：

```python
self._client.set_missing_host_key_policy(AutoAddPolicy())
```

自动信任任何未知主机 → 中间人攻击可窃取凭据/篡改命令。

```python
run_cmd = (
    f"cd {self.workspace} && "
    f"setsid nohup bash -c '{start_cmd} > task.log 2>&1; echo $? > exit.code' "
    f"</dev/null >/dev/null 2>&1 & echo $!"
)
```

`start_cmd` 含用户可控的 `entry_file` / `spider_name`，可注入 `;` `&&` 等 shell 元字符。

此外：

- `mkdir -p {remote_dir}`、`rm -rf {self.workspace}`、`echo {pid} > {workspace}/spider.pid` 全是字符串拼接
- `_install_dependencies` 在远程服务器用系统 Python `pip install -r requirements.txt`，污染节点环境

**建议**：用 `shlex.quote` 包裹所有路径；首次记录 host key 后续严格校验；远程用 venv 隔离依赖。

---

## 二、设计层面缺陷（影响可维护性 / 扩展性）

### 6. 执行器契约只是口头约定，没有抽象基类

`docs/design-philosophy.md` 宣称"四个执行器实现同一套契约 `execute_task / get_task_status / get_task_logs / stop_task`"，但实际：

| 执行器 | execute_task | get_task_status | get_task_logs | stop_task | pause/resume |
|---|---|---|---|---|---|
| LocalExecutor | async | sync | sync | async | 实现 |
| SshExecutor | async | sync | sync | async | **未实现** |
| DockerExecutor | async | sync | sync | async | **未实现** |
| AgentTaskService | **未实现**（pull 模式） | sync | sync | async | **未实现** |

- 没有 Protocol/ABC，新增执行器时编译期检查不到契约违反
- `pause/resume` 只有 LocalExecutor 实现，`backend/app/api/v1/websocket.py` 只能在路由层硬编码 `if deploy_mode in ("ssh", "docker", "agent"): 拒绝`
- 4 个执行器的 `_update_spider_stats` / `_update_task_completion` / `_delayed_cleanup` 几乎完全复制粘贴

**建议**：定义 `Executor` Protocol + 抽出 `TaskUpdater` mixin 处理 DB 写入。

### 7. 配置硬编码开发者本地路径

`backend/app/services/docker_executor.py`：

```python
CRAWLO_WHEEL_PATH = os.environ.get(
    "CRAWLO_WHEEL_PATH",
    "/Users/oscar/projects/Crawlo/dist/crawlo-1.7.2-py3-none-any.whl",
)
```

部署到任何其他机器默认失效。虽然有 fallback，但默认行为是错的。

**建议**：默认值改 `None`，强制走 pip 安装或显式配置。

### 8. config.py 默认值与 README 不一致

- `backend/app/core/config.py` `MYSQL_HOST: str = "mysql"`（docker-compose 服务名）
- `README.md` 写的是 `127.0.0.1`
- 本地开发如果没 `.env`，连不上数据库
- `DATABASE_TYPE` 默认 mysql 但代码里 sqlite 路径还在，是死分支

### 9. Agent 模式用轮询而非推送

设计哲学说"agent 反向连接控制端"，但实际是"反向 HTTP 轮询"：每 5 秒一次 `GET /tasks`。

- 节点空载时也在不停发起 HTTP 请求
- 多 agent 同时轮询会到 DB，规模化时 DB 压力线性增长
- 没有真正建立长连接（与设计哲学描述不符）

**建议**：长轮询（hold 30s）或 SSE 推送。

### 10. 任务状态机字段语义不一致

- `backend/app/models/__init__.py` `deploy_mode` 注释写 `local / docker / ssh`，漏了 `agent`，但实际代码用了
- `backend/app/services/task_service.py` 用字符串比较 `spider.status == "disabled"`，而不是 `SpiderStatus.DISABLED`
- `deploy_mode` 应该是 Enum，现在是 String，没有约束

---

## 三、运维与可观测性缺陷

### 11. 数据库迁移历史混乱

`backend/alembic/versions/` 下 16 个迁移，问题：

- 两个"创建 spider 表"：`4a8c26e16402_create_spider_table.py` 和 `b6985578c953_add_spider_table.py`
- merge migration `c4aabb19606c_merge_*.py` 表示有并行分支
- `s2c3h4e5d6u7_unify_schedule_migration.py` 名字暗示重写过 schedule
- 项目根散落 `add_missing_columns.py` / `migrate_node_credentials.py` / `_fix_db.py` / `add_sample_data.py` — 迁移之外多次手工修补

**建议**：清查能否从空库一次性 `alembic upgrade head`；归档手工 fix 脚本。

### 12. 状态更新存在竞态（应用层保护而非 DB 层）

DockerExecutor 注释明确写了"先标记取消再移除容器：监控线程可能正并发 poll" — 设计者知道有竞态，用"终态保护" `if task.status in terminal: return` 解决。

但这是应用层检查，仍有 TOCTOU 窗口。`_update_task_completion` 在 4 个执行器里各实现一份，逻辑重复且行为可能有细微差异。

**建议**：用 `UPDATE task_instance SET status=... WHERE id=... AND status NOT IN (...)` 让 DB 保证原子性。

### 13. APScheduler 多实例不安全

`backend/app/services/scheduler_service.py` 用 `BackgroundScheduler`（进程内），多实例部署时同一调度会被多个进程同时触发。设计文档说"主备切换（数据库行锁，按需选型）"但未实现。

唯一索引兜底了幂等，但每次触发都会走一遍 `create_and_run_task` 才撞唯一约束，浪费资源。

**建议**：生产明确单实例；多实例用 APScheduler 的 SQLAlchemyJobStore + 锁，或把调度拆成独立服务。

### 14. WebSocket / Prometheus endpoint 鉴权弱

- `backend/app/api/v1/websocket.py` token 从 query 参数取（浏览器 WS 限制，常见做法但 token 会进 access log）
- `backend/app/main.py` `/metrics` 完全无鉴权，暴露请求量/错误率

---

## 四、次要问题

- **LocalExecutor 暂停用 SIGSTOP**：crawlo 框架可能 spawn 子线程/协程，SIGSTOP 只暂停主进程，暂停期间 stdout 读取线程阻塞在 readline 上
- **容器名 `task-{task_id[:8]}` 冲突**：task_id 自增 int，旧容器未清理时创建新容器会失败
- **错误处理混乱**：`get_task_logs` 失败返回字符串 `"获取日志失败: ..."`，调用方难以区分真实日志和错误
- **资源限制只在 docker 模式生效**：`backend/app/services/task_service.py` `is_docker = bool(node and node.connect_type == "docker")`，local/ssh/agent 模式无任何资源限制
- **`_dispatch_agent` 多余的状态重置**：task 创建时已是 PENDING，又改回 PENDING 一次

---

## 五、值得肯定的设计

- 控制面/执行面分离的分层是对的，executor_registry 集中分发避免了四处 if/elif
- "项目 Dockerfile 优先 + 缺失回退内置模板 + 镜像按内容摘要缓存" 是合理的 Docker 构建策略
- 终态保护（`task.status in terminal: return`）方向正确，只是实现层不够原子
- 任务调度幂等用 MySQL 唯一索引兜底，是务实的方案
- Agent 用纯标准库实现，部署门槛低
- 文档与代码的"已实现/未实现"导流做得不错

---

## 修复优先级建议

| 优先级 | 项 | 工作量 |
|---|---|---|
| P0 | #1 删除 task_executor.py 死代码 | 0.5h |
| P0 | #2 SECRET_KEY 拆分 + 启动校验 | 1h |
| P0 | #3 Agent token 改 header | 2h |
| P0 | #4 tar 路径穿越修复 | 1h |
| P0 | #5 SSH 命令注入 + host key | 4h |
| P1 | #6 定义 Executor Protocol | 4h |
| P1 | #9 Agent 改长轮询/推送 | 8h |
| P1 | #12 状态更新改 DB 条件更新 | 4h |
| P2 | #11 清理迁移历史 | 4h |
| P2 | #13 多实例调度器选型 | 8h |
