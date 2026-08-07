# Changelog

本文件记录 CrawloPilot 的显著变更，格式遵循
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循
[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

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
