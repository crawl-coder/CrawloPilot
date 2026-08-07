# CrawloPilot Spider Runner

Crawlo 爬虫的 Docker 运行环境镜像构建目录。

> **角色说明（兜底，非主链路）**：平台 Docker 执行的主链路使用
> `crawlopilot/base:1.7.2`（由本地 Crawlo wheel 在构建时生成），
> 仅当 wheel 不可用需要回退到 `pip install crawlo` 时，才使用本目录构建的
> 兜底镜像（`crawlopilot/base:fallback`）。详见
> [docs/modules/04-execution.md](../docs/modules/04-execution.md) 第 4 节。

## 功能

- 预装 Crawlo 框架运行环境
- 环境变量配置（`SPIDER_NAME` 等）
- 日志标准输出
- 健康检查

## 构建镜像

```bash
cd spider-runner
docker build -t crawlopilot/base:fallback .
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| SPIDER_NAME | ✅ | 爬虫名称 |
| SPIDER_ARGS | ❌ | 爬虫参数 |
| TASK_ID | ❌ | CrawloPilot 任务 ID（仅记录到日志） |

> 注：`API_URL` / `API_TOKEN` 曾被早期 SDK 上报方案使用，该方案已移除，
> 当前传入不产生任何上报行为。

## 使用示例

```bash
# 准备爬虫代码（示例）
cp -r examples/ofweek_standalone /tmp/test_spider

# 运行容器
docker run -it --rm \
  -v /tmp/test_spider:/spider/code \
  -e SPIDER_NAME=of_week \
  crawlopilot/base:fallback
```

## 目录结构（容器内）

```text
/spider/
├── code/           # 爬虫代码（挂载）
├── data/           # 运行时数据
├── logs/           # 日志目录
├── output/         # 输出目录
└── run_spider.py   # 启动脚本
```
