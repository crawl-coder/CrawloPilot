# CrawloPilot Spider Runner

Crawlo 爬虫的 Docker 运行环境,由 CrawloPilot 平台管理。

## 功能

- ✅ 预装 Crawlo 框架
- ✅ Git 代码拉取支持
- ✅ 环境变量配置
- ✅ 日志标准输出
- ✅ 健康检查

## 构建镜像

```bash
cd spider-runner
docker build -t crawlopilot/spider-runner:latest .
```

## 使用示例

### 1. 本地测试

```bash
# 准备爬虫代码
cp -r /Users/oscar/projects/CrawloPilot/examples/ofweek_standalone /tmp/test_spider

# 运行容器
docker run -it --rm \
  -v /tmp/test_spider:/spider/code \
  -e SPIDER_NAME=of_week \
  crawlopilot/spider-runner:latest
```

### 2. CrawloPilot 平台调用

```python
# 平台通过 TaskExecutor 创建容器
container = docker_client.containers.create(
    image='crawlopilot/spider-runner:latest',
    name=f'task-{task_id}',
    environment={
        'SPIDER_NAME': 'of_week',
        'TASK_ID': task_id,
    },
    volumes={
        '/path/to/spider/code': {'bind': '/spider/code', 'mode': 'ro'}
    },
    network='crawlopilot-network'
)
container.start()
```

## 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| SPIDER_NAME | ✅ | 爬虫名称 |
| SPIDER_ARGS | ❌ | 爬虫参数 |
| TASK_ID | ❌ | CrawloPilot 任务 ID |
| API_URL | ❌ | CrawloPilot API 地址 |
| API_TOKEN | ❌ | CrawloPilot API Token |

## 日志格式

```
2024-04-12 10:00:00 [INFO] CrawloPilot Spider Runner 启动
2024-04-12 10:00:00 [INFO] ============================================================
2024-04-12 10:00:00 [INFO] Spider Name: of_week
2024-04-12 10:00:00 [INFO] Task ID: task_123
2024-04-12 10:00:01 [INFO] 爬虫代码目录: /spider/code
2024-04-12 10:00:01 [INFO] 启动爬虫: of_week
2024-04-12 10:00:02 [INFO] Spider of_week started
2024-04-12 10:00:03 [INFO] Crawled 100 pages, 50 items
2024-04-12 10:00:10 [INFO] Spider of_week closed
```

## 目录结构

```
/spider/
├── code/           # 爬虫代码 (挂载)
├── data/           # 运行时数据
├── logs/           # 日志目录
├── output/         # 输出目录
└── run_spider.py   # 启动脚本
```
