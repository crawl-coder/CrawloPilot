# CrawloPilot V2 设计方案

> 版本：V2.0（草案）
> 日期：2026-08-07
> 作者：架构评审
> 状态：待评审
> 关联文档：[DESIGN-ISSUES.md](../DESIGN-ISSUES.md)、[docs/design-philosophy.md](design-philosophy.md)

---

## 一、定位与愿景

### 1.1 V2 定位

**分布式爬虫编排平台**（Distributed Crawler Orchestration Platform）。

V1 自称"Crawlo 爬虫框架的管理部署平台"，实际代码已支持 Crawlo / Scrapy / Selenium / Playwright / Requests / Custom 六种类型，定位与实现脱节。V2 明确定位为**框架无关的分布式爬虫编排平台**，Crawlo 仅作为推荐默认引擎。

### 1.2 目标用户

5-20 人中型爬虫团队，典型场景：

- 同时维护 20-200 个爬虫项目
- 部署在 3-10 台节点
- 需要告警、代理池、日志聚合、审计
- 需要多成员协作 + 操作可追溯

### 1.3 V2 核心目标

| 目标 | V1 现状 | V2 目标 |
|---|---|---|
| 状态管理 | 执行器直写 DB + 内存 active_tasks | TaskStateStore 统一中间层 |
| 多实例 | 单实例硬约束 | 水平扩展 |
| 执行器契约 | 口头约定 | Protocol + ABC |
| Agent 通信 | HTTP 轮询 5s | MessageBus 长连接推送 |
| 可观测性 | 无 | 告警 + 日志聚合 + 指标 |
| 安全 | 单密钥 + token in URL | 双密钥 + Bearer + 审计 |
| 生态扩展 | 无 | 代理池 + Webhook |

### 1.4 非目标

V2 **不做**以下事项，留给 V3：

- 多租户 / 工作空间隔离
- 数据质量监控（V1 已取消，V2 不恢复）
- 可视化爬虫编排（DAG 拖拽）
- 爬虫代码在线 IDE

---

## 二、与 V1 的差异对比

### 2.1 架构层面

| 维度 | V1 | V2 |
|---|---|---|
| 状态写入 | 执行器直写 DB | 经 TaskStateStore |
| 任务状态机 | 应用层终态保护 | DB 条件 UPDATE 原子 |
| 调度器 | APScheduler 进程内 | Celery Beat 独立服务 + DB 锁 |
| Agent 通信 | HTTP 轮询 | Redis Streams 推送 |
| 日志存储 | 文件 + 容器卷 | Loki 聚合 |
| 告警 | 无 | AlertManager + Webhook |
| 代理池 | 无 | ProxyPool 微服务 |
| 密钥管理 | 单 SECRET_KEY 共用 | JWT / 凭据加密分离 |
| 审计 | 无 | AuditLog 模块 |

### 2.2 兼容性策略

V2 采用**演进式重构**，不重写：

- API 路径保持 `/api/v1/*`（不升 v2，避免前端破坏）
- 数据库 schema 增量迁移，不重建
- V1 的 4 个执行器全部保留，逐步适配 Protocol
- Agent 协议升级走版本协商（V1 agent 仍可连接，但功能降级）

---

## 三、整体架构

### 3.1 分层视图

```
┌─────────────────────────────────────────────────────┐
│  用户 / Agent / Webhook                             │
└─────────────────────────────────────────────────────┘
                         │
┌──────────────────────────────┬──────────────────────┐
│ 控制面 Control Plane         │ 执行面 Execution      │
│  ┌─────────┐ ┌─────────┐    │  ┌Executor Protocol┐ │
│  │ API网关 │ │ 调度器  │    │  │ Local/SSH/Docker│ │
│  └─────────┘ └─────────┘    │  │ Agent(MQ驱动)   │ │
│  ┌────────────────────────┐ │  └─────────────────┘ │
│  │ TaskStateStore (核心)  │◄┼──────────────────────┤
│  │ 条件UPDATE·原子状态机  │ │                       │
│  └────────────────────────┘ │                       │
└──────────────┬───────────────┴───────────────────────┘
               │
┌──────────────┴──────────────────────────────────────┐
│ 数据面                │ 可观测 + 生态                │
│  MySQL · Redis · Loki │  AlertManager · ProxyPool    │
└──────────────────────────────────────────────────────┘
               │
┌──────────────┴──────────────────────────────────────┐
│ 横切：Auth(双密钥) · AuditLog · Prometheus · Webhook│
└─────────────────────────────────────────────────────┘
```

### 3.2 核心改进点

1. **TaskStateStore**：所有任务状态变更的唯一入口，执行器不再持有 DB session
2. **Executor Protocol**：定义抽象基类，编译期检查契约
3. **MessageBus**：基于 Redis Streams，替代 Agent HTTP 轮询
4. **AlertManager**：规则引擎 + 多通道告警（Webhook / 飞书 / 邮件）
5. **ProxyPool**：独立微服务，提供代理获取 / 健康检查 / 计费
6. **LogAggregator**：基于 Loki + Promtail，统一日志查询
7. **AuditLog**：所有写操作记录操作者 / 时间 / 变更前后值

---

## 四、核心模块设计

### 4.1 TaskStateStore（状态中间层）

**职责**：任务状态变更的唯一入口，保证原子性 + 多实例安全。

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
        返回 True 表示转换成功，False 表示状态已变（被其他实例抢先）。"""

    async def heartbeat(self, task_id: int, metrics: dict) -> None:
        """执行器心跳上报。Redis TTL 30s，过期由 reaper 回收。"""

    async def append_log(self, task_id: int, line: str, level: str) -> None:
        """日志写入 Loki + Redis 缓冲。"""

    async def update_stats(self, task_id: int, stats: dict) -> None:
        """更新爬虫统计（items_count / pages_count 等）。"""
```

**实现要点**：

- DB 层：`UPDATE task_instance SET status=:to WHERE id=:id AND status IN (:from)` 让数据库保证原子性
- 心跳：Redis `task:heartbeat:{task_id}` TTL 30s，过期触发 reaper 任务回收
- 多实例：状态机无共享，多个控制面实例可同时写不冲突
- 审计：每次 transition 记录到 AuditLog

**消除 V1 痛点**：

- 不再有 `active_tasks` 内存字典（重启丢失问题）
- 不再有应用层 TOCTOU 竞态
- 4 个执行器的 `_update_task_completion` 复制粘贴统一到这里

### 4.2 Executor Protocol（执行器契约）

```python
class Executor(Protocol):
    """所有执行器必须实现的契约。编译期检查。"""

    @property
    def mode(self) -> DeployMode: ...

    async def execute_task(self, task: TaskInstance) -> None:
        """启动任务（异步，立即返回）。状态变更走 TaskStateStore。"""

    def get_task_status(self, task_id: int) -> TaskStatus:
        """同步查询任务当前状态（从 TaskStateStore 读，不直接读 DB）。"""

    def get_task_logs(self, task_id: int, tail: int = 200) -> list[LogEntry]:
        """获取日志。统一返回 LogEntry 列表，不再返回字符串错误。"""

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
| LocalExecutor | ✓ | ✓ | ✓ | ✓ | ✓（改用 SIGSTOP + 子进程组） |
| SshExecutor | ✓ | ✓ | ✓ | ✓ | ✗（不实现，路由层拒绝） |
| DockerExecutor | ✓ | ✓ | ✓ | ✓ | ✗ |
| AgentExecutor | ✓（push 模式） | ✓ | ✓ | ✓ | ✗ |

**LocalExecutor 暂停修复**：V1 用 `os.kill(pid, SIGSTOP)` 只暂停主进程，子线程仍占用资源。V2 改为暂停整个进程组 `os.killpg(os.getpgid(pid), SIGSTOP)`，并通过 TaskStateStore 标记状态而非本地字典。

### 4.3 MessageBus（替代 HTTP 轮询）

**V1 问题**：Agent 每 5s `GET /tasks`，N 个 agent = 0.2N 次/秒 DB 查询，规模化时 DB 压力线性增长。

**V2 方案**：基于 Redis Streams。

```
控制面 → Redis Stream "task:dispatch:{node_id}" → Agent 长阻塞读取（XREADGROUP BLOCK 30000）
Agent  → Redis Stream "task:report:{node_id}"    → 控制面消费组读取
```

**协议**：

```python
# 控制面下发任务
await redis.xadd(
    f"task:dispatch:{node_id}",
    {"task_id": task_id, "action": "execute", "code_url": "..."},
)

# Agent 阻塞读取（最长 30s）
messages = await redis.xreadgroup(
    groupname="agents",
    consumername=node_id,
    streams={f"task:dispatch:{node_id}": ">"},
    block=30000,  # 长轮询
    count=1,
)
```

**优势**：

- 空载 Agent 30s 才发一次请求，DB 压力降 99%
- 任务下发延迟从 5s 降到 <100ms
- 天然支持多 Agent 负载均衡（消费组）
- Redis 已是 V2 必备组件（TaskStateStore 心跳），无新增依赖

**降级策略**：Agent 启动时若 Redis 不可达，回退到 HTTP 轮询模式（兼容 V1）。

### 4.4 AlertManager（告警引擎）

**规则模型**：

```python
class AlertRule(BaseModel):
    id: int
    name: str
    enabled: bool
    # 触发条件
    metric: str  # "task_failed_count" / "task_duration" / "spider_error_rate"
    operator: str  # ">" / "<" / "==" 
    threshold: float
    window_minutes: int  # 时间窗口
    # 通知配置
    channels: list[str]  # ["webhook", "feishu", "email"]
    cooldown_minutes: int  # 告警冷却，避免轰炸
    # 目标范围
    spider_id: int | None  # None = 全局
    node_id: int | None
```

**内置规则**：

| 规则 | 默认阈值 | 窗口 |
|---|---|---|
| 任务失败 | 连续 3 次 | 1h |
| 任务超时 | > 30 分钟 | 实时 |
| 节点离线 | 心跳超 60s | 实时 |
| 爬虫错误率 | > 10% | 5min |
| 代理池告罄 | < 10 个可用 | 实时 |

**通道**：

- Webhook（通用，用户自定义）
- 飞书（lark-im 集成）
- 邮件（SMTP）

### 4.5 ProxyPool（代理池服务）

**独立微服务**，与控制面解耦，通过 HTTP API 交互。

**核心接口**：

```
GET  /proxies/acquire?spider_id=X&count=1   # 获取代理
POST /proxies/release                        # 释放代理
POST /proxies/report                         # 上报代理质量
GET  /proxies/stats                          # 代理池统计
```

**代理来源**：

1. 自有代理（用户上传）
2. 第三方 API（芝麻代理 / 快代理等，配置化接入）
3. 自建代理（爬取免费代理 + 健康检查，质量低但免费）

**健康检查**：后台任务每 5 分钟检测所有代理可用性，淘汰失效代理。

**与爬虫集成**：

- Crawlo 框架：通过 `PROXY_POOL_URL` 环境变量注入
- Scrapy：通过 middlewares 接入
- 自定义：HTTP API 调用

### 4.6 LogAggregator（日志聚合）

**V1 问题**：多节点部署后，日志散落在各节点文件，排查需 SSH 登录。

**V2 方案**：Loki + Promtail。

```
Agent/Executor → stdout → Promtail 采集 → Loki 存储 → API 网关查询
```

- 容器化部署：Docker Executor 直接走 stdout，Promtail 采集 docker logs
- 本地部署：LocalExecutor 日志写文件，Promtail tail 采集
- SSH 部署：在节点部署 Promtail，采集远程日志
- Agent 模式：Agent 上报日志走 MessageBus，控制面写入 Loki

**查询接口**：

```
GET /api/v1/tasks/{task_id}/logs?tail=200&level=ERROR&since=1h
```

后端转发到 Loki LogQL 查询。

### 4.7 AuditLog（审计日志）

**记录范围**：所有写操作（创建/更新/删除/启停）。

```python
class AuditLog(BaseModel):
    id: int
    user_id: int | None  # None 表示系统操作
    action: str  # "task.create" / "spider.update" / "credential.delete"
    resource_type: str  # "task" / "spider" / "node"
    resource_id: int
    before: dict | None  # 变更前快照
    after: dict | None   # 变更后快照
    ip: str
    user_agent: str
    created_at: datetime
```

**存储**：单独 `audit_logs` 表，按月分区，保留 1 年（可配置）。

**查询接口**：`GET /api/v1/audit-logs?user_id=&action=&resource_type=&since=`

---

## 五、关键技术选型

| 模块 | 选型 | 理由 |
|---|---|---|
| 消息队列 | Redis Streams | 已依赖 Redis，无新增；长轮询 + 消费组 |
| 调度器 | Celery Beat 独立服务 | 多实例安全（DB 锁）；任务编排能力强 |
| 日志聚合 | Loki + Promtail | 比 ELK 轻 10 倍；与 Grafana 原生集成 |
| 指标 | Prometheus + Grafana | 行业标准；社区 dashboard 丰富 |
| 告警 | 自研 AlertManager + Alertmanager 兼容 | 业务规则复杂，复用 Prometheus 告警通道 |
| 代理池 | 独立 FastAPI 微服务 | 解耦；可独立部署/扩展 |
| 分布式锁 | Redis Redlock | 多实例调度器幂等 |
| 任务编排 | Celery Canvas（chain/group/chord） | 替代 APScheduler，支持任务依赖 |

**未选型说明**：

- **Kafka/NATS**：体量未到，Redis Streams 足够；未来流量 >10k msg/s 再迁移
- **Temporal/Airflow**：太重，爬虫编排不需要复杂 DAG
- **Elasticsearch**：日志量未到 ELK 级别，Loki 更轻

---

## 六、数据模型变更

### 6.1 新增表

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
    source VARCHAR(32) NOT NULL,  # "self" / "thirdparty" / "free"
    region VARCHAR(32),
    is_available BOOLEAN DEFAULT TRUE,
    last_check_at DATETIME,
    success_count INT DEFAULT 0,
    fail_count INT DEFAULT 0,
    avg_response_ms INT,
    created_at DATETIME NOT NULL
);
```

### 6.2 修改表

```sql
-- task_instance: deploy_mode 改为 ENUM
ALTER TABLE task_instance 
    MODIFY COLUMN deploy_mode 
    ENUM('local','ssh','docker','agent') NOT NULL;

-- task_instance: 新增 heartbeat_at
ALTER TABLE task_instance 
    ADD COLUMN heartbeat_at DATETIME COMMENT '最后心跳时间，用于离线检测';

-- nodes: 新增 last_seen_at
ALTER TABLE nodes 
    ADD COLUMN last_seen_at DATETIME COMMENT 'Agent 最后在线时间';

-- spiders: 新增 alert_enabled
ALTER TABLE spiders 
    ADD COLUMN alert_enabled BOOLEAN DEFAULT TRUE;
```

### 6.3 迁移策略

- 新增表：直接创建，不影响 V1
- 修改表：`deploy_mode` 改 ENUM 需要先清理脏数据
- 提供 `alembic upgrade head` 一次性迁移脚本
- V1 → V2 升级需停机一次（约 10 分钟）

---

## 七、API 变更

### 7.1 新增 API

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

# Agent（V2 协议）
GET    /api/v1/agent/stream    # SSE 或 WebSocket 长连接（替代轮询）
POST   /api/v1/agent/heartbeat
```

### 7.2 修改 API

**Agent 鉴权统一改 Bearer**：

```diff
- GET /api/v1/nodes/agent/tasks?node_id=1&token=xxx
+ GET /api/v1/nodes/agent/tasks?node_id=1
+ Authorization: Bearer xxx
```

**日志查询增强**：

```diff
- GET /api/v1/tasks/{id}/logs
+ GET /api/v1/tasks/{id}/logs?tail=200&level=ERROR&since=1h
```

### 7.3 废弃 API

```
# V2 仍保留但标记 deprecated，V3 移除
GET /api/v1/nodes/agent/tasks  # 轮询模式（降级兼容）
```

---

## 八、演进路线

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

**交付**：V1.1 版本，安全可上生产。

### Phase 2：架构收敛（1-2 个月）

**目标**：解决状态散落 + 单实例约束。

| 任务 | 工作量 | 依赖 |
|---|---|---|
| 引入 Redis 基础设施 | 2h | - |
| 实现 TaskStateStore | 16h | Redis |
| 定义 Executor Protocol + 适配 4 执行器 | 24h | TaskStateStore |
| Agent 改 MessageBus（长轮询降级） | 16h | Redis Streams |
| 调度器拆分 Celery Beat + DB 锁 | 16h | - |
| 状态更新改 DB 条件 UPDATE | 8h | TaskStateStore |
| 迁移历史清理 + alembic 整合 | 8h | - |

**交付**：V2.0 版本，多实例可部署。

### Phase 3：平台化（3-6 个月）

**目标**：补齐分布式平台能力。

| 任务 | 工作量 | 优先级 |
|---|---|---|
| AlertManager + Webhook | 40h | P0 |
| Loki 日志聚合接入 | 24h | P0 |
| Prometheus 指标接入 | 16h | P0 |
| AuditLog 模块 | 24h | P1 |
| ProxyPool 微服务 | 40h | P1 |
| Grafana Dashboard 模板 | 8h | P2 |
| 飞书告警通道集成 | 8h | P2 |

**交付**：V2.1 版本，完整分布式平台。

---

## 九、风险与对策

| 风险 | 概率 | 影响 | 对策 |
|---|---|---|---|
| Redis 单点故障 | 中 | 高（任务下发中断） | Redis Sentinel 主从；Agent 降级 HTTP 轮询 |
| Celery Beat 多实例触发 | 低 | 中 | DB advisory lock 兜底；唯一索引幂等 |
| Loki 日志查询慢 | 低 | 中 | 索引 label 精简；保留期 30 天 |
| V1 升级 V2 数据迁移失败 | 中 | 高 | 全量备份 + 灰度升级 + 回滚脚本 |
| Agent 协议升级兼容性 | 中 | 中 | 版本协商；V1 agent 仍可连接但功能降级 |
| 代理池质量不稳 | 高 | 低 | 多源混合；健康检查；降级直连 |
| 团队学习成本 | 中 | 中 | 文档 + 示例 + 渐进式接入 |

---

## 十、验收标准

### 10.1 功能验收

- [ ] 4 个执行器全部适配 Executor Protocol，无契约违反
- [ ] TaskStateStore 成为唯一状态入口，执行器无 DB session
- [ ] Agent 通过 MessageBus 接收任务，延迟 < 1s
- [ ] 多实例部署（2 个控制面）任务不重复执行
- [ ] AlertManager 5 条内置规则全部触发验证通过
- [ ] Loki 日志查询响应 < 2s（10 万条日志）
- [ ] AuditLog 记录所有写操作，可按用户/资源/时间查询
- [ ] ProxyPool 可获取/释放代理，健康检查正常

### 10.2 非功能验收

- [ ] 安全：无默认密钥、无 token in URL、无命令注入、无路径穿越
- [ ] 性能：单实例支持 100 并发任务、50 个 Agent 在线
- [ ] 可用性：单节点故障不影响整体服务
- [ ] 可观测：所有关键指标暴露 Prometheus，有 Grafana Dashboard
- [ ] 文档：API 文档、部署文档、迁移文档齐全

### 10.3 兼容性验收

- [ ] V1 前端无需改动即可连接 V2 后端
- [ ] V1 Agent 可连接 V2 控制面（功能降级到 HTTP 轮询）
- [ ] V1 数据库可平滑迁移到 V2 schema

---

## 十一、里程碑

| 里程碑 | 时间 | 交付物 |
|---|---|---|
| M1: 止血完成 | +2 周 | V1.1 安全版本 |
| M2: 架构收敛 | +2 月 | V2.0 多实例版本 |
| M3: 可观测就绪 | +3 月 | V2.0.1 告警 + 日志聚合 |
| M4: 生态完整 | +6 月 | V2.1 完整平台 |

---

## 十二、附录

### 12.1 术语表

| 术语 | 含义 |
|---|---|
| 控制面 | 接收用户请求、调度任务、管理状态 |
| 执行面 | 实际运行爬虫的执行器集合 |
| 数据面 | 持久化存储（MySQL/Redis/Loki） |
| TaskStateStore | 任务状态中间层，唯一状态入口 |
| MessageBus | 基于 Redis Streams 的任务下发通道 |
| Agent | 部署在远程节点的代理进程 |

### 12.2 参考资料

- [DESIGN-ISSUES.md](../DESIGN-ISSUES.md)：V1 问题清单
- [docs/design-philosophy.md](design-philosophy.md)：V1 设计哲学
- Crawlab 架构：https://docs.crawlab.cn/
- Celery Beat 文档：https://docs.celeryq.dev/
- Loki 文档：https://grafana.com/docs/loki/
