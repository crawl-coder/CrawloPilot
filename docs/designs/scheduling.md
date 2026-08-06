# 定时任务配置功能设计

> 状态：设计稿（待评审）
> 关联文档：[设计哲学](../DESIGN_PHILOSOPHY.md)、[任务管理](../modules/06-tasks.md)、[部署执行](../modules/04-execution.md)

## 1. 目标与范围

让用户能够为爬虫配置**定时触发规则**，由平台在后台按规则自动创建并执行任务，
执行链路（状态/日志/指标/停止）完全复用现有四种执行器。

V1 范围：

- 三种触发类型：**Cron 表达式 / 固定间隔 / 一次性**（依赖触发 DEPENDENCY 仅保留枚举，不实现）
- 调度管理：创建、编辑、删除、启用/停用、立即执行一次、运行历史
- 并发守卫：同一调度同时最多 N 个运行中任务（默认 1，防止重叠执行）
- 时区：默认 `Asia/Shanghai`，支持按调度指定

不做（后续版本）：跨实例分布式调度（互斥已有方案，见第 4 节）、调度成功率告警。

## 2. 页面归属（回答"定时任务在哪个页面"）

**主入口：独立「定时任务」页面（一级菜单，位于「任务管理」之后）**，
**辅助入口：爬虫详情页提供"为此爬虫新建定时任务"快捷按钮（预填爬虫）**。

理由：

- 定时任务是"任务"的配置形态，与任务管理同域；全局列表便于查看所有调度与运行情况；
- 若只放在爬虫管理内，跨爬虫汇总（哪些任务在跑、各自周期）非常困难；
- 爬虫详情页的快捷入口解决"从爬虫出发"的使用习惯，避免割裂。

页面导航最终形态：

```text
仪表盘 / 项目管理 / 爬虫管理 / 任务管理 / 定时任务 / 节点管理 / 系统
```

## 3. 数据模型

复用现有 `schedule` 表并修正缺陷：当前表存 `spider_name` 而不是 `spider_id`，
无法可靠关联爬虫（重名、改名都会断裂），必须改为外键。

```python
class Schedule(Base):
    __tablename__ = "schedule"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128))                    # 调度名称（可空，默认"爬虫名-周期"）
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    spider_id = Column(BigInteger, ForeignKey("spider.id"), nullable=False)   # 新增
    spider_name = Column(String(128))             # 冗余展示字段（随爬虫同步）
    node_id = Column(BigInteger, ForeignKey("node.id"), nullable=True)        # None=本地执行

    schedule_type = Column(Enum(ScheduleType))    # cron / interval / once
    cron_expr = Column(String(64))                # 5 段标准 cron（按 timezone 解释）
    interval_seconds = Column(Integer)            # interval 秒数
    run_at = Column(DateTime)                     # once 的执行时间
    timezone = Column(String(64), default="Asia/Shanghai")

    max_concurrency = Column(Integer, default=1)  # 同一调度最多并发运行数
    timeout_seconds = Column(Integer, default=3600)
    description = Column(Text)
    enabled = Column(Boolean, default=True)

    next_run_time = Column(DateTime)              # 调度引擎回写，供列表展示
    last_run_at = Column(DateTime)
    last_run_status = Column(String(32))
    last_run_task_id = Column(BigInteger)
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)

    created_by = Column(BigInteger, ForeignKey("user.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

> 迁移：`alembic` 新增列 `spider_id / name / run_at / timezone / run_count / ...`；
> 存量行按 `spider_name` 匹配回填 `spider_id`，匹配不到的行标记禁用并提示。

`task_instance.schedule_id` 已存在，运行历史天然通过它关联调度。

## 4. 调度引擎（进程内 APScheduler）

**采用进程内 APScheduler 3.10（已在依赖中），不引入 Celery。**

- 随 FastAPI lifespan 启动 `BackgroundScheduler`（timezone=Asia/Shanghai）；
- 启动时从 DB 加载所有 `enabled` 调度注册为 job；API 变更（增删改/启停）通过
  `SchedulerService` 热更新，避免重启；
- 每个 job 一个稳定 job_id（`schedule-{id}`），避免重复注册；
- 触发后执行 `_run_schedule(schedule_id)`：
  1. 校验：爬虫存在且未禁用、代码目录存在、节点在线（若指定）
  2. 并发守卫：统计该 `schedule_id` 下 `running` 任务数 >= max_concurrency → 跳过并记日志
  3. 创建 `TaskInstance(schedule_id=..., spider_id=..., node_id=...)`
  4. 复用任务创建/分发公共 service（见第 6 节）
  5. 回写 `last_run_*`、`next_run_time`
- 错过执行：`misfire_grace_time=60s`，超时则跳过本次（一次性任务标记 skipped，不追跑）。

### 补偿机制（设计硬性要求）

**机制一：启动时的错跑检测（DB 驱动）**

进程内 APScheduler 的 job 只存在于内存，后端重启/宕机期间到点的触发会丢失。
因此启动时除"从 DB 重建 job"外，还必须做错跑检测：

1. 扫描所有 `enabled` 调度，找出 `next_run_time` 已过期、且当前时间落在
   `[next_run_time, next_run_time + 补偿窗口]` 内的调度；
2. 按配置策略处理：
   - 默认：**记录为 skipped**（写 `last_run_status=skipped`，不执行，避免追跑堆积）；
   - 可选：**补跑一次**（`run-now` 语义，仅对 cron/interval 生效，once 直接 skipped）；
3. 处理后按规则推进 `next_run_time`，保证不重复补偿。

补偿窗口默认 24h（可配置），超过窗口的旧错过不再处理，只更新 `next_run_time`。

**机制二：触发幂等 / 多实例互斥**

触发入口必须幂等，防止以下两类重复：

- 同一实例因重试或双 fire 产生重复任务；
- 多实例各自运行调度器时，同一 cron 被触发多次。

实现（二选一，推荐 GET_LOCK）：

1. **MySQL `GET_LOCK`**：触发时以 `schedule-{id}-{期望触发时间戳}` 为锁名加锁，
   拿到锁才创建任务，执行完释放；天然兼容多实例；
2. **唯一约束**：`task_instance` 增加 `(schedule_id, expected_run_at)` 唯一索引
   （新增列 `expected_run_at`），重复创建被数据库拒绝。

任选其一即可满足"一次触发最多创建一个任务"。

> 前端提示/运行记录层面，任务来源统一带 `triggered_by="schedule"` 与
> `schedule_id`，便于排查重复。

### 多实例说明

V1 假设**单实例控制面**（调度器只跑一个）。多实例部署时：

- 方案 A（简单）：调度器只在主实例启用（环境变量 `ENABLE_SCHEDULER=true`）；
- 方案 B（推荐）：配合机制二的 `GET_LOCK`，允许每实例都跑调度器，
  由锁保证一次触发只被一个实例消费（无需主从配置）。

设计哲学一致：先保证单实例正确，再谈分布式。

### APScheduler 适用边界与升级路径

进程内 APScheduler 的**有效边界：单实例（或互斥后多实例）+ 容忍分钟级重启窗口**。

- 边界内：V1/V2 完全覆盖，成本最低；
- 出现"绝不能漏跑"或"双活控制面"硬需求时，升级为**独立调度器**：
  把 APScheduler 放进独立进程/容器（仍不引入 Celery），触发逻辑不变
  （纯 DB 操作 + `task_service.create_and_run_task` 调用），迁移成本低；
- 出现海量任务队列/背压/重试需求时，才评估 Celery（beat + worker），
  且需重构执行层——V3 之后的议题。

## 5. API 设计

```text
GET    /api/v1/schedules                    列表（筛选 project_id / spider_id / status / 分页）
POST   /api/v1/schedules                    创建（返回创建的调度）
GET    /api/v1/schedules/{id}               详情
PUT    /api/v1/schedules/{id}               更新（触发规则/节点/并发/开关等）
DELETE /api/v1/schedules/{id}               删除（同时移除 job 与关联关系）
POST   /api/v1/schedules/{id}/enable        启用（重新注册 job）
POST   /api/v1/schedules/{id}/disable       停用（移除 job，保留配置）
POST   /api/v1/schedules/{id}/run-now       立即执行一次（不改变周期）
GET    /api/v1/schedules/preview            预览下次 N 次运行时间
       ?schedule_type=cron&cron_expr=...&timezone=...
GET    /api/v1/schedules/{id}/history       运行历史（按 schedule_id 过滤任务列表）
```

创建/更新请求体示例：

```json
{
  "name": "ofweek 每2小时",
  "spider_id": 1,
  "node_id": null,
  "schedule_type": "cron",
  "cron_expr": "0 */2 * * *",
  "timezone": "Asia/Shanghai",
  "max_concurrency": 1,
  "timeout_seconds": 3600,
  "enabled": true
}
```

校验规则：

- `cron` 必须合法 5 段表达式（服务端解析失败返回 400）；
- `interval` 需 `interval_seconds >= 60`；
- `once` 需 `run_at` 未来时间；
- 爬虫必须存在；节点若指定必须存在（在线校验放在触发时，避免创建时误伤离线节点）。

## 6. 与现有执行链路复用

当前 `run_spider`（[spiders.py](../../backend/app/api/v1/spiders.py)）内聚了：

1. 校验爬虫/代码目录/节点
2. 创建 TaskInstance
3. 按节点 `connect_type` 分发到 local / ssh / docker / agent 执行器

设计上把这部分抽成公共服务：

```python
# app/services/task_service.py
def create_and_run_task(db, spider_id, node_id=None, schedule_id=None,
                        triggered_by="manual") -> TaskInstance:
    """创建任务并按节点分发（手动运行与定时触发共用）"""
```

`run_spider` 与调度器都调用它，保证行为一致；调度触发带 `triggered_by="schedule"`、
`schedule_id`，便于任务列表区分来源与追溯。

## 7. 前端设计

### 7.1 定时任务列表页（`/schedules`）

```
┌────────────────────────────────────────────────────────────────┐
│ 定时任务                        [新建定时任务]                   │
│ 筛选: 项目 ▾  爬虫 ▾  状态 ▾                                     │
├──────┬────────┬────────┬────────┬────────┬──────────┬─────────┤
│ 名称 │ 爬虫   │ 类型    │ 节点   │ 下次运行 │ 上次运行/结果 │ 操作    │
│ ofweek│ of_week│ Cron   │ 本地   │ 08-06 16:00 │ 成功 08-06 14:00│ 详情/… │
│ ...  │        │ 每2h   │        │          │             │        │
└──────┴────────┴────────┴────────┴────────┴──────────┴─────────┘
```

- 类型列展示：`Cron 0 */2 * * *` / `间隔 30分钟` / `一次性 08-07 09:00`
- 启用/停用开关即时生效（调用 enable/disable API）
- 操作：编辑、立即执行、启用/停用、删除（确认弹窗）、运行历史
- 行点击或"历史"打开抽屉：展示该调度最近任务（复用任务列表数据，跳转任务详情）

### 7.2 新建/编辑表单（弹窗或抽屉，分步）

1. **选择爬虫**：项目 → 爬虫下拉（展示爬虫名、入口文件、代码目录是否存在）
2. **触发规则**：
   - Cron：表达式输入 + 说明 + **实时预览下次 5 次运行时间**
   - 间隔：数字输入（分钟/秒换算）
   - 一次性：日期时间选择器
   - 时区选择（默认 Asia/Shanghai）
3. **执行设置**：节点下拉（空=本地）、超时时间、最大并发
4. 确认：展示"下一次运行时间"摘要

### 7.3 入口与改造

- 新增路由 `/schedules` + 侧边栏一级菜单（任务管理之后）
- 爬虫详情页（SpiderDetail.vue）增加"定时任务"按钮 → 跳转新建页并预填 `spider_id`
- 任务管理页（Tasks.vue）："调度ID"列可点击跳转对应调度
- **移除爬虫创建表单中的半成品调度字段**（[Spiders.vue](../../frontend/src/views/Spiders.vue)
  的 `schedule_enabled / cron_expr / timeout_seconds / retry_count`），避免双入口混乱；
  定时配置统一走新页面

## 8. 测试策略

### 后端

- 单测：cron 解析与预览、非法表达式 400、间隔/一次性校验、并发守卫、missed 跳过
- 集成：创建 `interval=10s` 调度 → 等待 2 个周期 → 断言生成 2 个成功任务；
  disable 后不再触发；`run-now` 立即生成任务且不改周期；删除调度后 job 移除
- 时区：配置 `Asia/Shanghai` 的 cron 按本地时间触发断言

### 前端

- 表单校验（cron 合法性、间隔下限、一次性未来时间）
- cron 预览正确展示下次 5 次
- 启用/停用/立即执行/删除交互与列表刷新

## 9. 实施步骤拆分

1. 数据模型：Schedule 表改造 + `task_instance.expected_run_at` 列 +
   alembic 迁移 + 存量数据回填
2. `SchedulerService`（APScheduler 集成）+ lifespan 启停 +
   **启动错跑检测（机制一）** + `task_service.create_and_run_task` 抽取
3. 触发链路**幂等/互斥（机制二：GET_LOCK 或唯一索引）** + 并发守卫
4. `/schedules` API（CRUD/启停/run-now/预览/历史）
5. 前端：列表页 + 表单 + 路由/菜单 + 爬虫详情入口
6. 清理 Spiders.vue 残留调度字段
7. 测试（后端单测/集成 + 前端，含错跑检测与重复触发用例）
