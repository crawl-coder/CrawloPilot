# CrawloPilot V2 设计方案

> 版本：V2.0（基于 Crawlo 框架认知修正版）
> 日期：2026-08-07
> 作者：架构评审
> 状态：待评审
> 关联文档：[DESIGN-ISSUES.md](../DESIGN-ISSUES.md)、[docs/design-philosophy.md](design-philosophy.md)
> 关键修正：基于对 Crawlo 框架分布式能力的认知，重新界定 CrawloPilot 与 Crawlo 的职责边界

---

## 一、定位与愿景

### 1.1 V2 定位

**面向 Crawlo 框架的分布式爬虫编排平台**（Orchestration Platform for Crawlo Framework）。

V1 自称"Crawlo 爬虫框架的管理部署平台"，但实际代码支持 6 种爬虫类型（Crawlo/Scrapy/Selenium/Playwright/Requests/Custom），定位与实现脱节。

V2 明确：**Crawlo 是默认推荐引擎**，其他框架作为兼容执行目标保留但不再投入。平台的核心价值是让 Crawlo 的分布式能力在多爬虫、多节点场景下被有效编排。

### 1.2 关键认知：两层分布式

Crawlo 框架本身已具备完整的分布式能力：

| Crawlo 已实现 | 说明 |
|---|---|
| Redis Stream Queue | 请求级分发，XREADGROUP 消费 |
| Consumer Group + XACK | 请求级 ACK，崩溃任务不丢 |
| XAUTOCLAIM | 120s 内回收崩溃 Worker 的 pending |
| FailoverManager | 两阶段故障检测（90s 超时 + 30s 确认） |
| WorkerRegistry + Heartbeat | Worker 注册与心跳（15s ±20% jitter） |
| DistributedLock | 基于 SET NX PX + Lua 防误删 |
| Leader 选举 | 协调退出时的临时 Leader（SETNX） |
| 分布式限速 | Lua 令牌桶，按域名 |
| 动态配置 | Pub/Sub + Redis Key 双通道 |
| 死信队列 | retry_count 超限转入 stream:failed |
| 种子去重 | SETNX 互斥种子生成器 |
| 优雅退出 | drain + STATUS_STOPPING 豁免 |

**CrawloPilot 的分布式是另一层**：

| CrawloPilot 负责 | Crawlo 负责 |
|---|---|
| M 个爬虫项目部署到 N 个节点 | 单个爬虫在 N 个 Worker 上分发请求 |
| 代码版本管理、调度、凭据 | 请求级 Stream/ACK/Failover |
| 任务级状态机（running/done/failed） | 请求级状态机（pending/processing/acked） |
| 节点级故障检测 + 告警 | Worker 级故障检测 + 任务回收 |

**V2 核心原则**：CrawloPilot 不重复实现请求级 Stream/ACK/Failover。在需要深爬场景下，CrawloPilot 通过 `CrawloDistributedAdapter` 调度 Crawlo 的 distributed 模式。

### 1.3 目标用户

5-20 人中型爬虫团队，典型场景：

- 同时维护 20-200 个爬虫项目
- 部署在 3-10 台节点
- 需要告警、代理池、日志聚合、审计
- 需要多成员协作 + 操作可追溯
- 部分爬虫需要深爬（单 spider 数十万页以上）

### 1.4 V2 核心目标

| 目标 | V1 现状 | V2 目标 |
|---|---|---|
| 编排与执行边界 | 执行器越层直写 DB | TaskStateStore 收敛任务级状态 |
| 多实例部署 | 单实例硬约束 | 水平扩展 |
| 执行器契约 | 口头约定 | Protocol + ABC |
| Agent 通信 | HTTP 5s 轮询 | HTTP 长轮询（30s hold） |
| Crawlo 分布式调度 | 不支持 | CrawloDistributedAdapter |
| 可观测性 | 无 | 告警 + 日志聚合 + 指标 |
| 安全 | 单密钥 + token in URL | 双密钥 + Bearer + 审计 |
| 生态扩展 | 无 | 代理池 + Webhook |

### 1.5 非目标

V2 **不做**以下事项：

- 请求级 ACK / Stream / Failover（这是 Crawlo 的职责）
- 多租户 / 工作空间隔离（V3）
- 数据质量监控（V1 已取消，V2 不恢复）
- 可视化爬虫编排 DAG 拖拽（V3）
- 爬虫代码在线 IDE

---

## 二、与 V1 的差异对比

### 2.1 架构层面

| 维度 | V1 | V2 |
|---|---|---|
| 状态写入 | 执行器直写 DB + 内存 active_tasks | 经 TaskStateStore（任务级） |
| 调度器 | APScheduler 进程内 | 独立服务 + DB advisory lock |
| Agent 通信 | HTTP 轮询 5s | HTTP 长轮询 30s（不引入 MQ） |
| 日志存储 | 文件 + 容器卷 | Loki 聚合 |
| 告警 | 无 | AlertManager + Webhook |
| 代理池 | 无 | ProxyPool 微服务 |
| 密钥管理 | 单 SECRET_KEY 共用 | JWT / 凭据加密分离 |
| 审计 | 无 | AuditLog 模块 |
| Crawlo 分布式 | 不支持 | CrawloDistributedAdapter |

### 2.2 与 Crawlo 的职责边界（新增）

V2 明确以下分工，避免重复造轮子：

| 职责 | CrawloPilot 做 | Crawlo 做 |
|---|---|---|
| 爬虫代码版本管理 | ✓ Git 工作流 | ✗ |
| 调度（cron/interval） | ✓ | ✗ |
| 多爬虫项目管理 | ✓ | ✗ |
| 节点资源管理 | ✓ 节点池 | ✗ |
| 凭据管理 | ✓ 加密 | ✗ |
| 任务级状态机 | ✓ spider running/done | ✗ |
| **请求级分发** | ✗ | ✓ Stream Queue |
| **请求级 ACK** | ✗ | ✓ XACK/NACK |
| **请求级去重** | ✗ | ✓ Redis Set |
| **Worker 故障检测** | ✗ | ✓ Heartbeat + Failover |
| **请求级重试** | ✗ | ✓ retry_count + 死信 |
| **分布式限速** | ✗ | ✓ Lua 令牌桶 |
| **协调退出** | ✗ | ✓ Leader 选举 |
| 节点故障告警 | ✓ AlertManager | ✗ |
| 日志聚合 | ✓ Loki | ✗ |
| 代理池 | ✓ ProxyPool | ✗ |

### 2.3 兼容性策略

V2 采用**演进式重构**，不重写：

- API 路径保持 `/api/v1/*`
- 数据库 schema 增量迁移
- V1 的 4 个执行器全部保留，逐步适配 Protocol
- V1 Agent 可连接 V2 控制面（降级 HTTP 轮询）
- V1 standalone 模式任务完全兼容

---

## 三、三种部署模式（核心）

V2 根据爬虫规模与可用节点数，提供三种部署模式。**这是 V2 最重要的设计决策**，让用户按需选择 Crawlo 的运行模式。

### 3.1 模式 A：项目隔离（standalone）

**适用**：80% 场景，50+ 独立小爬虫，每个 10-1000 页

```
CrawloPilot → 调度 Spider A 到 Node 1 (crawlo run spider_a)
CrawloPilot → 调度 Spider B 到 Node 2 (crawlo run spider_b)
每个 spider 用 RUN_MODE=standalone，不依赖 Redis
```

- 节点之间不共享 Redis
- 节点故障 = 任务失败，CrawloPilot 标记失败，下次调度重试
- 简单可靠，无外部依赖
- 不支持单 spider 跨机扩展

### 3.2 模式 B：单机深爬（single_node_distributed）

**适用**：15% 场景，单个 spider 数万到数十万页，榨干单机性能

```
CrawloPilot → 调度深爬任务到 Node 1
Node 1 启动 N 个 Crawlo Worker 进程（distributed 模式）
Worker 共享本机 Redis（或同机房 Redis）
```

- 一个节点跑多个 Worker，Consumer Group 自动负载均衡
- Worker 崩溃由 Crawlo FailoverManager 回收（120s XAUTOCLAIM）
- 请求级 ACK，不丢数据
- 不跨机扩展

### 3.3 模式 C：多机联合深爬（multi_node_distributed）

**适用**：5% 场景，超大规模爬取（50 万+ 页），需要跨机扩展 + 高可用

```
CrawloPilot → 调度深爬任务 → 同时部署到 Node 1/2/3
所有节点共享同一个 Redis（Sentinel 高可用）
每个节点跑 1 个 Crawlo Worker，distributed 模式
Crawlo 的 Consumer Group 自动负载均衡
```

- 节点崩溃 → Crawlo FailoverManager 90s 检测 → XAUTOCLAIM 回收 pending
- 请求级不丢数据（ACK 至少一次语义）
- CrawloPilot 层面看到任务仍在运行（其他节点还活着）
- 需要 Redis HA（Sentinel 或 Cluster）

### 3.4 模式选择决策树

```
单 spider 总页数 < 1000？
  └─ 是 → 模式 A (standalone)
  └─ 否 → 单机 N 核够用？
            └─ 是 → 模式 B (single_node_distributed)
            └─ 否 → 模式 C (multi_node_distributed)
```

### 3.5 模式在数据模型中的表达

新增字段 `distribution_mode`：

```sql
ALTER TABLE task_instance ADD COLUMN distribution_mode
    ENUM('standalone', 'single_node_distributed', 'multi_node_distributed')
    DEFAULT 'standalone';

ALTER TABLE task_instance ADD COLUMN shared_redis_url VARCHAR(256)
    COMMENT '模式 C 共享 Redis 地址（Sentinel 格式：redis+sentinel://host:26379/0）';

ALTER TABLE task_instance ADD COLUMN worker_count INT DEFAULT 1
    COMMENT '模式 B/C 每节点启动的 Worker 进程数';
```

---

## 四、整体架构

### 4.1 分层视图

```
┌─────────────────────────────────────────────────────┐
│  用户 / Agent / Webhook                             │
└─────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────────────────────────────┐
│ 控制面 Control Plane (CrawloPilot)                  │
│   ┌─────────┐ ┌─────────┐ ┌────────────────────┐    │
│   │ API网关 │ │ 调度器  │ │ TaskStateStore     │    │
│   └─────────┘ └─────────┘ │ (任务级状态)        │    │
│                            └────────────────────┘    │
│   ┌─────────────────────────────────────────────┐   │
│   │ CrawloDistributedAdapter (新增)              │   │
│   │ 选择 standalone / single_node / multi_node  │   │
│   └─────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────────┘
                       │ 调度任务到节点
┌──────────────────────┴───────────────────────────────┐
│ 执行面 Execution Plane                              │
│   Executor Protocol:                                │
│   ┌──────────┬──────────┬──────────┬─────────────┐ │
│   │ Local    │ SSH      │ Docker   │ Agent       │ │
│   │ (4模式) │ (4模式) │ (4模式) │ (4模式)     │ │
│   └──────────┴──────────┴──────────┴─────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ 启动 Crawlo
┌──────────────────────┴───────────────────────────────┐
│ Crawlo 框架（已有能力，不重做）                      │
│   standalone: 内存队列                              │
│   distributed: Redis Stream + ACK + Failover       │
└──────────────────────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────┐
│ 数据面 / 可观测 / 生态                              │
│   MySQL · Loki · AlertManager · ProxyPool           │
└──────────────────────────────────────────────────────┘
```

### 4.2 核心改进点

1. **TaskStateStore**：任务级状态变更的唯一入口（不碰请求级）
2. **Executor Protocol**：抽象基类 + 编译期契约检查
3. **CrawloDistributedAdapter**：把任务转换为 Crawlo distributed 部署
4. **AlertManager**：规则引擎 + 多通道告警
5. **ProxyPool**：独立微服务
6. **LogAggregator**：Loki + Promtail
7. **AuditLog**：操作审计

**取消的 V1 设计**：
- ~~MessageBus（Redis Streams 替代 HTTP 轮询）~~ —— Crawlo 已有 Stream，不重复
- Agent 保持 HTTP 长轮询（hold 30s），简单可靠

---

## 五、核心模块设计

### 5.1 TaskStateStore（任务级状态中间层）

**职责**：任务（spider 实例）整体状态变更的唯一入口。**不处理请求级状态**。

**接口**：

```python
class TaskStateStore(Protocol):
    async def transition(
        self,
        task_id: int,
        from_statuses: list[TaskStatus],
        to_status: TaskStatus,
        payload: dict | None = None,
    ) -> bool:
        """原子状态转换。仅当当前状态在 from_statuses 中时才转换。
        返回 True 表示转换成功，False 表示状态已变。"""

    async def heartbeat(self, task_id: int, metrics: dict) -> None:
        """执行器心跳上报。Redis TTL 30s，过期由 reaper 标记任务 failed。"""

    async def append_log(self, task_id: int, line: str, level: str) -> None:
        """日志写入 Loki + Redis 缓冲。"""

    async def update_stats(self, task_id: int, stats: dict) -> None:
        """更新爬虫统计（items_count / pages_count 等，来自 Crawlo ProgressAggregator）。"""
```

**实现要点**：

- DB 层：`UPDATE task_instance SET status=:to WHERE id=:id AND status IN (:from)` 原子性
- 心跳：Redis `task:heartbeat:{task_id}` TTL 30s
- 多实例：状态机无共享，多个控制面实例可同时写不冲突
- 审计：每次 transition 记录到 AuditLog

**与 Crawlo 的协作**：

- Crawlo 的 `ProgressAggregator` 把统计写入 Redis `progress:stats` HASH
- CrawloPilot 的 `TaskStateStore.update_stats` 从 Redis 读取并同步到 MySQL
- Crawlo 的 `control:state` 变为 `shutdown` 时，CrawloPilot 监听到后调用 `transition(task_id, [...], COMPLETED)`

### 5.2 Executor Protocol（执行器契约）

```python
class Executor(Protocol):
    """所有执行器必须实现的契约。编译期检查。"""

    @property
    def mode(self) -> DeployMode: ...

    async def execute_task(self, task: TaskInstance) -> None:
        """启动任务（异步，立即返回）。状态变更走 TaskStateStore。"""

    def get_task_status(self, task_id: int) -> TaskStatus:
        """同步查询任务当前状态（从 TaskStateStore 读）。"""

    def get_task_logs(self, task_id: int, tail: int = 200) -> list[LogEntry]:
        """获取日志。统一返回 LogEntry 列表。"""

    async def stop_task(self, task_id: int, force: bool = False) -> None:
        """停止任务。force=True 时强制 kill。"""


class PausableExecutor(Executor, Protocol):
    """可选：支持暂停/恢复的执行器。"""

    async def pause_task(self, task_id: int) -> None: ...
    async def resume_task(self, task_id: int) -> None: ...
```

**适配情况**：

| 执行器 | execute | status | logs | stop | pause |
|---|---|---|---|---|---|
| LocalExecutor | ✓ | ✓ | ✓ | ✓ | ✓（进程组 SIGSTOP） |
| SshExecutor | ✓ | ✓ | ✓ | ✓ | ✗ |
| DockerExecutor | ✓ | ✓ | ✓ | ✓ | ✗ |
| AgentExecutor | ✓（push 模式） | ✓ | ✓ | ✓ | ✗ |

### 5.3 CrawloDistributedAdapter（新增 · 核心模块）

**职责**：把 CrawloPilot 的任务转换为 Crawlo distributed 部署，对接三种模式。

```python
class CrawloDistributedAdapter:
    """把 CrawloPilot 任务转换为 Crawlo distributed 部署。
    
    不重复实现 Crawlo 的 Stream/ACK/Failover，
    只负责选择模式、生成启动脚本、监听完成。
    """

    async def deploy(
        self,
        task: TaskInstance,
        nodes: list[Node],
    ) -> None:
        """根据 task.distribution_mode 选择部署方式。"""
        mode = task.distribution_mode
        
        if mode == "standalone":
            # 模式 A：每个节点独立 spider，不共享 Redis
            await self._deploy_standalone(task, nodes)
        
        elif mode == "single_node_distributed":
            # 模式 B：单节点 N Worker，本机 Redis
            await self._deploy_single_node_distributed(task, nodes[0])
        
        elif mode == "multi_node_distributed":
            # 模式 C：多节点共享 Redis
            await self._deploy_multi_node_distributed(task, nodes)
    
    async def _deploy_standalone(self, task, nodes):
        """模式 A：标准 standalone 部署。
        
        每个 Agent 收到任务后执行：
            crawlo run spider_name
        不需要 Redis。节点故障 = 任务失败。
        """
        for node in nodes[:1]:  # standalone 只调度到一个节点
            await self.agent_service.dispatch(
                node_id=node.id,
                entry_file=task.entry_file or "crawlo run",
                env={
                    "RUN_MODE": "standalone",
                    "SPIDER_NAME": task.spider_name,
                },
            )
    
    async def _deploy_single_node_distributed(self, task, node):
        """模式 B：单节点多 Worker，本机 Redis。
        
        Agent 收到任务后执行启动脚本，启动 N 个 Worker：
            for i in range(N): crawlo run spider_name
        
        所有 Worker 共享本机 Redis，Crawlo Consumer Group 自动负载均衡。
        """
        worker_script = self._generate_worker_script(
            spider_name=task.spider_name,
            worker_count=task.worker_count or 4,
            redis_url="redis://localhost:6379/0",
        )
        await self.agent_service.dispatch(
            node_id=node.id,
            entry_file=worker_script,
            env={
                "RUN_MODE": "distributed",
                "QUEUE_TYPE": "redis_stream",
                "REDIS_URL": "redis://localhost:6379/0",
                "SPIDER_NAME": task.spider_name,
            },
        )
        # 订阅 Crawlo 的 control:state 变化
        await self._subscribe_crawlo_completion(task.id, "redis://localhost:6379/0")
    
    async def _deploy_multi_node_distributed(self, task, nodes):
        """模式 C：多节点共享 Redis。
        
        所有 Agent 收到相同任务，连接同一个 Redis（Sentinel HA）。
        Crawlo 的 Consumer Group 自动跨节点负载均衡。
        """
        redis_url = task.shared_redis_url
        for node in nodes:
            await self.agent_service.dispatch(
                node_id=node.id,
                entry_file="crawlo run",
                env={
                    "RUN_MODE": "distributed",
                    "QUEUE_TYPE": "redis_stream",
                    "REDIS_URL": redis_url,
                    "SPIDER_NAME": task.spider_name,
                    "PROJECT_NAME": task.project_name,
                },
            )
        # 订阅 Crawlo 协调退出信号
        await self._subscribe_crawlo_completion(task.id, redis_url)
    
    async def _subscribe_crawlo_completion(self, task_id: int, redis_url: str):
        """监听 Crawlo 的 control:state，任务完成时通知 TaskStateStore。
        
        Crawlo Leader Worker 检测到全部完成时，会：
            SET control:state = "shutdown" + PUBLISH channel:control "shutdown"
        
        本方法订阅该 Pub/Sub 频道，收到 shutdown 时调用 TaskStateStore.transition(COMPLETED)。
        """
        # 后台任务：订阅 channel:control
        # 收到 action=shutdown 时：
        #   await self.task_state_store.transition(task_id, [RUNNING], COMPLETED)
        pass
    
    def _generate_worker_script(self, spider_name, worker_count, redis_url):
        """生成启动脚本（启动 N 个 Worker 进程）。"""
        return f"""
import subprocess, sys, time
for i in range({worker_count}):
    subprocess.Popen([sys.executable, "-m", "crawlo", "run", "{spider_name}"])
    time.sleep(2)  # 间隔启动，避免心跳风暴
# 等待所有子进程
import os
os.wait()
"""
```

**关键设计点**：

1. **不重复造 Stream**：Crawlo 已经有 Redis Stream，CrawloPilot 只负责启动参数传递
2. **订阅完成信号**：通过 Crawlo 的 `control:state = "shutdown"` 感知任务完成
3. **节点故障处理**：
   - 模式 A：节点故障 = 任务失败，CrawloPilot 重试
   - 模式 B：Worker 故障由 Crawlo FailoverManager 处理，CrawloPilot 不感知
   - 模式 C：节点故障由 Crawlo XAUTOCLAIM 回收其 pending，CrawloPilot 看任务仍 running

### 5.4 AlertManager（告警引擎）

**规则模型**：

```python
class AlertRule(BaseModel):
    id: int
    name: str
    enabled: bool
    metric: str  # "task_failed_count" / "node_offline" / "spider_error_rate"
    operator: str
    threshold: float
    window_minutes: int
    channels: list[str]  # ["webhook", "feishu", "email"]
    cooldown_minutes: int
    spider_id: int | None
    node_id: int | None
```

**内置规则**：

| 规则 | 默认阈值 | 窗口 | 说明 |
|---|---|---|---|
| 任务失败 | 连续 3 次 | 1h | CrawloPilot 任务级 |
| 节点离线 | 心跳超 60s | 实时 | CrawloPilot 节点级 |
| 任务超时 | > 30 分钟 | 实时 | CrawloPilot 任务级 |
| 死信队列增长 | > 0 | 5min | 来自 Crawlo `stream:failed` |
| Worker 故障 | Worker 数下降 | 5min | 来自 Crawlo `registry:workers` |

**与 Crawlo 集成**：AlertManager 后台任务从 Crawlo 的 Redis 读取 `XLEN stream:failed`、`HLEN registry:workers`，作为指标来源。

### 5.5 ProxyPool（代理池服务）

**独立微服务**，与控制面解耦。

**核心接口**：

```
GET  /proxies/acquire?spider_id=X&count=1
POST /proxies/release
POST /proxies/report
GET  /proxies/stats
```

**与 Crawlo 集成**：

- Crawlo 通过 `PROXY_POOL_URL` 环境变量调用
- Crawlo 的 `ProxyMiddleware` 自动从 ProxyPool 获取代理
- 代理失败时 Crawlo 上报，ProxyPool 标记不可用

### 5.6 LogAggregator（日志聚合）

**V1 问题**：多节点部署后，日志散落各节点文件。

**V2 方案**：Loki + Promtail。

- 容器化：Docker Executor 直接 stdout，Promtail 采集 docker logs
- 本地部署：LocalExecutor 日志写文件，Promtail tail
- SSH 部署：节点部署 Promtail
- Agent 模式：Agent 上报日志走 HTTP，控制面写入 Loki

**查询接口**：

```
GET /api/v1/tasks/{task_id}/logs?tail=200&level=ERROR&since=1h
```

### 5.7 AuditLog（审计日志）

**记录范围**：所有写操作。

```python
class AuditLog(BaseModel):
    id: int
    user_id: int | None
    action: str  # "task.create" / "spider.update" / "credential.delete"
    resource_type: str
    resource_id: int
    before: dict | None
    after: dict | None
    ip: str
    user_agent: str
    created_at: datetime
```

**存储**：单独 `audit_logs` 表，按月分区，保留 1 年。

---

## 六、关键技术选型

| 模块 | 选型 | 理由 |
|---|---|---|
| 消息队列 | **不引入** | Crawlo 已用 Redis Stream；CrawloPilot 不需要 MQ |
| 调度器 | Celery Beat 独立服务 | 多实例安全（DB 锁） |
| 日志聚合 | Loki + Promtail | 比 ELK 轻 10 倍 |
| 指标 | Prometheus + Grafana | 行业标准 |
| 告警 | 自研 AlertManager | 业务规则复杂 |
| 代理池 | 独立 FastAPI 微服务 | 解耦 |
| 分布式锁 | Redis Redlock | 多实例调度器幂等 |
| Agent 通信 | HTTP 长轮询 | 简单可靠，hold 30s |

**未选型说明**：

- **Kafka/NATS**：Crawlo 已用 Redis Stream，CrawloPilot 不需要自己的 MQ
- **Temporal/Airflow**：太重，爬虫编排不需要复杂 DAG

---

## 七、数据模型变更

### 7.1 新增表

```sql
-- 审计日志
CREATE TABLE audit_logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32) NOT NULL,
    resource_id BIGINT NOT NULL,
    before_value JSON,
    after_value JSON,
    ip VARCHAR(45),
    user_agent VARCHAR(256),
    created_at DATETIME NOT NULL,
    INDEX idx_user_action (user_id, action, created_at),
    INDEX idx_resource (resource_type, resource_id, created_at)
) PARTITION BY RANGE (TO_DAYS(created_at));

-- 告警规则
CREATE TABLE alert_rules (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(128) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    metric VARCHAR(64) NOT NULL,
    operator VARCHAR(8) NOT NULL,
    threshold FLOAT NOT NULL,
    window_minutes INT NOT NULL,
    channels JSON NOT NULL,
    cooldown_minutes INT DEFAULT 30,
    spider_id BIGINT,
    node_id BIGINT,
    created_at DATETIME NOT NULL,
    updated_at DATETIME NOT NULL
);

-- 告警记录
CREATE TABLE alert_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    rule_id BIGINT NOT NULL,
    resource_type VARCHAR(32),
    resource_id BIGINT,
    message TEXT,
    fired_at DATETIME NOT NULL,
    resolved_at DATETIME,
    INDEX idx_rule_fired (rule_id, fired_at)
);

-- 代理池
CREATE TABLE proxies (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    url VARCHAR(256) NOT NULL,
    source VARCHAR(32) NOT NULL,
    region VARCHAR(32),
    is_available BOOLEAN DEFAULT TRUE,
    last_check_at DATETIME,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    avg_response_ms INT,
    created_at DATETIME NOT NULL
);
```

### 7.2 修改表

```sql
-- task_instance: deploy_mode 改为 ENUM
ALTER TABLE task_instance 
    MODIFY COLUMN deploy_mode 
    ENUM('local','ssh','docker','agent') NOT NULL;

-- task_instance: 新增 distribution_mode（核心）
ALTER TABLE task_instance 
    ADD COLUMN distribution_mode
    ENUM('standalone', 'single_node_distributed', 'multi_node_distributed')
    DEFAULT 'standalone';

-- task_instance: 新增 shared_redis_url（模式 C 用）
ALTER TABLE task_instance 
    ADD COLUMN shared_redis_url VARCHAR(256)
    COMMENT '模式 C 共享 Redis 地址';

-- task_instance: 新增 worker_count
ALTER TABLE task_instance 
    ADD COLUMN worker_count INT DEFAULT 1
    COMMENT '模式 B/C 每节点 Worker 进程数';

-- task_instance: 新增 heartbeat_at
ALTER TABLE task_instance 
    ADD COLUMN heartbeat_at DATETIME;

-- nodes: 新增 last_seen_at
ALTER TABLE nodes 
    ADD COLUMN last_seen_at DATETIME;
```

### 7.3 迁移策略

- 新增表：直接创建，不影响 V1
- 修改表：`deploy_mode` 改 ENUM 需先清理脏数据
- `distribution_mode` 默认 `standalone`，V1 任务自动兼容
- 提供 `alembic upgrade head` 一次性迁移脚本

---

## 八、API 变更

### 8.1 新增 API

```
# 告警
POST   /api/v1/alerts/rules
GET    /api/v1/alerts/rules
PUT    /api/v1/alerts/rules/{id}
DELETE /api/v1/alerts/rules/{id}
GET    /api/v1/alerts/events

# 代理池
GET    /api/v1/proxies
POST   /api/v1/proxies
DELETE /api/v1/proxies/{id}
GET    /api/v1/proxies/acquire
POST   /api/v1/proxies/release
GET    /api/v1/proxies/stats

# 审计
GET    /api/v1/audit-logs

# 任务创建增强
POST   /api/v1/tasks  # 新增 distribution_mode / shared_redis_url / worker_count 字段
```

### 8.2 修改 API

**Agent 鉴权统一改 Bearer**：

```diff
- GET /api/v1/nodes/agent/tasks?node_id=1&token=xxx
+ GET /api/v1/nodes/agent/tasks?node_id=1
+ Authorization: Bearer xxx
```

**Agent 长轮询**：

```diff
- GET /api/v1/nodes/agent/tasks  # 立即返回，5s 后再请求
+ GET /api/v1/nodes/agent/tasks?wait=30  # hold 30s，有任务立即返回
```

**日志查询增强**：

```diff
- GET /api/v1/tasks/{id}/logs
+ GET /api/v1/tasks/{id}/logs?tail=200&level=ERROR&since=1h
```

### 8.3 废弃 API

```
# V2 仍保留但标记 deprecated，V3 移除
GET /api/v1/nodes/agent/tasks?wait=0  # 立即返回模式（兼容 V1 Agent）
```

---

## 九、演进路线

### Phase 1：止血修复（2 周，无架构变更）

**目标**：让 V1 能安全上生产。

| 任务 | 工作量 | 优先级 |
|---|---|---|
| 删除 task_executor.py 死代码 | 0.5h | P0 |
| SECRET_KEY 拆分 + 启动校验 | 1h | P0 |
| Agent token 改 Bearer header | 2h | P0 |
| tar 路径穿越修复 | 1h | P0 |
| SSH 命令注入 + host key | 4h | P0 |
| CRAWLO_WHEEL_PATH 默认改 None | 0.5h | P0 |

**交付**：V1.1 安全版本。

### Phase 2：架构收敛（1-2 个月）

**目标**：解决状态散落 + 单实例约束 + Crawlo 分布式调度。

| 任务 | 工作量 | 依赖 |
|---|---|---|
| 引入 Redis 基础设施 | 2h | - |
| 实现 TaskStateStore | 16h | Redis |
| 定义 Executor Protocol + 适配 4 执行器 | 24h | TaskStateStore |
| **实现 CrawloDistributedAdapter** | 24h | TaskStateStore |
| Agent 改长轮询（hold 30s） | 8h | - |
| 调度器拆分 + DB 锁 | 16h | - |
| 状态更新改 DB 条件 UPDATE | 8h | TaskStateStore |
| 迁移历史清理 | 8h | - |

**交付**：V2.0，多实例可部署，支持三种 Crawlo 分布式模式。

### Phase 3：平台化（3-6 个月）

**目标**：补齐可观测与生态能力。

| 任务 | 工作量 | 优先级 |
|---|---|---|
| AlertManager + Webhook | 40h | P0 |
| Loki 日志聚合接入 | 24h | P0 |
| Prometheus 指标接入 | 16h | P0 |
| AuditLog 模块 | 24h | P1 |
| ProxyPool 微服务 | 40h | P1 |
| Grafana Dashboard 模板 | 8h | P2 |
| 飞书告警通道集成 | 8h | P2 |

**交付**：V2.1 完整平台。

---

## 十、三种模式实战示例

### 10.1 模式 A：项目隔离（典型用户）

**场景**：维护 50 个新闻爬虫，每个爬 100 页/天。

**配置**：
```json
POST /api/v1/tasks
{
    "spider_id": 123,
    "node_id": 1,
    "deploy_mode": "agent",
    "distribution_mode": "standalone",
    "schedule": "0 8 * * *"
}
```

**执行流程**：
1. CrawloPilot 调度器触发任务
2. Agent 收到任务，下载代码
3. Agent 执行 `crawlo run news_spider`
4. Crawlo standalone 模式运行，内存队列
5. 完成后 Agent 上报 `COMPLETED`
6. CrawloPilot TaskStateStore 更新状态

### 10.2 模式 B：单机深爬

**场景**：爬取电商全站 18 万商品页，单机 8 核。

**配置**：
```json
POST /api/v1/tasks
{
    "spider_id": 456,
    "node_id": 1,
    "deploy_mode": "agent",
    "distribution_mode": "single_node_distributed",
    "worker_count": 8,
    "schedule": "manual"
}
```

**执行流程**：
1. CrawloPilot 调度任务到 Node 1
2. Agent 收到任务，CrawloDistributedAdapter 生成启动脚本
3. Agent 执行脚本，启动 8 个 Crawlo Worker（distributed 模式）
4. 8 个 Worker 共享本机 Redis，Consumer Group 自动负载均衡
5. 单个 Worker 崩溃 → Crawlo FailoverManager 120s 回收其 pending
6. 全部完成 → Crawlo Leader 广播 shutdown → CrawloPilot 监听到 → 标记 COMPLETED

### 10.3 模式 C：多机联合深爬

**场景**：爬取 50 万页政府数据，3 台节点。

**配置**：
```json
POST /api/v1/tasks
{
    "spider_id": 789,
    "node_ids": [1, 2, 3],
    "deploy_mode": "agent",
    "distribution_mode": "multi_node_distributed",
    "shared_redis_url": "redis+sentinel://sentinel:26379/0",
    "worker_count": 4,
    "schedule": "manual"
}
```

**执行流程**：
1. CrawloPilot 调度任务到 Node 1/2/3
2. 3 个 Agent 同时收到任务
3. 每个 Agent 启动 4 个 Crawlo Worker，全部连接共享 Redis
4. 12 个 Worker 共享一个 Consumer Group，自动负载均衡
5. Node 2 崩溃 → Crawlo FailoverManager 90s 检测 → XAUTOCLAIM 回收 Node 2 的 pending 到 Node 1/3
6. CrawloPilot 通过 Redis 监控到 Worker 数从 12 降到 8，触发告警
7. 全部完成 → Crawlo Leader 广播 shutdown → CrawloPilot 标记 COMPLETED

---

## 十一、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Redis 单点故障（模式 B/C） | 中 | 高 | Sentinel 主从；Agent 降级 standalone |
| Crawlo 与 CrawloPilot 版本不匹配 | 中 | 中 | Adapter 版本协商；兼容性测试 |
| 调度器多实例触发 | 低 | 中 | DB advisory lock；唯一索引 |
| Loki 日志查询慢 | 低 | 中 | 索引 label 精简；保留期 30 天 |
| V1 升级 V2 数据迁移失败 | 中 | 高 | 全量备份 + 灰度升级 + 回滚脚本 |
| Agent 协议升级兼容性 | 中 | 中 | 版本协商；V1 Agent 仍可连接 |
| 代理池质量不稳 | 高 | 低 | 多源混合；健康检查；降级直连 |
| 共享 Redis 多 spider 资源竞争 | 中 | 中 | `{project}:{spider}` hash tag 隔离 |

---

## 十二、验收标准

### 12.1 功能验收

- [ ] 4 个执行器全部适配 Executor Protocol
- [ ] TaskStateStore 成为任务级状态唯一入口
- [ ] **三种 distribution_mode 全部可用**
  - [ ] 模式 A：standalone 任务正常调度
  - [ ] 模式 B：单节点 N Worker，任务完成正确感知
  - [ ] 模式 C：多节点共享 Redis，节点故障任务不丢
- [ ] Agent 长轮询（hold 30s）正常工作
- [ ] 多实例部署（2 个控制面）任务不重复执行
- [ ] AlertManager 5 条内置规则触发验证通过
- [ ] Loki 日志查询响应 < 2s
- [ ] AuditLog 记录所有写操作
- [ ] ProxyPool 可获取/释放代理

### 12.2 非功能验收

- [ ] 安全：无默认密钥、无 token in URL、无命令注入、无路径穿越
- [ ] 性能：单实例支持 100 并发任务、50 个 Agent 在线
- [ ] 可用性：单节点故障不影响整体服务
- [ ] 可观测：所有关键指标暴露 Prometheus
- [ ] 兼容：V1 前端无需改动即可连接 V2 后端

### 12.3 兼容性验收

- [ ] V1 前端无需改动即可连接 V2 后端
- [ ] V1 Agent 可连接 V2 控制面（降级 HTTP 轮询）
- [ ] V1 数据库可平滑迁移到 V2 schema
- [ ] V1 standalone 任务在 V2 默认 `distribution_mode=standalone` 正常运行

---

## 十三、里程碑

| 里程碑 | 时间 | 交付物 |
|---|---|---|
| M1: 止血完成 | +2 周 | V1.1 安全版本 |
| M2: 架构收敛 + Crawlo 适配 | +2 月 | V2.0（三种模式可用） |
| M3: 可观测就绪 | +3 月 | V2.0.1 告警 + 日志聚合 |
| M4: 生态完整 | +6 月 | V2.1 完整平台 |

---

## 十四、附录

### 14.1 术语表

| 术语 | 含义 |
|---|---|
| 编排面 | CrawloPilot，负责多爬虫调度、节点管理、状态管理 |
| 执行面 | Crawlo 框架，负责单爬虫内的请求分发、ACK、Failover |
| TaskStateStore | 任务级状态中间层（spider 整体 running/done） |
| CrawloDistributedAdapter | 把任务转换为 Crawlo distributed 部署的适配器 |
| distribution_mode | 任务部署模式：standalone / single_node_distributed / multi_node_distributed |
| standalone | Crawlo 内存队列模式，不依赖 Redis |
| distributed | Crawlo Redis Stream 模式，支持多 Worker |
| Consumer Group | Crawlo 的 Worker 消费组，自动负载均衡 |
| XACK/XAUTOCLAIM | Crawlo 的请求级确认/故障回收机制 |

### 14.2 关键修正记录

相比 V2 初版方案，本版的修正：

| 项 | 初版 | 本版 | 理由 |
|---|---|---|---|
| Agent 通信 | Redis Streams MessageBus | HTTP 长轮询 | Crawlo 已有 Stream，不重复 |
| 任务级 vs 请求级 | 混在一起 | 明确分离 | Crawlo 管请求级，CrawloPilot 管任务级 |
| Crawlo 分布式 | 不支持 | CrawloDistributedAdapter | 核心新增能力 |
| 部署模式 | 单一 | 三种 distribution_mode | 按需选择 |
| MessageBus 模块 | 保留 | **取消** | 重复造轮子 |

### 14.3 参考资料

- [DESIGN-ISSUES.md](../DESIGN-ISSUES.md)：V1 问题清单
- [docs/design-philosophy.md](design-philosophy.md)：V1 设计哲学
- Crawlo 分布式架构：`/Users/oscar/projects/Crawlo/docs/distributed_architecture.md`
- Crawlo cluster 模块：`/Users/oscar/projects/Crawlo/crawlo/cluster/`
- Crawlo RedisStreamQueue：`/Users/oscar/projects/Crawlo/crawlo/queue/redis_stream_queue.py`
