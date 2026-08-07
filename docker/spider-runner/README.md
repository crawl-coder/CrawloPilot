# CrawloPilot Spider Runner Docker Image（历史镜像，已不在主链路）

> **状态：遗留**。本文档描述的"SDK 注入 / 心跳保活 / 数据上报"架构已废弃
> （`crawlopilot` SDK 包已从仓库移除）。当前 Docker 执行链路见
> [docs/modules/04-execution.md](../../docs/modules/04-execution.md)：
> 平台使用 `crawlopilot/base:1.7.2` 基础镜像（由本地 Crawlo wheel 构建）+
> 任务镜像 COPY 代码的方式运行容器，日志/状态由控制端执行器管理，
> 容器内无需任何 SDK 或上报逻辑。
>
> 本目录的 Dockerfile/entrypoint 仅作为自定义运行环境的参考样例保留。

## 当前实际行为

- 入口脚本 `entrypoint.sh`：校验环境变量 → 可选安装 requirements → 执行爬虫命令
- 环境变量中的 `API_URL` / `API_TOKEN` 已无消费方（SDK 已移除），传入也不会产生上报

## 当前平台的 Docker 执行方式（摘要）

```text
crawlopilot/base:1.7.2（python:3.10-slim + crawlo 全家桶 wheel，一次性构建）
  └── 任务镜像 crawlo-project-{id}-{内容摘要}（COPY 代码 + 装 requirements，秒级缓存复用）
        └── 容器运行入口：entry_file 或 run.py
```

构建与验证流程见 [docs/modules/04-execution.md](../../docs/modules/04-execution.md) 第 4 节。

## 许可证

MIT License
