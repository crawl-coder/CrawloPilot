# legacy/ 历史文档

> **注意**：本目录收录早期开发阶段的设计与实现记录，**仅供追溯历史演进使用**。
> 其中描述的架构（Celery、spider-runner 心跳进程、项目级 Git API 等）大部分已被重构或移除，
> **不代表当前实现**。当前架构请以 [modules/](../modules/)、[designs/](../designs/)、
> [product-design.md](../product-design.md) 为准。

## 文档清单

| 文件 | 记录的历史内容 | 当前状态 |
|------|---------------|----------|
| Git管理和本地上传功能说明.md | 项目级 Git API + 本地上传 | 已重构为爬虫级 Git API |
| SPIDER_LIFECYCLE_MANAGEMENT.md | 爬虫生命周期与 Celery 异步执行 | Celery 已移除，改执行器模式 |
| SPIDER_STATUS_AND_CONTROL.md | 状态监控与 Celery 停止任务 | 已改为四种执行器 |
| HEARTBEAT_MONITORING.md | 容器内心跳监控方案 | 已废弃，改 Agent 反向连接 |
| MULTI_SPIDER_SUPPORT.md | 多爬虫运行支持 | 已由执行器 subprocess 实现 |

> 早期 `DEVELOPMENT.md`（Celery 开发清单）与 `ARCHITECTURE_CLEANUP_COMPLETE.md`（SDK 删除记录）
> 属纯操作记录，已删除。

## 术语对照

| 旧文档（已废弃） | 当前实现 |
|------------------|----------|
| Celery Worker | LocalExecutor / SSHExecutor / DockerExecutor / AgentExecutor |
| spider-runner 容器心跳 | Agent 反向连接心跳 |
| 项目级 Git API (`/projects/{id}/git`) | 爬虫级 Git API (`/spiders/{id}/git`) |
