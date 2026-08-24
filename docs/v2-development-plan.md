> 📖 [docs 首页](README.md) ｜ 关联：[v2-design-revised.md](v2-design-revised.md)（架构设计）｜ [remaining-work.md](remaining-work.md)（V1 收尾状态）

# CrawloPilot V2 下一阶段开发任务计划

> 版本：V2-plan.1
> 日期：2026-08-24
> 作者：高级爬虫开发工程师 × 高级产品经理 联合评审
> 输入：V1 全链路重新走查（2026-08-24 实测）、`v2-design-revised.md`、`remaining-work.md`、`DESIGN-ISSUES.md`

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

### Wave A：可靠性止血（预计 4–5 天剩余，P0，立即启动；A5 已交付）

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 |
|---|------|--------|--------|--------|------|----------|
| A1 | **启动任务对账（reconciliation）**：`lifespan` 启动时扫描全部 PENDING/RUNNING 任务，local 模式核对 PID 进程存活、docker 核对容器状态、ssh 核对远程 PID、agent 询问节点；无法确认存活的一律标记 FAILED 并写明 `error_message`（"控制面重启对账"） | `main.py` lifespan + 各执行器补 `is_alive(task)` 类方法 | P0 | 1d | 无 | 重启控制面后 DB 无超龄 RUNNING（阈值如 >10min 且无心跳）；走查脚本新增"重启对账"用例通过 |
| A2 | **运行中任务巡检兜底**：后台每日/每小时巡检循环（复用 maintenance_loop 模式），把超过 `TASK_STALE_HOURS`（默认 24h）仍 RUNNING 的任务标记 FAILED | `maintenance_service.py` + 配置项 | P0 | 0.5d | A1 | 人为构造僵尸记录 → 一个巡检周期内被收敛；告警 Webhook 同步收到通知 |
| A3 | **并发守卫排除僵尸**（A1 的防御性补充）：调度守卫统计运行数时忽略"最后心跳/更新时间超阈值的 RUNNING 任务" | `scheduler_service._fire_schedule` | P0 | 0.5d | A1 | 复现 F1 场景（手工插入假 RUNNING）不再阻断调度触发 |
| A4 | **密钥配置体检**：`JWT_SECRET_KEY` / `CREDENTIAL_ENCRYPTION_KEY` 回退 SECRET_KEY 时启动打 WARNING 日志并在 `/health` 返回提示字段；`.env.example` 注释强化 | `config.py` / `main.py` health | P2 | 0.5d | 无 | 本地 .env 缺省启动可见 WARNING；生产文档标注 |
| A5 | **Agent 链路端到端回归测试**（F5/F6 的防复发）：✅ **已交付（2026-08-24）** `tests/agent_flow_test.py`——真实拉起 `agent/crawlo_agent.py` 子进程直连本地控制面，26 项断言覆盖 register→heartbeat→领任务→下载代码→执行→日志上报→终态回报→停止全部端点，并固化 F5（协议一致性）/F6（无自我续命）两条回归线；配套 agent 测试逃生阀 `CRAWLO_AGENT_SKIP_CRAWLO_INSTALL=1` | 已完成 | — | — | 无 | 实测 26/26 通过，约 2 分钟；纳入 CI 与发版前必跑 |
| A6 | **Agent 环境准备优化**：venv 模板缓存（按 crawlo 版本预装好复制即用，消除每任务 pip install）；执行循环前置的安装阶段响应停止指令（安装子进程可被 terminate） | `agent/crawlo_agent.py` | P1 | 1d | 无 | 二次任务环境准备 <2s；安装阶段发起停止 ≤5s 内生效 |
| A6.1 | **代码分包排除 `.git`**（走查发现）：Git 来源爬虫保留完整 `.git`，而控制面 `/nodes/agent/tasks/{id}/code` 用 `tar.add(code_dir)` 整目录打包——仓库全量历史被下发给每个执行节点（带宽浪费 + 代码历史暴露）；SSH 分发同理需核查。修复：打包时过滤 `.git`（及 `.DS_Store` 等），SSH/Docker 路径一并审计 | `agent.py` code 端点、`ssh_executor.py`、`docker_executor.py` | P1 | 0.5d | 无 | Git 来源爬虫经 Agent/SSH 分发的包内无 `.git`；任务正常执行；包体积显著下降 |
| A6.2 | **代码分发按内容摘要缓存**：同一 spider 代码不变时的重复全量传输（Agent 每次任务现打 tar.gz 全量下载）。方案：控制面计算代码目录摘要（如 `sha256(content manifest)`），任务元数据携带版本号，Agent 本地缓存命中则跳过下载（SSH/Docker 已分别有 PID 复用/镜像摘要复用，对齐其思路） | agent 协议（tasks/code 端点）、`crawlo_agent.py` | P2 | 1d | A6 | 同代码二次派发不再传输代码包（日志可见 cache hit）；代码变更后立即失效 |
| A7 | **Agent 版本握手与漂移检测**：register/heartbeat 上报 `agent_version` 与协议版本号，控制面发现节点版本过旧时在节点列表标黄并提示"重新部署 Agent"；批量部署入口对旧版本一键升级 | agent 脚本 + `nodes.py` + 前端 Nodes.vue | P1 | 1d | 无 | 手工把节点 agent 降级为旧版 → 列表出现版本告警且不可被任务选中（可选严格模式） |

### Wave B：调度与运维增强收尾（预计 3 天，P1）

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 |
|---|------|--------|--------|--------|------|----------|
| B1 | **一爬虫多调度**：`POST /schedules` 从 upsert 改纯 create；前端调度表单去掉一对一约束；列表支持同爬虫多条规则 | `api/v1/schedules.py`、`Schedules.vue` | P1 | 1d | 无 | 同一爬虫创建 cron+interval 两条规则互不影响；删除一条不影响另一条；`schedule_test.py` 扩展用例全绿 |
| B2 | **爬虫级防并行守卫**：`create_and_run_task` 入口统一校验（手动 + 调度 + run-now 共用），同爬虫活跃任务 ≥ `max_parallel`(spider 级, 默认 1) 时拒绝/跳过；返回明确错误码 | `task_service.py`、`spiders.py` run 接口 | P1 | 1d | 无 | 并发双击运行只产生一个任务；调度触发被守卫跳过时有日志与告警事件 |
| B3 | **调度软删除/历史保留**：删除调度改为 `deleted_at` 软删（或归档表），任务 `schedule_id` 不再 SET NULL；历史页可按"已删除调度"过滤 | `models`、alembic 迁移、API、前端确认弹窗文案 | P1 | 1d | 无 | 删除调度后其历史任务的 schedule_id/schedule_name 可追溯；旧数据兼容（存量 NULL 不可恢复，接受并注明） |

### Wave C：监控告警完整版（预计 7 天，P1，可与 Wave B 并行）

| # | 任务 | 改动点 | 优先级 | 工作量 | 依赖 | 验收标准 |
|---|------|--------|--------|--------|------|----------|
| C1 | **alert_rule 引擎恢复**：基于既有 `alert_rule` 表实现规则评估引擎；内置规则类型：任务失败、任务超时、连续失败 N 次、成功率低于阈值、节点离线（复用节点健康检查事件）、僵尸任务收敛事件（对接 A2） | 新 `alert_engine.py` + 事件总线（进程内即可） | P0 | 3d | A2 | 7 类规则各一条自动化触发用例通过；规则启停即时生效 |
| C2 | **通知通道抽象**：把 d5c3041 的单点 `ALERT_WEBHOOK_URL` 升级为 channel 表（钉钉/企微/飞书/自定义 Webhook），支持静默期与聚合去重 | `notification_service.py` + 配置迁移 | P1 | 2d | C1 | 同一事件 5 分钟窗口内不重复轰炸；任一通道失败不影响其他通道 |
| C3 | **告警前端**：规则配置页 + 告警记录列表（时间/规则/对象/状态/处理人），记录表复用既有 `alert` 表结构 | 新增 2 个 Vue 页面 + alerts API | P1 | 2d | C1 | 页面 CRUD 全通；告警产生后 30s 内列表可见 |

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

| 里程碑 | 内容 | 出口条件 |
|---|---|---|
| **M1（+1 周）** | Wave A + B 全部 | 四套官方测试 + 走查脚本全绿；重启对账演练通过；发布 V1.1 |
| **M2（+3 周）** | Wave C 完整版 | 7 类告警规则上线演练；发布 V1.2（运营可用） |
| **M3（+6 周）** | Wave D（D1–D6） | 设计稿 §12.1 三种 distribution_mode 功能验收逐项打勾；发布 V2.0 |
| **M4（+8 周）** | D7/D8 + Wave E 选做 | 多实例压测通过；发布 V2.1 |

## 五、风险与对策

| 风险 | 对策 |
|---|---|
| A1 对账误杀慢启动任务（把还在跑的判死） | local/docker 用真实进程/容器探测而非时间戳一刀切；ssh/agent 无法确认时先标 SUSPECTED 再二次确认；阈值可配 |
| 一爬虫多调度（B1）破坏老用户一对一习惯 | upsert 行为仅在 POST 语义变化，存量数据无需迁移；发版说明显著标注 |
| 分布式模式依赖用户环境 Redis 版本/拓扑差异大 | 模式 B/C 先在 Docker Compose 演示环境固化参考拓扑；文档给 Sentinel 最小配置样例 |
| Wave D 期间回归风险 | 每个执行器接入 store 后立即跑四套测试 + 走查脚本；`distribution_mode` 默认 standalone 保证 V1 行为零变化（§12.3 兼容验收） |

## 六、本次已落地的配套变更

- 新增 `tests/v1_walkthrough.py`：25 项 V1 主链路 API 走查，纳入 M1 起的常规回归资产；
- 修复 `tests/full_flow_test.py` 文件保存断言（query → body，对齐 cf97469），联调恢复 41/41；
- **修复 Agent 回报 schema 断裂**（F5）：`backend/app/api/v1/agent.py` 移除 `AgentLogs`/`AgentTaskReport` 的必填 `token` 字段；
- **修复 Agent 节点"自我续命"**（F6）：`node_service.check_all_nodes_health_light` 不再回写 `last_heartbeat`；
- 以上修复均已在 117.72.16.51 云节点实测验证：任务 success + 日志/指标回流 + 停止 cancelled + 节点正常回落 OFFLINE。
