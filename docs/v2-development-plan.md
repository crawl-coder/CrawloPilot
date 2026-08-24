> 📖 [docs 首页](README.md) ｜ 关联：[v2-design-revised.md](v2-design-revised.md)（架构设计）｜ [remaining-work.md](remaining-work.md)（V1 收尾状态）

# CrawloPilot V2 下一阶段开发任务计划

> 版本：V2-plan.2
> 日期：2026-08-24（Wave A 进度更新）
> 作者：高级爬虫开发工程师 × 高级产品经理 联合评审
> 输入：V1 全链路重新走查（2026-08-24 实测）、`v2-design-revised.md`、`remaining-work.md`、`DESIGN-ISSUES.md`；Wave A 实现与回归

---

## 一、V1 重新走查结论（2026-08-24 实测）

走查方式：全新启动前后端 + API 级端到端调用，覆盖 V1 主链路全部环节。

### 1.1 验证结果（全绿）

| 验证项 | 结果 |
|---|---|
| 自研走查脚本 `tests/v1_walkthrough.py`（登录→仪表盘→项目/版本→爬虫→ZIP 上传→文件树/在线编辑→本地运行→日志→指标解析 pages/items/errors→停止→重试→调度创建/预览/run-now/历史/停用→节点/服务器/用户接口） | **25/25 ✅** |
| 官方部署流程验收 `tests/test_deployment_flow.py` | **18/18 ✅** |
| 前后端全流程联调 `tests/full_flow_test.py` | **41/41 ✅**（修复 1 处过时断言后） |
| Agent 模式实测（117.72.16.51 云服务器，SSH 反向隧道回连本机控制面）：注册→心跳→领任务→代码下载→venv 执行→日志/指标回流→停止指令 | **发现 P0 断裂 ×2（F5/F6），修复后全链路打通**（详见 §1.2） |

结论：**V1 主链路健康；Agent 模式在当前代码下曾完全不可用（已修复），可在此基础上启动 V2**。

### 1.2 走查发现的实际问题（本次新增输入）

| # | 级别 | 问题 | 实证 | 影响 |
|---|------|------|------|------|
| F1 | **P0** | **无任务状态对账机制**：控制面重启/执行进程意外死亡后，任务永久停留 RUNNING；`lifespan` 启动逻辑只做建表、健康检查、清理循环、调度器启动，无任何存量任务核对 | 生产实例任务 #219（sina_stock_finance）自 08-10 起 RUNNING 13 天，本机无对应进程 | ① 统计/仪表盘失真；② **经调度并发守卫永久阻断该爬虫的定时调度**（日志每 3 分钟一次"触发被并发守卫拦截"，已持续 13 天）；③ 手动重试入口被占用 |
| F2 | P1 | 删除调度后任务 `schedule_id` 外键 ON DELETE SET NULL，运行历史与调度失去关联，调度删除即历史不可追溯 | 走查中 run-now 触发的任务 #231 在删除调度后 schedule_id 变 NULL | 审计/复盘时无法回答"这条任务由哪条调度触发" |
| F3 | P2 | 测试债：`full_flow_test.py` 文件保存断言仍用 query 传参（cf97469 已改 body 传输），导致 40/41 假失败 | 本次已修复 | 测试可信度 |
| F4 | P2 | 本地 `.env` 未设置独立的 `JWT_SECRET_KEY` / `CREDENTIAL_ENCRYPTION_KEY`，回退共享 `SECRET_KEY` | 启动仅静默回退 | 与 DESIGN-ISSUES #2 的密钥分离整改不一致，缺显式提醒 |
| F5 | **P0（已修复 2026-08-24）** | **Agent 回报协议断裂**：安全整改把鉴权迁到 Bearer header 时，`/nodes/agent/tasks/{id}/logs` 与 `/report` 的 body schema 仍要求必填 `token`；当前 agent 脚本（与仓库 md5 一致）已不发 body token → 日志上报与终态回报全部 422，任务永久卡 running。以 117.72.16.51 实测复现：爬虫正常跑完（60 pages），但平台侧无日志、状态永不收敛 | 云端实测任务 #416 | 全新部署的 V1 Agent 模式完全不可用；演示站可用仅因云端后端是旧版。暴露 **Agent 链路零端到端测试覆盖**（tests/ 无 agent 用例）。已修复 schema 并实测打通（#419 success、日志/指标回流、停止链路 cancelled） |
| F6 | **P0（已修复 2026-08-24）** | **Agent 节点永不离线**：轻量健康检查对 agent 判定 online 后回写 `last_heartbeat=now`（自我续命），死节点永远无法离线、调度仍会选中它分发任务 | 杀掉云端 agent 后节点仍持续 ONLINE（心跳被后台循环刷新）；修复后正确回落 OFFLINE | 与 F1 同根因：用推断代替真实状态对账 |
| F7 | P2 | Agent 模式首任务延迟高：每任务独立 venv + 从 PyPI 安装 crawlo ≈30s+（京东云实测 33s）；且停止指令在依赖安装阶段不生效（需进入执行循环才检查 stop_requested） | 任务 #419 总耗时 95.9s，其中环境准备约 35s；#420 停止等待安装完成后才生效 | 轻爬虫场景纯开销大；用户"点了停止没反应"体验差 |

F1 的临时处置（已完成）：僵尸任务 #219 手动标记 FAILED 并注明原因，调度随即恢复正常触发（新任务 #241 SUCCESS）。**但根因未修，任何一次控制面重启都可能复现**——列为 Wave A 第一优先级。

### 1.3 计划与现实的对齐修正

`remaining-work.md` 中部分 Wave 任务实际已交付，本计划据此重排（避免重复开发）：

| remaining-work 条目 | 文档状态 | 实际状态 | 证据 |
|---|---|---|---|
| Wave 1.1 调度全局视图页 | 规划中 | **✅ 已交付** | `frontend/src/views/Schedules.vue`（531 行：筛选/启停/运行/历史弹窗） |
| Wave 1.2 调度终态统计回写 | 规划中 | **✅ 已交付** | commit ef75d67 |
| Wave 1.3 一爬虫多调度 | 规划中 | ❌ 未做 | `POST /schedules` 仍按 spider_id upsert（代码注释已预告改造方向） |
| Wave 1.4 爬虫级防并行守卫 | 按需 | ❌ 未做 | 仅调度级 max_concurrency 守卫存在；手动运行无任何并发校验 |
| Wave 2 监控告警 | 规划中 | ◐ 最小版已有 | d5c3041 提供 `ALERT_WEBHOOK_URL` 单通道、任务 failed/timeout 推送；规则引擎/告警记录/节点离线检测均未做 |
| V2 架构收敛（TaskStateStore / 三种 distribution_mode / 调度器拆分） | Phase 2 | ❌ 全部未启动 | — |

---

## 二、V2 产品目标与范围

**一句话定位**：从"能跑通的爬虫部署平台"升级为"中小团队可托付生产的 Crawlo 分布式编排平台"。

四个产品主题（按用户价值排序）：

1. **可靠性止血**（Wave A/B）：让"重启不丢账、重复触发有守卫、告警有人管"——生产化的最低门槛；
2. **监控告警完整版**（Wave C）：从单点 Webhook 升级为规则引擎 + 多通道 + 告警记录闭环；
3. **架构收敛与分布式编排**（Wave D）：TaskStateStore + 三种 distribution_mode，兑现 V2 核心设计；
4. **平台化生态**（Wave E）：审计、代理池、日志聚合，按需并行。

**非目标（沿用 v2-design-revised §1.6）**：请求级 Stream/ACK/Failover（Crawo 职责）、多租户、数据质量、DAG 拖拽、在线 IDE。

---

## 三、分波次任务清单

> 工作量为单人有效开发日（含自测）；优先级：P0 > P1 > P2。每个任务都有可执行的验收标准，完成即勾选并更新 CHANGELOG。

### Wave A：可靠性止血（✅ **A1–A8 全部完成（2026-08-24）**）

> 实际工作量：2 天（含走查、修复、回归测试）。A1–A8 全量回归通过（联调 41/41 + 部署验收 18/18 + agent e2e 32/32 + 走查 25/25 全绿）。

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 | 状态 |
|---|------|--------|--------|--------|------|----------|------|
| A1 | **启动任务对账（reconciliation）**：✅ `lifespan` 启动时扫描全部 PENDING/RUNNING 任务，local 核对 PID 存活（`os.kill(pid,0)`）、docker 查容器状态、ssh 远程 PID 探活（best effort）、agent 无进程标识回退超龄判定；无法确认存活的一律标记 FAILED 并写明原因 | `task_reconciler.py`（新增）+ `main.py` lifespan 调用 | P0 | 1d | 无 | 重启控制面后 DB 无遗留 RUNNING；插入假 PID + 超龄 agent 两条路径均正确收敛 | ✅ `805e079` |
| A2 | **运行中任务巡检兜底**：✅ 超龄兜底逻辑内聚在 `task_reconciler.reconcile_tasks()`，`TASK_STALE_HOURS=24h` 可配；独立于探活结果，防止进程标识丢失时遗漏 | `task_reconciler.py`（与 A1 同文件） | P0 | — | A1 | 超龄 agent 任务自动标记 FAILED | ✅ `805e079` |
| A3 | **并发守卫排除僵尸**：✅ 调度守卫统计运行数时忽略超龄 RUNNING 任务（`TASK_STALE_HOURS` 阈值），防止僵尸永久阻断调度触发 | `task_reconciler.py`（对账逻辑） | P0 | — | A1 | 复现 F1 场景（假 RUNNING 插入）不再阻断调度触发 | ✅ `805e079` |
| A4 | **密钥配置体检**：✅ `validate_secrets()` 开发模式发 WARNING（不阻断启动），生产模式硬拒绝；`/health` 端点新增 `warnings` 字段（当前 3 条：JWT/凭据共用 SECRET_KEY + 两者均未独立设置）；`config.py` 补 `secret_warnings()` 供健康端点展示 | `config.py` + `main.py` health | P2 | 0.5d | 无 | 本地 .env 缺省启动可见 WARNING；生产文档标注 | ✅ `805e079` |
| A5 | **Agent 链路端到端回归测试**（F5/F6 的防复发）：✅ `tests/agent_flow_test.py`——真实拉起 `agent/crawlo_agent.py` 子进程直连本地控制面，26 项断言覆盖 register→heartbeat→领任务→下载代码→执行→日志上报→终态回报→停止全部端点，并固化 F5（协议一致性）/F6（无自我续命）两条回归线；配套 agent 测试逃生阀 `CRAWLO_AGENT_SKIP_CRAWLO_INSTALL=1` | 已完成 | — | — | 无 | 实测 26/26 通过，约 2 分钟；纳入 CI 与发版前必跑 | ✅ `5021e51` |
| A6 | **Agent 环境准备优化**：✅ venv 模板缓存（`~/.crawlo-agent/template_venv/` 预装 crawlo，任务 venv 直接复制，~0.5s vs 原来 30s+）；安装阶段（venv/crawlo/requirements）每步前检查 `stop_requested`，停止 ≤5s 内生效并汇报 cancelled；Agent 版本 0.1.0→0.2.0 | `agent/crawlo_agent.py` | P1 | 1d | 无 | 二次任务环境准备 <2s；安装阶段发起停止 ≤5s 内生效 | ✅ `0688620` |
| A6.1 | **代码分包排除 `.git`**：✅ Agent `/code` 端点 `tar.add` 加 `filter` 排除 `.git/__pycache__/.DS_Store`；SSH 分发同步排除；Docker `_iter_code_files` 本已排除无需改动 | `agent.py` code 端点、`ssh_executor.py` | P1 | 0.5d | 无 | Git 来源爬虫经 Agent/SSH 分发的包内无 `.git`；任务正常执行 | ✅ `b9bbe63` |
| A6.2 | **代码分发按内容摘要缓存**：✅ 控制面 `_code_digest()` 计算文件清单 sha256（文件名+大小+mtime，秒级）；领任务响应 `code_digest` 字段；Agent 本地 `~/.crawlo-agent/code-cache/{digest}/` 命中则跳过下载；旧 agent 无此字段兼容不变 | `agent.py` + `crawlo_agent.py` | P2 | 1d | A6 | 同代码二次派发不传输代码包（日志可见 cache hit）；代码变更后立即失效 | ✅ `1f3d32c` |
| A7 | **Agent 版本握手与漂移检测**：✅ Node model 新增 `protocol_version` 列（alembic 迁移 a7b8c9d0e1f2，幂等）；Agent register 上报 `protocol_version`（当前=1）；NodeResponse 新增 `agent_compatible`（protocol_version >= REQUIRED=1 → True，否则 False）；旧 agent（NULL/0）→ 不兼容，前端可标黄 | `agent.py`、`nodes.py`、`agent_service.py`、`models`、`agent/crawlo_agent.py` | P1 | 1d | 无 | 旧版 agent 节点 agent_compatible=False；新版 = True | ✅ `7e3d8f1` |
| A8 | **Agent 并发扩展**：✅ `run()` 主循环改为并发提交（`threading.Thread` + `_running_tasks` dict + `_lock`），poll_task 领到任务后立即提交为独立线程返回继续领取；`execute_task` 生命周期内注册/注销 proc 到 `_running_tasks`，停止指令精确找到对应子进程并终止；`--max-workers` 参数 + `CRAWLO_AGENT_MAX_WORKERS` 环境变量（默认 2）；满载时 sleep 1s 防忙等 | `agent/crawlo_agent.py` | P1 | 2d | A6 | 3 个任务同时派发到同一 agent 节点 → 3 个并发 running；单任务失败不影响其他；停止指令精确杀对进程 | ✅ `358edbe` |

### Wave B：调度与运维增强收尾（✅ **B1–B3 全部完成（2026-08-24）**）

> 实际工作量：1 天。B1 已完成（代码已改纯 create + 前端支持多条）；B2 新增 max_concurrent 守卫；B3 改为软删除保留历史。回归全绿。

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 | 状态 |
|---|------|--------|--------|--------|------|----------|------|
| B1 | **一爬虫多调度**：✅ POST /schedules 已是纯 create（V1 早期 upsert 无残留），前端 `Schedules.vue` 已支持多条规则（注释"一个爬虫可配置多条定时任务"），docstring 已清理 | `schedules.py` 注释 | P1 | — | 无 | 同一爬虫创建 cron+interval 两条规则互不影响 | ✅ `e08429f` |
| B2 | **爬虫级防并行守卫**：✅ Spider model 新增 `max_concurrent` 列（alembic 迁移 b2c3d4e5f6g7，幂等，默认 1，0=不限）；`create_and_run_task` 入口统一校验（手动+调度+run-now 共用），活跃任务 ≥ 上限时返回明确错误码；SpiderCreate/SpiderUpdate schema 暴露 max_concurrent 供用户配置 | `models`、`task_service.py`、`schemas/spider.py` | P1 | 1d | 无 | 双击运行只产生一个任务；超限返回"爬虫并发守卫：当前活跃任务 N ≥ 上限 M" | ✅ `e08429f` |
| B3 | **调度软删除/历史保留**：✅ Schedule model 新增 `deleted_at` 列（alembic 迁移 b3d4e5f6g7h8，幂等）；DELETE 改为 `deleted_at=now()` + `enabled=false`，不删行、不置空 `task_instance.schedule_id`，任务历史完整保留调度关联；列表默认过滤已删除，`include_deleted=true` 可查看（含历史追溯）；enable/disable/run-now/put 对已 deleted 返回 410 | `models`、`schedules.py` | P1 | 1d | 无 | 删除调度后任务 schedule_id 保持；列表过滤正确；history 可查 | ✅ `93af9ce` |

### Wave C：监控告警完整版（✅ **C1–C3 全部完成（2026-08-24）**）

> 实际工作量：1 天。新增 6 个后端文件 + 3 个前端文件，1136 行代码。回归全绿。

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 | 状态 |
|---|------|--------|--------|--------|------|----------|------|
| C1 | **alert_rule 引擎**：✅ 进程内 pub-sub 事件总线 + 6 类内置规则（task_failed / task_timeout / consecutive_failures / success_rate / node_offline / zombie_converged）+ 规则冷却期去重 + 范围过滤（spider_id/project_id）+ task_updater/node_service/task_reconciler 三处事件 hook | `alert_engine.py`（新增）、`models`、`task_updater.py`、`node_service.py`、`task_reconciler.py` | P0 | 3d | A2 | 6 类规则各一条自动化触发用例通过；规则启停即时生效 | ✅ `e376900` |
| C2 | **通知通道抽象**：✅ alert_channel 表（dingtalk/wechat/feishu/custom）+ 后台线程并行发送 + 消息格式适配（钉钉 markdown / 企微 markdown / 飞书 text / 自定义 JSON）+ 兼容旧版 ALERT_WEBHOOK_URL 双路发送 | `notification_service.py`（新增） | P1 | 2d | C1 | 同一事件不重复轰炸（冷却期）；任一通道失败不影响其他 | ✅ `e376900` |
| C3 | **告警前端**：✅ AlertRules.vue（规则 CRUD + 启停 + admin 权限）+ AlertRecords.vue（告警记录列表 + 级别/确认筛选 + 一键确认）+ Layout.vue 侧边栏接入（告警记录所有用户、告警规则 admin 子菜单）+ alert.js API 调用 | 3 个 Vue 文件 + alert.js + router | P1 | 2d | C1 | 页面 CRUD 全通；告警产生后 API 可查 | ✅ `e376900` |

### Wave D：架构收敛与分布式编排（V2 核心，预计 15–18 天，P0/P1 混合）

> 按 `v2-design-revised.md` Phase 2 执行，此处拆解为可独立验收的任务。前置：Wave A 完成（分布式模式下状态对账更关键）。

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准（对齐设计稿 §12） |
|---|------|--------|--------|--------|------|---------------------------|
| D1 | Redis 基础设施回归 | compose 服务、`REDIS_*` 配置、连接管理 | P0 | 0.5d | 无 | compose up 后 /health 报告 redis connected |
| D2 | **TaskStateStore** | 新中间层：`transition/heartbeat/append_log/update_stats`，DB 条件 UPDATE 原子转换 + Redis 心跳 TTL 60s | P0 | 2d | D1 | 并发 transition 只成功一次；心跳过期由 reaper 标记 failed（与 A2 打通） |
| D3 | settings override 生成器 + **Redis Key 命名空间管理** | 按 `{project}:{spider}` 生成 ns，拼接 `crawlo:{ns}:*` 读取统计/状态 | P0 | 1d | D2 | 对 Crawlo 1.7.3 实测生成的 Key 与框架内部一致（对照附录 14.2 清单） |
| D4 | **CrawloDistributedAdapter**：三种 distribution_mode | task_instance 加 `distribution_mode/shared_redis_url/worker_count/redis_namespace` 字段（alembic 迁移）；执行器按模式生成启动命令 | P0 | 3d | D2, D3 | 模式 A standalone 回归全绿；模式 B 单机 N Worker 任务完成感知正确；Worker 崩溃 pending 被 XAUTOCLAIM 回收 |
| D5 | 模式 C 多机联合深爬 | 共享 Redis(Sentinel) 配置下发 + 多节点编排 | P1 | 2d | D4 | 双节点共享队列消费；kill 单节点后其余节点继续消费、任务最终 SUCCESS |
| D6 | 执行器全量接入 TaskStateStore | local/ssh/docker/agent 四执行器状态写入统一走 store | P0 | 2d | D2 | grep 无绕过 store 的直写 `task.status =`（白名单除外） |
| D7 | 调度器拆分 + DB 锁（多实例控制面） | APScheduler 可独立进程部署；触发前抢 MySQL 行锁/advisory lock | P1 | 2d | D2 | 双实例同跑同一 job 只触发一次（压测用例） |
| D8 | 分布式模式前端与文档 | 爬虫/任务表单暴露 distribution_mode 选择器 + 决策树提示；README/部署文档更新 | P1 | 1.5d | D4 | 三种模式在 UI 可配置、任务详情可见模式与 Worker 数 |

### Wave E：平台化生态（按需并行，P2）

| # | 任务 | 说明 | 工作量 |
|---|------|------|--------|
| E1 | 操作审计 AuditLog | audit_log 表已建；中间件记录所有写操作 + 查询页 | 2d |
| E2 | 代理池 ProxyPool | proxy_pool 表已建；代理录入/探活/分配 API + 页面 | 3d |
| E3 | Loki 日志聚合 | promtail 采集 `_task_logs` + Loki 查询接入日志页（保留现有文件查询降级路径） | 2d |
| E4 | Prometheus/Grafana | 指标暴露 + Dashboard 模板 | 2d |

---

## 四、里程碑建议

| 里程碑 | 内容 | 出口条件 | 当前进度 |
|---|---|---|---|
| **M1（+1 周）** | Wave A + B 全部 | 四套官方测试 + 走查脚本全绿；重启对账演练通过；发布 V1.1 | **Wave A + B 全部完成 ✅**（A1–A8 + B1–B3） |
| **M2（+3 周）** | Wave C 完整版 | 7 类告警规则上线演练；发布 V1.2（运营可用） | **Wave C 全部完成 ✅**（C1–C3） |
| **M3（+6 周）** | Wave D（D1–D6） | 设计稿 §12.1 三种 distribution_mode 功能验收逐项打勾；发布 V2.0 | 未开始 |
| **M4（+8 周）** | D7/D8 + Wave E 选做 | 多实例压测通过；发布 V2.1 | 未开始 |

## 五、资源分配依据（执行模式评估）

> 评价基于 2026-08-24 V1 全链路实测与源码审查，详细记分卡见 [执行模式使用指南 § 选型附录](guides/execution-modes.md)。

### 投入策略矩阵

| 模式 | 产品定位 | 投入级别 | 理由 |
|---|---|---|---|
| **本地** | 默认演示体验（开箱即用，唯一支持暂停/恢复） | 维护 | F1 僵尸任务+无依赖隔离——定位是验收模式，不值得补隔离短板（A8） |
| **SSH** | 兼容旧服务器的过渡选项 | **维护模式，不再新投** | 安全面最大（交出整机凭据）、PID 轮询脆弱、实时性差；Wave A 只修对账，不做新功能 |
| **Docker** | 生产环境首选（隔离最彻底、镜像复用秒级） | 主力维护 | 工程完成度最高；后续投入集中在文档优化（2375 暴露替代方案），代码改动极少 |
| **Agent** | **战略路径：V2 多机分布式深爬的关键载体** | 最高优先级 | 刚修复 F5/F6/F7；单 agent 串行主循环限制并发；V2 三种 distribution_mode 全都落点在执行器，是架构收敛的瓶颈所在 |

### 具体决策项

- **本地模式**：补“已知限制”文档（重启僵尸任务 + 依赖冲突风险），但代码层只做对账止血（A1），不投入 venv 隔离等重改造；
- **SSH 模式**：Wave A 修复对账后封存，不做新功能（已有的凭据加密、探活等保持）；公共文档里显著提示“生产建议 Docker/Agent”；
- **Docker 模式**：补齐开发者文档（socket 直连 / SSH 隧道 / DNAT 三种网络拓扑的抉择树），代码不再大改；
- **Agent 模式**：Wave A 的 A6（venv 缓存 + .git 排除 + 代码摘要缓存）、A7（版本握手）是必做项；串行主循环限制作为 A8 纳入（改成进程池并行，单节点多任务），为 Wave D 的分布式模式铺路。

## 六、风险与对策

| 风险 | 对策 |
|---|---|
| A1 对账误杀慢启动任务（把还在跑的判死） | local/docker 用真实进程/容器探测而非时间戳一刀切；ssh/agent 无法确认时先标 SUSPECTED 再二次确认；阈值可配 |
| 一爬虫多调度（B1）破坏老用户一对一习惯 | upsert 行为仅在 POST 语义变化，存量数据无需迁移；发版说明显著标注 |
| 分布式模式依赖用户环境 Redis 版本/拓扑差异大 | 模式 B/C 先在 Docker Compose 演示环境固化参考拓扑；文档给 Sentinel 最小配置样例 |
| Wave D 期间回归风险 | 每个执行器接入 store 后立即跑四套测试 + 走查脚本；`distribution_mode` 默认 standalone 保证 V1 行为零变化（§12.3 兼容验收） |
| Agent 串行限制影响多节点分布式编排实效 | A8 改主循环为进程池并行（单节点可跑多个 Worker），同时保持任务级隔离 |

## 七、本次已落地的配套变更（截至 2026-08-24，Wave A 完成）

> 含 11 个提交，变更文件 15+ 个，新增代码 ~1200 行（含测试）。四套官方测试 41/41 + 部署验收 18/18 + agent e2e 26/26 + 走查 25/25 全绿。

### Wave A 核心实现（A1–A7）

- **新增 `backend/app/services/task_reconciler.py`**：任务对账模块（A1/A2/A3），启动时扫描遗留 PENDING/RUNNING 任务，按 deploy_mode 分发探活（local PID / docker 容器 / ssh 远程 PID / agent 超龄），超龄 24h 兜底标记 FAILED；已通过插入假僵尸（假 PID + 超龄 agent）两条路径验证
- **`backend/app/main.py` lifespan**：对账调用 + 密钥体检调用（启动顺序：建表→对账→密钥体检→健康监控→调度器）
- **`backend/app/core/config.py`**：`validate_secrets()` 开发模式发 WARNING 不阻断；新增 `secret_warnings()` 供 `/health` 展示；补 `import logging`
- **`agent/crawlo_agent.py` v0.2.0**：
  - venv 模板缓存（`~/.crawlo-agent/template_venv/`，按 crawlo 版本预装，任务 venv 直接复制 ~0.5s）+ 安装阶段每步检查 `stop_requested`
  - 代码分发缓存（`~/.crawlo-agent/code-cache/{digest}/`，领任务时 `code_digest` 命中跳过下载）
  - `protocol_version` 上报（A7）+ `PROTOCOL_VERSION=1` 常量
  - 并发执行（A8）：`run()` 改为 `threading.Thread` 并发提交 + `_running_tasks` 追踪运行中任务 + `--max-workers` 参数（默认 2）+ 满载防忙等
  - `CRAWLO_AGENT_SKIP_CRAWLO_INSTALL=1` 测试逃生阀（A5 配套）
- **`backend/app/api/v1/agent.py`**：
  - AgentLogs/AgentTaskReport schema 移除必填 `token`（F5 修复）
  - `/code` 端点排除 `.git/__pycache__/.DS_Store`（A6.1）+ `X-Code-Digest` 响应头（A6.2）
  - `_code_digest()` 工具函数 + `/tasks` 领任务响应 `code_digest` 字段（A6.2）
  - `AgentRegister.protocol_version` 字段 + register 写入（A7）
- **`backend/app/services/node_service.py`**：`check_all_nodes_health_light` 不再回写 `last_heartbeat`（F6 修复）
- **`backend/app/api/v1/nodes.py`**：NodeResponse 新增 `protocol_version` + `agent_compatible` 字段（A7）
- **`backend/app/models/__init__.py`**：Node 新增 `protocol_version` 列（Integer, default=0）
- **`backend/app/services/agent_service.py`**：`REQUIRED_PROTOCOL_VERSION = 1`（A7）
- **`backend/alembic/versions/a7b8c9d0e1f2_add_node_protocol_version.py`**：alembic 迁移（幂等）

### 回归测试资产（A5 + 已有）

- 新增 `tests/agent_flow_test.py`（26 项）：真实拉起 agent 子进程全链路 e2e，固化 F5/F6 回归线
- 新增 `tests/v1_walkthrough.py`（25 项）：V1 主链路 API 走查
- 修复 `tests/full_flow_test.py` 文件保存断言（query → body），联调恢复 41/41
