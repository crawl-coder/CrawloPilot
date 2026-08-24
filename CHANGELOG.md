# Changelog

本文件记录 CrawloPilot 的显著变更，格式遵循
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- **任务对账模块 `task_reconciler.py`（V2 计划 A1/A2/A3）**：`lifespan` 启动时扫描遗留
  PENDING/RUNNING 任务，按 deploy_mode 分发探活（local PID / docker 容器 / ssh 远程 PID /
  agent 超龄）；超龄 24h（`TASK_STALE_HOURS` 可配）兜底标记 FAILED；调度守卫排除僵尸，
  防止类似 F1 的任务永久阻断调度触发
- **密钥配置体检（A4）**：`config.validate_secrets()` 开发模式发 WARNING 不阻断启动，
  `/health` 新增 `warnings` 字段展示当前密钥配置缺陷（JWT/凭据共用 + 两者均未独立设置）
- **Agent venv 模板缓存（A6）**：`~/.crawlo-agent/template_venv/` 预装 crawlo，
  任务 venv 直接复制（~0.5s vs 原来 30s+）；安装阶段（venv/crawlo/requirements）
  每步检查 `stop_requested`，停止 ≤5s 内生效；Agent 版本 0.1.0 → 0.2.0
- **代码分发排除 .git + 摘要缓存（A6.1/A6.2）**：Agent `/code` 和 SSH 分发打包时
  排除 `.git/__pycache__/.DS_Store`；控制面 `_code_digest()` 计算文件清单 sha256 摘要，
  Agent 本地 `~/.crawlo-agent/code-cache/{digest}/` 命中则跳过下载；旧 agent 无
  `code_digest` 字段兼容不变
- **Agent 版本握手（A7）**：Node model 新增 `protocol_version` 列（alembic 迁移
  a7b8c9d0e1f2，幂等）；Agent register 上报 `protocol_version`；NodeResponse 新增
  `agent_compatible`（protocol_version ≥ REQUIRED=1 → True，否则 False）；
  旧版 agent（NULL/0）→ 不兼容，前端可标黄提示重新部署
- **执行模式使用指南 `docs/guides/execution-modes.md`**：本地/SSH/Docker/Agent 四种模式
  的前置条件、接入步骤、验证方法与排错速查表（含代码分发机制说明与 API 最小示例）；
  `modules/05-nodes.md` §4 操作流程收敛为指针，消除双处维护
- **Agent 模式端到端回归测试 `tests/agent_flow_test.py`**（A5）：真实拉起
  `agent/crawlo_agent.py` 子进程直连本地控制面，26 项断言覆盖 register/heartbeat/
  领任务/下载代码/执行/日志上报/终态回报/停止指令全部端点，并固化 F5（协议一致性）
  /F6（无自我续命）两条回归线
- Agent 新增测试逃生阀：`CRAWLO_AGENT_SKIP_CRAWLO_INSTALL=1` 跳过每任务 crawlo 安装
- V2 下一阶段开发任务计划：`docs/v2-development-plan.md`（Wave A–E 排期 + F1–F7 实证）
- 新增 `tests/v1_walkthrough.py`：V1 主链路 API 走查脚本（25 项，含指标解析、
  停止/重试、调度 run-now/历史），作为常规回归资产

### Fixed

- **Agent 模式回报断裂**（实测发现）：`/nodes/agent/tasks/{id}/logs` 与 `/report` 的
  body schema 仍要求必填 `token`，与已 Bearer 化的 agent 脚本不匹配，导致全新部署的
  Agent 任务日志上报与终态回报全部 422、任务永久卡 running；移除两个 schema 中的
  `token` 字段（鉴权仅走 header，旧版 agent 多传的 token 字段默认忽略，双向兼容）
- **Agent 节点永不离线**：轻量健康检查在判定 online 后回写 `last_heartbeat = now`，
  形成"自我续命"——死掉的 Agent 永远无法离线、调度仍会选中该节点；改为心跳只由
  Agent 真实上报，健康检查仅依据其新鲜度判定状态
- `tests/full_flow_test.py` 爬虫文件保存断言改为 body 传输（对齐 cf97469 的接口变更，
  消除联调 40/41 假失败）

### Changed

- crawlo 升级到 1.7.3（与 PyPI 最新一致）：Docker 基础镜像
  `crawlopilot/base:1.7.3` 随任务构建自动生成/复用

### Removed

- 移除 Celery 死代码：`app/workers/` 任务模块（无任何活跃调用方）、
  `CELERY_*` 配置项、Prometheus Celery 指标；部署 / 回滚 / 重试改为
  FastAPI BackgroundTasks 直调 `DeployService`
- 移除 Redis 依赖：`/health` 与监控探针、登录限流死代码（原已注释停用）、
  `REDIS_*` 配置项、Compose redis 服务与 `docker/redis/` 配置；
  平台运行时外部依赖收敛为仅 MySQL

### Security

- 节点 SSH 凭据（`ssh_pwd` / `ssh_key`）改为 Fernet 加密落库：
  写入经 `encrypt_if_plain`、读取经 `decrypt_or_plain`（兼容存量明文），
  与 Git 凭据加密同源；`migrate_node_credentials.py` 幂等迁移存量数据

## [1.0.0] - 2026-08-07

首次正式发布：爬虫部署管理平台 V1 全链路打通。

### Added

- 用户认证与权限：JWT + RBAC（用户 / 角色 / 团队 / 权限码），用户管理 admin 鉴权
- 项目管理：项目 CRUD、版本管理、代码文件上传与在线编辑
- 爬虫管理：爬虫 CRUD、代码文件树与 Monaco 编辑器、运行与停止
- 代码来源：Git 仓库克隆（保留完整 `.git`）、ZIP/TAR 上传、空模板
- Git 工作流：提交 / 推送 / 拉取 / 切换分支，凭据单次注入不落盘
- Git 凭据体系：个人凭据（Fernet 加密）与团队机器人凭据池
- 任务执行：本地进程 / SSH 远程 / Docker 直连 / Agent 节点四种执行模式
- Server 实体：真实服务器管理，下辖 SSH / Docker / Agent 三种执行通道
- 任务全生命周期：状态机、实时日志（WebSocket）、暂停 / 恢复 / 停止 / 重试 / 删除
- 运行统计：解析爬虫指标（pages / items / errors）回写运行记录
- 定时调度：进程内 APScheduler，cron / interval / once 三种触发，
  并发守卫、触发幂等、启停 / 立即执行 / 预览 / 历史
- 仪表盘：项目 / 爬虫 / 任务 / 节点概览
- CI/CD：GitHub Actions（测试 / 代码质量 / 安全扫描 / Docker 构建）

### Fixed

- 修复依赖冲突：`aiohttp` / `httpx` 与 crawlo 1.7.2 要求冲突，放宽版本并补充缺失依赖
- 升级被 GitHub 下架的过时 Actions（upload-artifact v3 → v4 等）
- 修复 docker-build 使用 secrets 的方式（映射到 job 级 env 判断）
- `/users` 管理接口补全 admin 鉴权
- 修复 uvicorn 双监听问题

### Security

- 爬虫内联 Git 凭据改为 Fernet 加密落库（兼容存量明文）
- 全库测试脚本明文凭据脱敏
