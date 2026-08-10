# CrawloPilot V2 设计方案（修订版）

> 版本：V2.0-revised（基于 Crawlo 1.7.3 架构对齐修正）
> 日期：2026-08-09
> 作者：架构评审
> 状态：待评审
> 关联文档：[v2-design.md](v2-design.md)（原版）、[DESIGN-ISSUES.md](../DESIGN-ISSUES.md)、[design-philosophy.md](design-philosophy.md)
> 修订基础：基于对 Crawlo 1.7.3 源码的深度审计，修正原版 6 处技术偏差

---

## 修订摘要

相比 [v2-design.md](v2-design.md) 原版，本版修正了以下 6 处技术偏差：

| # | 原版问题 | 影响 | 本版修正 |
|---|---|---|---|
| 1 | Redis Key 缺少命名空间前缀 | 所有 Redis 读取/订阅失败 | 增加 `redis_namespace` 字段，所有 Key 按 `{ns}:{suffix}` 拼接 |
| 2 | `REDIS_URL` 配置项不存在 | 分布式模式无法连接 Redis | 拆解为分散配置 + settings override 文件 |
| 3 | `SPIDER_NAME` 环境变量无效 | 爬虫无法启动 | 改用 CLI 参数 + settings override |
| 4 | 配置传递方式不可靠 | 非默认配置不生效 | 生成临时 settings override 文件，通过 `--settings` 指定 |
| 5 | Worker 脚本 `os.wait()` 只等待一个子进程 | 多 Worker 时部分子进程泄漏 | 改为 `for p in processes: p.wait()` |
| 6 | 心跳 TTL 30s 与 Crawlo 15s 心跳不匹配 | 误判任务超时 | 对齐为 60s TTL（覆盖 Crawlo 2 次心跳周期） |

此外补充了 auto 模式定位说明、版本要求升级至 `crawlo>=1.7.3`、AlertManager 指标 Key 前缀修正、节点级崩溃处理增强。

---

## 〇、版本边界说明

> 本文是 V2 方案修订版。以下能力已在 V1 交付，V2 在其基础上演进：
>
> **V1 已交付（不再属于 V2 范围）**：
> - Agent token-in-URL 彻底移除（纯 Bearer header）
> - 日志查询 `level`/`since` 过滤参数
> - Executor Protocol 契约定义 + 四个执行器适配（含 Agent `execute_task`）
> - Agent 长轮询（`long_poll` 参数）
> - 密钥分离（JWT 与凭据加密双密钥）
> - task_updater 终态原子更新
> - Git 工作流 + 凭据体系
> - 进程内 APScheduler 定时调度
>
> **V2 新增（本文核心内容）**：
> - 三种 distribution_mode + CrawloDistributedAdapter（§三、§5.3）
> - 多实例部署（§2.1）
> - TaskStateStore 全量状态收敛（§5.1）
> - AlertManager 告警引擎（§5.4）
> - ProxyPool 代理池（§5.5）
> - Loki 日志聚合（§5.6）
> - AuditLog 完整审计（§5.7）
>
> 详见 [design-philosophy.md](design-philosophy.md) 和 [remaining-work.md](remaining-work.md) 了解 V1 已交付能力。

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
| 编排与执行边界 | 部分原子更新，未全量收敛 | TaskStateStore 全量收敛任务级状态 |
| 多实例部署 | 单实例硬约束 | 水平扩展 |
| 执行器契约 | ✅ 已实现 Protocol | 保持，状态经 TaskStateStore |
| Agent 通信 | ✅ 已实现长轮询 | 保持，接入分布式模式 |
| Crawlo 分布式调度 | 不支持 | CrawloDistributedAdapter |
| 可观测性 | 基础指标 + 日志过滤 | 告警 + 日志聚合 |
| 安全 | ✅ 已实现双密钥 + Bearer | 保持 + 审计 |
| 生态扩展 | 无 | 代理池 + Webhook |

### 1.5 版本要求

**V2.0 要求 `crawlo >= 1.7.3`**。

理由：1.7.3 完成了核心架构重构，分布式组件（RedisStreamQueue、FailoverManager、ProgressAggregator、ClusterMessenger）在此版本后才完全稳定。1.7.2 的分布式能力存在已知的配置路径问题。

### 1.6 非目标

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
| 状态写入 | 部分原子更新，未全量收敛 | 全量经 TaskStateStore（任务级） |
| 调度器 | APScheduler 进程内 | 独立服务 + DB advisory lock |
| Agent 通信 | ✅ 长轮询已实现 | 接入分布式模式 |
| 日志存储 | 文件 + 容器卷 + 过滤查询 | Loki 聚合 |
| 告警 | 无 | AlertManager + Webhook |
| 代理池 | 无 | ProxyPool 微服务 |
| 密钥管理 | ✅ JWT / 凭据加密分离已实现 | 保持 + 审计 |
| 审计 | 无 | AuditLog 模块 |
| Crawlo 分布式 | 不支持 | CrawloDistributedAdapter |

### 2.2 与 Crawlo 的职责边界

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

### 3.0 Crawlo 运行模式与 V2 映射

Crawlo 通过两个正交配置维度（`RUN_MODE` × `QUEUE_TYPE`）提供三种运行模式：

| Crawlo 模式 | RUN_MODE | QUEUE_TYPE | Redis | ACK | Failover |
|---|---|---|---|---|---|
| 内存模式 | `standalone` | `memory` | 不需要 | 无 | 无 |
| 多节点协作 | `auto` | `redis` | 必需 | 无（ZPOPMIN 即移除） | 无 |
| 分布式系统 | `distributed` | `redis_stream` | 必需（5.0+） | XACK | 两阶段检测 + XAUTOCLAIM |

V2 的三种 distribution_mode 映射：

| V2 distribution_mode | 对应 Crawlo RUN_MODE | 对应 Crawlo QUEUE_TYPE | Redis 要求 |
|---|---|---|---|
| `standalone` | `standalone` | `memory` | 不需要 |
| `single_node_distributed` | `distributed` | `redis_stream` | 本机 Redis |
| `multi_node_distributed` | `distributed` | `redis_stream` | 共享 Redis（Sentinel HA） |

**为什么不支持 `auto` 模式？**

Crawlo 的 `auto` 模式（Redis ZSET 竞争消费）没有 ACK 和故障转移，任务可能丢失。在生产编排平台上，数据丢失是不可接受的。如果需要轻量多节点并发且不要求严格不丢数据，可以使用 `standalone` 模式 + 多节点独立部署（每个节点跑独立的 spider 实例），由 CrawloPilot 管理多个独立任务。

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

新增字段 `distribution_mode` 及配套字段：

```sql
ALTER TABLE task_instance ADD COLUMN distribution_mode
    ENUM('standalone', 'single_node_distributed', 'multi_node_distributed')
    DEFAULT 'standalone';

ALTER TABLE task_instance ADD COLUMN shared_redis_url VARCHAR(256)
    COMMENT '模式 C 共享 Redis 地址（Sentinel 格式：redis+sentinel://host:26379/0）';

ALTER TABLE task_instance ADD COLUMN worker_count INT DEFAULT 1
    COMMENT '模式 B/C 每节点启动的 Worker 进程数';

-- 【修订新增】Redis Key 命名空间，格式 {project}:{spider}
-- Crawlo 的所有 Redis Key 都以该前缀拼接：{ns}:stream:tasks、{ns}:control:state 等
-- 用于 TaskStateStore 读取统计、AlertManager 读取指标、订阅完成信号
ALTER TABLE task_instance ADD COLUMN redis_namespace VARCHAR(128)
    COMMENT 'Crawlo Redis Key 命名空间，格式 {project}:{spider}';
```

**`redis_namespace` 的计算规则**：

```
redis_namespace = f"{project_name}:{spider_name}"
```

例如项目名为 `ecommerce`、爬虫名为 `product_spider`，则 namespace = `ecommerce:product_spider`。Crawlo 内部所有 Redis Key 的完整格式为：

```
crawlo:{redis_namespace}:stream:tasks
crawlo:{redis_namespace}:control:state
crawlo:{redis_namespace}:registry:workers
crawlo:{redis_namespace}:progress:stats
crawlo:{redis_namespace}:channel:control    (Pub/Sub)
...
```

> **注意**：Crawlo 在 Redis Key 前会自动拼接 `crawlo:` 前缀（由 `PROJECT_NAME` 配置控制），因此 `redis_namespace` 字段只存储 `{project}:{spider}` 部分。CrawloPilot 读取 Redis 时需自行拼接 `crawlo:{redis_namespace}:{suffix}`。

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
│   │ 生成 settings override 文件                  │   │
│   │ 传递 Redis 分散配置 + 命名空间               │   │
│   └─────────────────────────────────────────────┘   │
└──────────────────────┬───────────────────────────────┘
                       │ 调度任务到节点
┌──────────────────────┴───────────────────────────────┐
│ 执行面 Execution Plane                              │
│   Executor Protocol:                                │
│   ┌──────────┬──────────┬──────────┬─────────────┐ │
│   │ Local    │ SSH      │ Docker   │ Agent       │ │
│   │ (3模式) │ (3模式) │ (3模式) │ (3模式)     │ │
│   └──────────┴──────────┴──────────┴─────────────┘ │
└──────────────────────┬───────────────────────────────┘
                       │ 启动 Crawlo (--settings override)
┌──────────────────────┴───────────────────────────────┐
│ Crawlo 框架（已有能力，不重做）                      │
│   standalone: 内存队列                              │
│   distributed: Redis Stream + ACK + Failover       │
│   Redis Key 命名空间: crawlo:{project}:{spider}:*  │
└────────────────────────────────────────────────────┘
                       │
┌──────────────────────┴───────────────────────────────┐
│ 数据面 / 可观测 / 生态                              │
│   MySQL · Loki · AlertManager · ProxyPool           │
│   Redis (Crawlo 共享，CrawloPilot 读取统计/指标)    │
└────────────────────────────────────────────────────┘
```

### 4.2 核心改进点

1. **TaskStateStore**：任务级状态变更的唯一入口（不碰请求级）
2. **Executor Protocol**：抽象基类 + 编译期契约检查
3. **CrawloDistributedAdapter**：把任务转换为 Crawlo distributed 部署，生成 settings override 文件
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
        """执行器心跳上报。Redis TTL 60s，过期由 reaper 标记任务 failed。"""

    async def append_log(self, task_id: int, line: str, level: str) -> None:
        """日志写入 Loki + Redis 缓冲。"""

    async def update_stats(self, task_id: int, stats: dict) -> None:
        """更新爬虫统计（items_count / pages_count 等，来自 Crawlo ProgressAggregator）。"""
```

**实现要点**：

- DB 层：`UPDATE task_instance SET status=:to WHERE id=:id AND status IN (:from)` 原子性
- 心跳：Redis `task:heartbeat:{task_id}` TTL **60s**（修订：原版 30s， Crawlo Worker 心跳 15s 一次，60s TTL 覆盖 Crawlo 2 次心跳周期，避免误判）
- 多实例：状态机无共享，多个控制面实例可同时写不冲突
- 审计：每次 transition 记录到 AuditLog

**与 Crawlo 的协作**（修订：Redis Key 带命名空间前缀）：

- Crawlo 的 `ProgressAggregator` 每 10s 把统计写入 Redis HASH `crawlo:{ns}:progress:stats`
- CrawloPilot 的 `TaskStateStore.update_stats` 从 `crawlo:{redis_namespace}:progress:stats` 读取并同步到 MySQL
- Crawlo 的 `crawlo:{ns}:control:state` 变为 `shutdown` 时，CrawloPilot 监听到后调用 `transition(task_id, [...], COMPLETED)`

**Redis Key 拼接规则**：

```python
def _crawlo_key(self, task: TaskInstance, suffix: str) -> str:
    """拼接 Crawlo 的完整 Redis Key。

    Crawlo 内部以 {PROJECT_NAME}:{spider_name} 作为命名空间，
    并在前面自动拼接 'crawlo:' 前缀。
    CrawloPilot 读取时需拼接完整 Key。
    """
    return f"crawlo:{task.redis_namespace}:{suffix}"

# 示例
# task.redis_namespace = "ecommerce:product_spider"
# _crawlo_key(task, "progress:stats") → "crawlo:ecommerce:product_spider:progress:stats"
# _crawlo_key(task, "control:state")  → "crawlo:ecommerce:product_spider:control:state"
```

### 5.2 Executor Protocol（执行器契约）

> Executor Protocol 已在 V1 完整定义并实现（四个执行器均适配）。
>
> **V2 新增点**：执行器状态变更统一改经 `TaskStateStore.transition`（见 §5.1），
> 并将 `CrawloDistributedAdapter` 作为 Agent 执行器的 V2 扩展接入三种部署模式。

### 5.3 CrawloDistributedAdapter（新增 · 核心模块）

**职责**：把 CrawloPilot 的任务转换为 Crawlo distributed 部署，对接三种模式。

**修订要点**（相比原版的 6 处修正）：

1. 不再使用 `REDIS_URL` / `SPIDER_NAME` / `PROJECT_NAME` 环境变量传递配置
2. 改为生成临时 settings override 文件，通过 `--settings` CLI 参数指定
3. 所有 Redis Key 读取/订阅使用 `redis_namespace` 拼接完整 Key
4. Worker 启动脚本修正 `os.wait()` 问题
5. 心跳 TTL 从 30s 改为 60s
6. 增加节点级崩溃检测

```python
class CrawloDistributedAdapter:
    """把 CrawloPilot 任务转换为 Crawlo distributed 部署。

    不重复实现 Crawlo 的 Stream/ACK/Failover，
    只负责选择模式、生成 settings override、监听完成。
    """

    def __init__(self, task_state_store: TaskStateStore, agent_service):
        self.task_state_store = task_state_store
        self.agent_service = agent_service

    async def deploy(
        self,
        task: TaskInstance,
        nodes: list[Node],
    ) -> None:
        """根据 task.distribution_mode 选择部署方式。"""
        mode = task.distribution_mode

        if mode == "standalone":
            await self._deploy_standalone(task, nodes)
        elif mode == "single_node_distributed":
            await self._deploy_single_node_distributed(task, nodes[0])
        elif mode == "multi_node_distributed":
            await self._deploy_multi_node_distributed(task, nodes)

    async def _deploy_standalone(self, task, nodes):
        """模式 A：标准 standalone 部署。

        每个 Agent 收到任务后执行：
            crawlo run spider_name --settings <override_file>
        不需要 Redis。节点故障 = 任务失败。
        """
        settings_module = await self._generate_settings_override(task, mode="standalone")

        for node in nodes[:1]:  # standalone 只调度到一个节点
            await self.agent_service.dispatch(
                node_id=node.id,
                entry_file=f"crawlo run {task.spider_name} --settings {settings_module}",
                env={
                    "CRAWLO_MODE": "standalone",
                },
            )

    async def _deploy_single_node_distributed(self, task, node):
        """模式 B：单节点多 Worker，本机 Redis。

        Agent 收到任务后执行启动脚本，启动 N 个 Worker：
            for i in range(N):
                crawlo run spider_name --settings <override_file>

        所有 Worker 共享本机 Redis，Crawlo Consumer Group 自动负载均衡。
        """
        settings_module = await self._generate_settings_override(
            task,
            mode="single_node_distributed",
            redis_host="127.0.0.1",
            redis_port=6379,
        )
        worker_script = self._generate_worker_script(
            spider_name=task.spider_name,
            worker_count=task.worker_count or 4,
            settings_module=settings_module,
        )
        await self.agent_service.dispatch(
            node_id=node.id,
            entry_file=f"python {worker_script}",
            env={
                "CRAWLO_MODE": "distributed",
            },
        )
        # 订阅 Crawlo 的 control:state 变化（使用完整 Key）
        await self._subscribe_crawlo_completion(task)

    async def _deploy_multi_node_distributed(self, task, nodes):
        """模式 C：多节点共享 Redis。

        所有 Agent 收到相同任务，连接同一个 Redis（Sentinel HA）。
        Crawlo 的 Consumer Group 自动跨节点负载均衡。
        """
        # 解析 shared_redis_url，拆解为分散配置
        redis_config = self._parse_redis_url(task.shared_redis_url)

        settings_module = await self._generate_settings_override(
            task,
            mode="multi_node_distributed",
            **redis_config,
        )

        for node in nodes:
            await self.agent_service.dispatch(
                node_id=node.id,
                entry_file=f"crawlo run {task.spider_name} --settings {settings_module}",
                env={
                    "CRAWLO_MODE": "distributed",
                },
            )
        # 订阅 Crawlo 协调退出信号
        await self._subscribe_crawlo_completion(task)

    async def _generate_settings_override(
        self,
        task: TaskInstance,
        mode: str,
        redis_host: str | None = None,
        redis_port: int | None = None,
        redis_password: str | None = None,
        redis_db: int = 0,
        sentinel_urls: list[str] | None = None,
        sentinel_service: str = "mymaster",
    ) -> str:
        """生成临时 settings override 文件。

        Crawlo 不通过环境变量传递 REDIS_HOST / QUEUE_TYPE 等配置，
        这些配置在 settings.py 中设置。因此 CrawloPilot 生成临时
        override 文件，通过 --settings 参数指定。

        返回 override 文件路径（相对于爬虫项目根目录）。
        """
        config_lines = [
            "# CrawloPilot auto-generated settings override",
            "# Do not edit manually.",
            f"PROJECT_NAME = '{task.project_name}'",
        ]

        if mode == "standalone":
            config_lines.extend([
                "RUN_MODE = 'standalone'",
                "QUEUE_TYPE = 'memory'",
            ])
        elif mode == "single_node_distributed":
            config_lines.extend([
                "RUN_MODE = 'distributed'",
                "QUEUE_TYPE = 'redis_stream'",
                f"REDIS_HOST = '{redis_host or '127.0.0.1'}'",
                f"REDIS_PORT = {redis_port or 6379}",
                f"REDIS_DB = {redis_db}",
            ])
            if redis_password:
                config_lines.append(f"REDIS_PASSWORD = '{redis_password}'")
        elif mode == "multi_node_distributed":
            config_lines.extend([
                "RUN_MODE = 'distributed'",
                "QUEUE_TYPE = 'redis_stream'",
            ])
            if sentinel_urls:
                config_lines.extend([
                    f"REDIS_SENTINEL_URLS = {sentinel_urls!r}",
                    f"REDIS_SENTINEL_SERVICE = '{sentinel_service}'",
                ])
            else:
                config_lines.extend([
                    f"REDIS_HOST = '{redis_host}'",
                    f"REDIS_PORT = {redis_port}",
                    f"REDIS_DB = {redis_db}",
                ])
                if redis_password:
                    config_lines.append(f"REDIS_PASSWORD = '{redis_password}'")

        content = "\n".join(config_lines) + "\n"
        file_path = f"{UPLOAD_DIR}/_settings/task_{task.id}_settings.py"
        await self._write_file(file_path, content)
        return file_path

    def _parse_redis_url(self, url: str) -> dict:
        """解析 Redis URL 为分散配置。

        支持：
        - redis://host:port/db
        - redis://:password@host:port/db
        - redis+sentinel://host:26379/db?service=mymaster
        """
        if url.startswith("redis+sentinel://"):
            return self._parse_sentinel_url(url)
        elif url.startswith("redis://"):
            return self._parse_standalone_url(url)
        else:
            raise ValueError(f"Unsupported Redis URL format: {url}")

    def _parse_standalone_url(self, url: str) -> dict:
        """解析 redis://[password@]host:port/db 格式。"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return {
            "redis_host": parsed.hostname or "127.0.0.1",
            "redis_port": parsed.port or 6379,
            "redis_password": parsed.password,
            "redis_db": int(parsed.path.lstrip("/") or "0"),
        }

    def _parse_sentinel_url(self, url: str) -> dict:
        """解析 redis+sentinel://host:26379/db?service=mymaster 格式。"""
        from urllib.parse import urlparse, parse_qs
        stripped = url.replace("redis+sentinel://", "redis://", 1)
        parsed = urlparse(stripped)
        query = parse_qs(parsed.query)
        return {
            "sentinel_urls": [f"{parsed.hostname}:{parsed.port or 26379}"],
            "sentinel_service": query.get("service", ["mymaster"])[0],
            "redis_db": int(parsed.path.lstrip("/") or "0"),
        }

    async def _subscribe_crawlo_completion(self, task: TaskInstance):
        """监听 Crawlo 的 control:state，任务完成时通知 TaskStateStore。

        Crawlo Leader Worker 检测到全部完成时，会：
            SET crawlo:{ns}:control:state = "shutdown"
            PUBLISH crawlo:{ns}:channel:control {"action": "shutdown"}

        本方法订阅 Pub/Sub 频道（使用完整命名空间 Key），
        收到 shutdown 时调用 TaskStateStore.transition(COMPLETED)。
        """
        channel = f"crawlo:{task.redis_namespace}:channel:control"
        state_key = f"crawlo:{task.redis_namespace}:control:state"

        # 后台任务：订阅 channel
        async def _listener():
            redis = await self._get_redis_connection(task)
            pubsub = redis.pubsub()
            await pubsub.subscribe(channel)
            try:
                async for message in pubsub.listen():
                    if message["type"] == "message":
                        import json
                        data = json.loads(message["data"])
                        if data.get("action") == "shutdown":
                            await self.task_state_store.transition(
                                task.id,
                                [TaskStatus.RUNNING],
                                TaskStatus.COMPLETED,
                            )
                            return
            finally:
                await pubsub.unsubscribe(channel)

        # 同时启动兜底轮询：每 10s 检查 control:state 持久化 Key
        async def _poller():
            import asyncio
            redis = await self._get_redis_connection(task)
            while True:
                await asyncio.sleep(10)
                state = await redis.get(state_key)
                if state and state.decode() == "shutdown":
                    await self.task_state_store.transition(
                        task.id,
                        [TaskStatus.RUNNING],
                        TaskStatus.COMPLETED,
                    )
                    return

        # 启动两个后台任务，任一感知到 shutdown 即可
        asyncio.create_task(_listener())
        asyncio.create_task(_poller())

    def _generate_worker_script(
        self,
        spider_name: str,
        worker_count: int,
        settings_module: str,
    ) -> str:
        """生成启动脚本（启动 N 个 Worker 进程）。

        修订：原版 os.wait() 只等待一个子进程，改为循环等待全部。
        """
        return f"""
import subprocess, sys, time, os, signal

def main():
    processes = []
    for i in range({worker_count}):
        p = subprocess.Popen(
            [sys.executable, "-m", "crawlo", "run", "{spider_name}",
             "--settings", "{settings_module}"],
            env={{**os.environ, "CRAWLO_MODE": "distributed"}}
        )
        processes.append(p)
        time.sleep(2)  # 间隔启动，避免心跳风暴

    # 等待所有子进程退出
    exit_codes = []
    for p in processes:
        exit_codes.append(p.wait())

    # 任一非零退出码则整体失败
    sys.exit(1 if any(c != 0 for c in exit_codes) else 0)

if __name__ == "__main__":
    main()
"""

    def _get_redis_connection(self, task: TaskInstance):
        """获取与 Crawlo 共享的 Redis 连接。

        使用任务的 Redis 配置（模式 B 用本机 Redis，模式 C 用共享 Redis）。
        """
        # 根据 task 的 Redis 配置创建连接
        # 实现略，使用 aioredis / redis-py asyncio
        pass
```

**关键设计点**（修订后）：

1. **不重复造 Stream**：Crawlo 已经有 Redis Stream，CrawloPilot 只负责生成 settings override 文件
2. **配置注入可靠**：通过 `--settings` 参数指定 override 文件，不依赖环境变量传递 Redis 配置
3. **订阅完成信号**：通过 Crawlo 的 `crawlo:{ns}:control:state = "shutdown"` 感知任务完成，同时订阅 Pub/Sub 和轮询持久化 Key（双通道保证）
4. **节点故障处理**：
   - 模式 A：节点故障 = 任务失败，CrawloPilot 重试
   - 模式 B 单 Worker 崩溃：由 Crawlo FailoverManager 处理（XAUTOCLAIM 回收 pending），CrawloPilot 不感知
   - 模式 B 节点级崩溃：CrawloPilot Agent 检测节点失联 → 标记任务 `node_failed` → TaskStateStore 触发重试
   - 模式 C 单节点崩溃：Crawlo XAUTOCLAIM 回收该节点 pending 到其他节点，CrawloPilot 看任务仍 running
   - 模式 C 全部节点崩溃：CrawloPilot 检测到全部 Agent 失联 → 标记任务 failed

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

**内置规则**（修订：Redis Key 使用完整命名空间前缀）：

| 规则 | 默认阈值 | 窗口 | 指标来源 | Redis Key |
|---|---|---|---|---|
| 任务失败 | 连续 3 次 | 1h | CrawloPilot 任务级 | — |
| 节点离线 | 心跳超 60s | 实时 | CrawloPilot 节点级 | — |
| 任务超时 | > 30 分钟 | 实时 | CrawloPilot 任务级 | — |
| 死信队列增长 | > 0 | 5min | Crawlo Redis | `XLEN crawlo:{ns}:stream:failed` |
| Worker 故障 | Worker 数下降 | 5min | Crawlo Redis | `HLEN crawlo:{ns}:registry:workers` |
| 队列积压 | pending > 1000 | 5min | Crawlo Redis | `XPENDING crawlo:{ns}:stream:tasks group:workers` |
| 去重集合过大 | SCARD > 100万 | 30min | Crawlo Redis | `SCARD crawlo:{ns}:dedup:request` |

**与 Crawlo 集成**：AlertManager 后台任务从 Crawlo 的 Redis 读取指标。所有 Key 使用 `crawlo:{redis_namespace}:{suffix}` 格式拼接。AlertManager 需要知道当前运行中任务的 `redis_namespace` 才能读取对应的指标。

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

- Crawlo 通过 settings override 中的 `PROXY_POOL_URL` 配置项调用 ProxyPool
- Crawlo 的 `ProxyMiddleware` 自动从 ProxyPool 获取代理（需确认 Crawlo 是否已内置此能力，如未内置需在 Crawlo 侧新增）
- 代理失败时 Crawlo 上报，ProxyPool 标记不可用

> **注意**：`PROXY_POOL_URL` 不是 Crawlo 当前内置的配置项。V2.0 实现时需确认 Crawlo 版本是否支持。如果不支持，有两个替代方案：
> 1. 在 Crawlo 侧新增 `ProxyPoolMiddleware`（推荐，需 Crawlo >= 某版本）
> 2. 由 CrawloPilot Agent 在启动爬虫前将代理列表写入 settings override 文件的 `PROXY_LIST` 配置项

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
| Crawlo 配置注入 | settings override 文件 + `--settings` 参数 | Crawlo 配置体系以文件为主，环境变量仅覆盖 `RUN_MODE` |

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

-- 【修订新增】redis_namespace：Crawlo Redis Key 命名空间
ALTER TABLE task_instance 
    ADD COLUMN redis_namespace VARCHAR(128)
    COMMENT 'Crawlo Redis Key 命名空间，格式 {project}:{spider}';

-- nodes: 新增 last_seen_at
ALTER TABLE nodes 
    ADD COLUMN last_seen_at DATETIME;
```

### 7.3 迁移策略

- 新增表：直接创建，不影响 V1
- 修改表：`deploy_mode` 改 ENUM 需先清理脏数据
- `distribution_mode` 默认 `standalone`，V1 任务自动兼容
- `redis_namespace` 对 V1 standalone 任务留空，仅 B/C 模式使用
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
POST   /api/v1/tasks  # 新增 distribution_mode / shared_redis_url / worker_count / redis_namespace 字段
```

### 8.2 修改 API

> 以下能力已在 V1 实现，V2 在其基础上扩展。

**Agent 鉴权**（V1 已实现纯 Bearer，query token 已彻底移除）：

```diff
- GET /api/v1/nodes/agent/tasks?node_id=1&token=xxx
+ GET /api/v1/nodes/agent/tasks?node_id=1
+ Authorization: Bearer xxx
```

**Agent 长轮询**（V1 已实现 `long_poll=1`，V2 保持兼容）：

```diff
- GET /api/v1/nodes/agent/tasks  # 立即返回，5s 后再请求
+ GET /api/v1/nodes/agent/tasks?long_poll=1  # hold 最多 25s，有任务立即返回
```

**日志查询增强**（V1 已实现 `level` / `since` 参数，V2 增加 Loki 聚合）：

```diff
- GET /api/v1/tasks/{id}/logs
+ GET /api/v1/tasks/{id}/logs?tail=200&level=ERROR&since=1h
```

### 8.3 废弃 API

V1 已完成的清理：
- query token 传递已彻底移除（agent 端已全部升级 Bearer）

---

## 九、演进路线

### Phase 1：止血修复（V1 已完成）

> 以下已在 V1 交付：删除 task_executor.py 死代码、SECRET_KEY 拆分 + 启动校验（强制双密钥分离）、
> Agent token 改 Bearer header（彻底移除 query token）、tar 路径穿越修复、
> SSH 命令注入 + host key TOFU、CRAWLO_WHEEL_PATH 默认 None。
> 详见 [design-philosophy.md](design-philosophy.md)。

### Phase 2：架构收敛（1-2 个月）

**目标**：解决状态散落 + 单实例约束 + Crawlo 分布式调度。

> V1 已交付基础：Executor Protocol 定义与 4 执行器适配、Agent 长轮询、Agent 任务领取/终态的状态原子更新（DB 条件 UPDATE）、迁移历史清理。

**V2 待办**：

| 任务 | 工作量 | 依赖 |
|---|---|---|
| 引入 Redis 基础设施 | 2h | - |
| 实现 TaskStateStore | 16h | Redis |
| **实现 CrawloDistributedAdapter** | 24h | TaskStateStore |
| **实现 settings override 生成器** | 4h | CrawloDistributedAdapter |
| **实现 Redis Key 命名空间管理** | 4h | CrawloDistributedAdapter |
| 调度器拆分 + DB 锁 | 16h | - |
| 全量状态写入收敛到 TaskStateStore（覆盖 Local/SSH/Docker 执行器） | 16h | TaskStateStore |

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
1. CrawloPilot 调度器触发任务，计算 `redis_namespace = "news:news_spider"`（standalone 模式不使用 Redis，但字段仍填充）
2. CrawloDistributedAdapter 生成 settings override 文件：
   ```python
   PROJECT_NAME = 'news'
   RUN_MODE = 'standalone'
   QUEUE_TYPE = 'memory'
   ```
3. Agent 收到任务，下载代码 + override 文件
4. Agent 执行 `crawlo run news_spider --settings task_123_settings.py`
5. Crawlo standalone 模式运行，内存队列
6. 完成后 Agent 上报 `COMPLETED`
7. CrawloPilot TaskStateStore 更新状态

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
1. CrawloPilot 调度任务到 Node 1，计算 `redis_namespace = "ecommerce:product_spider"`
2. CrawloDistributedAdapter 生成 settings override 文件：
   ```python
   PROJECT_NAME = 'ecommerce'
   RUN_MODE = 'distributed'
   QUEUE_TYPE = 'redis_stream'
   REDIS_HOST = '127.0.0.1'
   REDIS_PORT = 6379
   REDIS_DB = 0
   ```
3. CrawloDistributedAdapter 生成 Worker 启动脚本（8 个 Worker）
4. Agent 执行脚本，启动 8 个 Crawlo Worker（distributed 模式，`--settings task_456_settings.py`）
5. 8 个 Worker 共享本机 Redis，Consumer Group 自动负载均衡
6. 单个 Worker 崩溃 → Crawlo FailoverManager 120s 回收其 pending
7. 全部完成 → Crawlo Leader 广播 `PUBLISH crawlo:ecommerce:product_spider:channel:control {"action":"shutdown"}`
8. CrawloPilot `_subscribe_crawlo_completion` 监听到 shutdown → 标记 COMPLETED

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
    "shared_redis_url": "redis+sentinel://sentinel:26379/0?service=mymaster",
    "worker_count": 4,
    "schedule": "manual"
}
```

**执行流程**：
1. CrawloPilot 调度任务到 Node 1/2/3，计算 `redis_namespace = "gov:data_spider"`
2. CrawloDistributedAdapter 解析 Sentinel URL，生成 settings override 文件：
   ```python
   PROJECT_NAME = 'gov'
   RUN_MODE = 'distributed'
   QUEUE_TYPE = 'redis_stream'
   REDIS_SENTINEL_URLS = ['sentinel:26379']
   REDIS_SENTINEL_SERVICE = 'mymaster'
   REDIS_DB = 0
   ```
3. 3 个 Agent 同时收到任务 + 同一个 override 文件
4. 每个 Agent 启动 4 个 Crawlo Worker，全部连接共享 Redis（Sentinel HA）
5. 12 个 Worker 共享一个 Consumer Group，自动负载均衡
6. Node 2 崩溃 → Crawlo FailoverManager 90s 检测 → XAUTOCLAIM 回收 Node 2 的 pending 到 Node 1/3
7. CrawloPilot 通过 Redis 监控 `HLEN crawlo:gov:data_spider:registry:workers` 发现 Worker 数从 12 降到 8，触发告警
8. 全部完成 → Crawlo Leader 广播 shutdown → CrawloPilot 标记 COMPLETED

---

## 十一、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Redis 单点故障（模式 B/C） | 中 | 高 | Sentinel 主从；Agent 降级 standalone |
| Crawlo 与 CrawloPilot 版本不匹配 | 中 | 中 | Adapter 版本协商；兼容性测试；要求 crawlo >= 1.7.3 |
| 调度器多实例触发 | 低 | 中 | DB advisory lock；唯一索引 |
| Loki 日志查询慢 | 低 | 中 | 索引 label 精简；保留期 30 天 |
| V1 升级 V2 数据迁移失败 | 中 | 高 | 全量备份 + 灰度升级 + 回滚脚本 |
| Agent 协议升级兼容性 | 中 | 中 | 版本协商；V1 Agent 仍可连接 |
| 代理池质量不稳 | 高 | 低 | 多源混合；健康检查；降级直连 |
| 共享 Redis 多 spider 资源竞争 | 中 | 中 | `{project}:{spider}` 命名空间隔离 |
| settings override 文件残留 | 低 | 低 | 任务结束后清理 `_settings/task_{id}_settings.py` |
| Redis Key 命名空间计算错误 | 中 | 高 | 单元测试覆盖；部署前校验 namespace 格式 |

---

## 十二、验收标准

### 12.1 功能验收

- [ ] 4 个执行器全部适配 Executor Protocol
- [ ] TaskStateStore 成为任务级状态唯一入口
- [ ] **三种 distribution_mode 全部可用**
  - [ ] 模式 A：standalone 任务正常调度
  - [ ] 模式 B：单节点 N Worker，任务完成正确感知
  - [ ] 模式 C：多节点共享 Redis，节点故障任务不丢
- [ ] **CrawloDistributedAdapter 生成的 settings override 能被 Crawlo 正确读取**
- [ ] **Redis Key 命名空间在所有模式下正确拼接**
- [ ] **模式 B 单 Worker 崩溃后 pending 被 XAUTOCLAIM 回收**
- [ ] **模式 B 节点级崩溃后 CrawloPilot 能检测并标记 failed**
- [ ] **模式 C 节点崩溃后其余节点继续消费**
- [ ] **control:state = shutdown 被正确订阅（含命名空间前缀）**
- [ ] **ProgressAggregator 统计能被 TaskStateStore 正确读取**
- [ ] Agent 长轮询（hold 30s）正常工作
- [ ] 多实例部署（2 个控制面）任务不重复执行
- [ ] AlertManager 7 条内置规则触发验证通过
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
| redis_namespace | Crawlo Redis Key 命名空间，格式 `{project}:{spider}`，所有 Key 以 `crawlo:{ns}:{suffix}` 拼接 |
| settings override | CrawloPilot 生成的临时 settings 文件，通过 `--settings` 参数传递给 Crawlo |
| standalone | Crawlo 内存队列模式，不依赖 Redis |
| distributed | Crawlo Redis Stream 模式，支持多 Worker |
| Consumer Group | Crawlo 的 Worker 消费组，自动负载均衡 |
| XACK/XAUTOCLAIM | Crawlo 的请求级确认/故障回收机制 |

### 14.2 Crawlo Redis Key 完整清单

Crawlo 在分布式模式下使用的所有 Redis Key（以 `crawlo:{project}:{spider}:` 为前缀）：

| 用途 | 数据结构 | 完整 Key 格式 |
|---|---|---|
| 任务队列（普通） | STREAM | `crawlo:{ns}:stream:tasks` |
| 任务队列（高优） | STREAM | `crawlo:{ns}:stream:tasks:high` |
| 死信队列 | STREAM | `crawlo:{ns}:stream:failed` |
| 消费者组 | CONSUMER GROUP | `crawlo:{ns}:group:workers` |
| Worker 注册表 | HASH | `crawlo:{ns}:registry:workers` |
| 心跳时间戳 | ZSET | `crawlo:{ns}:registry:heartbeats` |
| 请求去重 | SET | `crawlo:{ns}:dedup:request` |
| 数据项去重 | SET | `crawlo:{ns}:dedup:item` |
| 全局统计 | HASH | `crawlo:{ns}:progress:stats` |
| 域名限速 | STRING + Lua | `crawlo:{ns}:rate:{domain}` |
| Failover 互斥锁 | STRING | `crawlo:{ns}:lock:failover` |
| Leader 选举锁 | STRING | `crawlo:{ns}:lock:leader` |
| 种子生成器锁 | STRING | `crawlo:{ns}:seed:generator` |
| 控制状态 | STRING | `crawlo:{ns}:control:state` |
| 动态配置 | HASH | `crawlo:{ns}:config:rate_limits` 等 |
| Pub/Sub 控制通道 | PUBSUB | `crawlo:{ns}:channel:control` |
| Pub/Sub 配置通道 | PUBSUB | `crawlo:{ns}:channel:config` |
| Pub/Sub 事件通道 | PUBSUB | `crawlo:{ns}:channel:events` |
| Pub/Sub 告警通道 | PUBSUB | `crawlo:{ns}:channel:alerts` |

### 14.3 修订记录

相比 [v2-design.md](v2-design.md) 原版的修正：

| # | 原版 | 本版 | 理由 |
|---|---|---|---|
| 1 | Redis Key 无命名空间前缀 | 增加 `redis_namespace` 字段，所有 Key 按 `crawlo:{ns}:{suffix}` 拼接 | Crawlo 内部所有 Redis Key 都带 `{project}:{spider}` 前缀 |
| 2 | `REDIS_URL` 环境变量 | 拆解为 `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` / `REDIS_DB` 分散配置 | Crawlo 没有 `REDIS_URL` 配置项 |
| 3 | `SPIDER_NAME` / `PROJECT_NAME` 环境变量 | 改用 `--settings` 参数 + settings override 文件 | Crawlo 不通过环境变量传递这些配置 |
| 4 | 纯环境变量传递配置 | 生成临时 settings override 文件 | Crawlo 配置体系以 settings.py 文件为主 |
| 5 | `os.wait()` 等待子进程 | 改为 `for p in processes: p.wait()` | `os.wait()` 只等待第一个子进程 |
| 6 | 心跳 TTL 30s | 改为 60s | 对齐 Crawlo 15s 心跳节奏，覆盖 2 次周期 |
| 7 | 未说明 auto 模式定位 | 新增 §3.0 说明跳过 auto 模式的理由 | auto 模式无 ACK，数据可能丢失 |
| 8 | 版本要求未明确 | 明确 `crawlo >= 1.7.3` | 1.7.3 分布式组件才完全稳定 |
| 9 | AlertManager 5 条规则 | 扩展至 7 条，补充队列积压和去重集合过大 | 充分利用 Crawlo 已有指标 |
| 10 | 完成信号仅 Pub/Sub 订阅 | 增加 `control:state` 持久化 Key 轮询兜底 | 双通道保证，防止 Pub/Sub 消息丢失 |

### 14.4 参考资料

- [v2-design.md](v2-design.md)：V2 设计原版
- [DESIGN-ISSUES.md](../DESIGN-ISSUES.md)：V1 问题清单
- [docs/design-philosophy.md](design-philosophy.md)：V1 设计哲学
- Crawlo 分布式架构：`/Users/oscar/projects/Crawlo/docs/distributed_architecture.md`
- Crawlo 集群模块：`/Users/oscar/projects/Crawlo/crawlo/cluster/`
- Crawlo RedisStreamQueue：`/Users/oscar/projects/Crawlo/crawlo/queue/backends/redis_stream.py`
- Crawlo 默认配置：`/Users/oscar/projects/Crawlo/crawlo/settings/default_settings.py`
- Crawlo 集群协调器：`/Users/oscar/projects/Crawlo/crawlo/cluster/coordinator.py`
