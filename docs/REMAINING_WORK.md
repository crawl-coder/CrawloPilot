# CrawloPilot V1 状态与后续规划

> 更新时间：2026-08-07

## V1 目标

V1 聚焦「爬虫部署流程」：登录 → 项目 → 爬虫 → 代码 → 执行 → 状态/日志，全链路打通。

## V1 已交付

- [x] 用户认证与 RBAC
- [x] 项目管理 + 代码文件上传
- [x] 爬虫管理 + 运行/停止
- [x] 本地进程执行（LocalExecutor，无需 Docker/Celery）
- [x] SSH 远程节点执行
- [x] Docker 节点直连执行（基础镜像复用 + 任务镜像秒级构建）
- [x] Agent 节点执行（反向注册/心跳/任务领取/日志回报/停止指令）
- [x] Server 实体（真实服务器管理）：server 表 + 服务器 Tab/详情页 +
      服务器下创建 SSH/Docker/Agent 通道 + 状态聚合
- [x] 任务状态 / 实时日志 / WebSocket 推送
- [x] 定时调度（方案 A）：进程内 APScheduler + Schedule 表驱动 + 爬虫表单入口，
      cron/interval/once 三种触发、并发守卫、触发幂等、启停/run-now/预览/历史，
      测试 `tests/schedule_test.py`（35/35 ✅）
- [x] Git 工作流：完整克隆保留 .git，详情页提交/推送/拉取/切分支，
      凭据单次注入不落盘（`git_service.py`）
- [x] Git 凭据体系：个人凭据（Fernet 加密、创建爬虫自动填充）+
      团队机器人凭据池（admin 维护、爬虫引用、轮换一处生效），
      测试 `tests/git_credentials_test.py`（34/34 ✅）
- [x] 部署流程验收测试：`tests/test_deployment_flow.py`（18/18 ✅）

## V1 已裁剪（V2 规划）

| 功能 | 说明 |
|------|------|
| 监控告警 | alerts API + alert_engine + 通知渠道 |
| ~~数据质量~~ | 2026-08-07 评估后取消（价值不大），表保留可恢复 |
| ~~数据统计/数据管理~~ | 2026-08-07 评估后取消（价值不大），表保留可恢复 |
| 代理池 | proxy_pool API / service / 模型 |
| API 管理 | api_management API / service / 模型 |
| 操作审计 | audit API / service / 中间件 |
| 基础设施 | MinIO / Prometheus / Grafana / ELK / Nginx（compose 中移除） |

> 注意：上述功能对应的数据库表仍然保留（`alert_rule`、`proxy_pool`、
> `api_config`、`audit_log`、`data_quality_rule` 等），便于 V2 平滑恢复，不做破坏性删除。

## V1 收尾清单（2026-08-07 全部完成 ✅）

- [x] `spider.schedule_config` schema 清理（model 列保留兼容旧数据，schema/API 不再读写）
- [x] `git_passphrase` 接入 git_service 与 clone（SSH_ASKPASS 方案，密码走环境变量不落明文脚本）
- [x] 爬虫内联 Git 凭据 Fernet 加密落库（`encrypt_if_plain` 幂等 + `decrypt_or_plain`
      兼容存量明文，已验证：新建落密文、解析还原、存量明文原样可用）
- [x] 开放注册开关 `ALLOW_OPEN_REGISTER`（默认 False；关闭时 /auth/register 仅 admin 可用，
      已验证两种模式；开发环境 .env 置 true）
- [x] Docker 模式真机验证（2026-08-07 本机 Docker Desktop）：unix socket 节点激活 →
      基础镜像构建 → 任务容器运行 SUCCESS → 日志落盘/接口可读；二次运行镜像 digest 命中 6.1s 复用
- [x] 测试债清理：`test_02_projects.py` 7/7（分页/删除断言兼容 + put 参数修正 +
      注册开关回退）；**全库明文凭据脱敏**（conftest.py、run_all_tests.py、_fix_db.py、
      note.txt、Nodes.vue 占位 IP、server-management.md）

## V2 计划（分波次，按价值 × 依赖排序）

### Wave 1：调度与运维增强（产品核心链路完善，前置无依赖）

| # | 事项 | 前后端 | 工作量 |
|---|------|--------|--------|
| 1.1 | **调度全局视图页**：只读列表 + 快捷操作（启停/run-now/历史），接口零改动 | 前端 | 1d |
| 1.2 | **调度终态统计回写**：任务终态回调更新 success_count/fail_count/last_run_status（与 1.1 配套，列表"上次结果"依赖它） | 后端 | 0.5d |
| 1.3 | **一爬虫多调度**（需求触发再做）：POST /schedules 从 upsert 改 create，列表页管多条规则；引擎层无需改动 | 前后端 | 1d |
| 1.4 | **爬虫级防并行守卫**（按需）：同爬虫运行中任务达阈值时拒绝新触发（手动+调度统一） | 后端 | 0.5d |

> 「一个爬虫一条调度」当前是 **API 层 upsert 约定**（POST 按 spider_id 找第一条更新），
> `schedule` 表无 (spider_id) 唯一索引。1.3 实施时的接口变更点：upsert → create
> （或拆 create + PUT by id）。

### Wave 2：监控告警（V1 裁剪表中运营价值最高）

- 告警规则引擎：`alert_rule` 表已建，恢复 alerts API + alert_engine
- 规则类型：任务失败 / 超时 / 节点离线 / 成功率阈值（任务与节点指标 V1 已具备）
- 通知通道：Webhook（钉钉/飞书）优先，邮件次之
- 前端：告警规则配置页 + 告警记录列表

### ~~Wave 3：数据质量与统计~~（2026-08-07 取消）

经评估对爬虫部署管理平台价值不大，不做。`data_quality_rule` 等表继续保留，
将来若有需求可低成本恢复。

### Wave 3：平台化（按实际需求裁剪，可独立并行）

- 代理池（proxy_pool 表已建）、API 管理（api_config 表已建）
- 操作审计（audit_log 表已建，中间件按需开启）
- 生产化：Scheduler 主备（Redis 分布式锁）、多实例控制面（UPLOAD_DIR 共享存储）、
  MinIO / Prometheus / Grafana / ELK（compose 恢复）

## 待定问题（已记录）

- ~~定时任务入口放在哪个页面~~（2026-08-07 已落定方案 A：
  V1 走爬虫表单入口写 `schedule` 表（cron/interval/once 均已支持），
  全局视图见 V2 Wave 1.1，详见 `docs/designs/scheduling.md`）
- ~~迁移机制双轨~~（2026-08-07 已统一：`migrate_schedule.py` 删除，
  职责由 alembic 迁移 `s2c3h4e5d6u7` 吸收，DDL 带存在性检查可安全空跑）
- ~~`/users` 管理接口缺少后端 admin 鉴权~~（2026-08-07 已修复：
  全部端点接入 `require_admin`，`require_admin` 已上移至 `core/dependencies.py`）

## 已知事项

- crawlo 已升级至 1.7.2（本地环境 + Docker 基础镜像均使用，基础镜像构建优先用本地 wheel）
- Agent 程序：`agent/crawlo_agent.py`，纯标准库，反向连接控制端
- 本地开发数据库：Homebrew mysql@8.0 或 Docker MySQL，库名 `crawlo_pilot`，
  账号见 `.env.example`（凭据以本地 `.env` 为准，不入库）
- 迁移链注意：早期裁剪移除的表（api_call_log/proxy_* 等）仍被旧迁移引用，
  **全新库不要直接 `alembic upgrade head`**，用 `Base.metadata.create_all` +
  `alembic stamp head` 建库（本地库已按此处理）
- 远程 MySQL/Redis 网络延迟约 0.5~1s/请求；本地部署建议使用 Docker 版 MySQL/Redis
- ~~Docker 守护进程未运行，容器模式暂未在本机验证~~（2026-08-07 已在本机 Docker
  Desktop 验证通过：镜像构建/容器运行/日志/复用全链路，见 V1 收尾清单）
- 遗留说明：`/execution/tasks` 与 `/task-instances` 是两套并存的任务 API（前端混用），
  建议 V2 收敛为一个入口
