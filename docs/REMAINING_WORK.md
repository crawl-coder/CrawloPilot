# CrawloPilot V1 状态与后续规划

> 更新时间：2026-08-05

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
- [x] 任务状态 / 实时日志 / WebSocket 推送
- [x] 部署流程验收测试：`tests/test_deployment_flow.py`（18/18 ✅）

## V1 已裁剪（V2 规划）

| 功能 | 说明 |
|------|------|
| Git 管理 | project_git / spider_git / git_service |
| 调度系统 | schedules API + scheduler 模块（依赖 Celery Worker） |
| 监控告警 | alerts API + alert_engine + 通知渠道 |
| 数据质量 | data_quality API / service / 模型 |
| 数据统计/数据管理 | DataStatistics / DataManagement 页面 |
| 代理池 | proxy_pool API / service / 模型 |
| API 管理 | api_management API / service / 模型 |
| 操作审计 | audit API / service / 中间件 |
| 基础设施 | MinIO / Prometheus / Grafana / ELK / Nginx（compose 中移除） |

> 注意：上述功能对应的数据库表仍然保留（`alert_rule`、`proxy_pool`、
> `api_config`、`audit_log`、`data_quality_rule` 等），便于 V2 平滑恢复，不做破坏性删除。

## V2 建议顺序

1. **服务器实体**：引入 `server` 表 + 服务器详情页，一台服务器下管理
   SSH/Docker/Agent 三种执行通道（设计见 `docs/modules/05-nodes.md`）
2. 调度系统（进程内 APScheduler + 本地执行）
3. 监控告警（基于任务状态与节点指标）
4. Git 仓库管理（clone/pull/push）
5. 数据质量与统计
6. 代理池 / API 管理
7. 操作审计（中间件按需开启）

## 待定问题（已记录）

- **定时任务入口放在哪个页面（2026-08-05 用户提出，待确认）**
  - 倾向方案：爬虫详情页加「定时调度」tab（调度绑定具体爬虫，上下文最直观）
  - 二期补充：顶栏「调度管理」总览页（全局视角看下次执行/最近结果/一键启停）
  - 技术路线：后端进程内 APScheduler + DB 持久化 + 复用 LocalExecutor 执行，
    去掉 Celery 依赖（`schedule` 表与旧接口仍在，恢复成本低）

## 已知事项

- crawlo 已升级至 1.7.2（本地环境 + Docker 基础镜像均使用，基础镜像构建优先用本地 wheel）
- Agent 程序：`agent/crawlo_agent.py`，纯标准库，反向连接控制端
- 远程 MySQL/Redis（117.72.16.51）网络延迟约 0.5~1s/请求；本地部署建议使用 Docker 版 MySQL/Redis
- Docker 守护进程未运行，容器模式暂未在本机验证
- `tests/run_all_tests.py` 中残留数据库明文凭据，生产环境需移除或改用环境变量
