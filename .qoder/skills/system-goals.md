# CrawloPilot 系统目标与核心定位

> **重要**: 本文档定义了 CrawloPilot 的核心目标和设计原则,所有开发必须遵循这些原则,不得偏离初衷。

---

## 🎯 系统目标

**CrawloPilot 是 Crawlo 爬虫的专用部署与管理平台**

核心定位: **零侵入式管理**

- ❌ 不强制修改爬虫代码
- ❌ 不依赖 SDK 或框架适配
- ✅ 仅通过标准化方式实现监控与管理

---

## 🏗️ 核心架构原则

### 1. 零侵入设计

**爬虫代码完全独立,不需要任何修改**

```python
# ✅ 正确: 爬虫代码保持纯净
from crawlo import Spider, Request, Response

class MySpider(Spider):
    name = "my_spider"
    # 不需要导入 crawlopilot
    # 不需要添加中间件
    # 不需要修改任何代码
```

**平台通过以下方式管理爬虫**:
1. Docker 容器化部署
2. 运行时日志采集
3. 容器指标监控 (CPU/内存/网络)
4. 数据库/文件输出同步
5. HTTP API 对接 (可选,爬虫主动调用)

### 2. SDK 的定位

**CrawloPilot 不依赖 SDK!**

爬虫完全不需要导入任何 SDK,平台通过以下方式实现零侵入管理:

1. Docker 容器化部署
2. 运行时日志采集
3. 容器指标监控 (CPU/内存/网络)
4. 数据库/文件输出同步

**历史说明**:
- 早期版本曾设计独立 SDK 模块
- 经架构评估,与零侵入原则矛盾
- 已于 2026-04-12 删除整个 sdk/ 目录
- 平台所有功能通过标准化方式实现

### 3. 数据采集方式

**优先非侵入方式**:

```
1. Docker 日志采集 (主要)
   ├── 爬虫输出日志到 stdout
   ├── 平台通过 Docker API 采集
   └── 解析日志提取指标

2. 数据库/文件同步
   ├── 爬虫将结果写入 DB/文件
   ├── 平台定期读取
   └── 无需爬虫主动上报

3. 容器指标监控
   ├── CPU/内存/网络使用
   ├── 容器状态 (running/stopped/failed)
   └── Docker API 自动获取

4. HTTP API (可选)
   ├── 爬虫主动调用平台 API
   ├── 上报进度/数据
   └── 不强制使用
```

---

## 📦 核心组件

### 1. Spider Runner (爬虫运行环境)

**位置**: `/spider-runner/`

**职责**: 提供 Crawlo 爬虫的 Docker 运行环境

```dockerfile
FROM python:3.10-slim
RUN pip install crawlo  # 预装 Crawlo 框架
ENTRYPOINT ["python", "/spider/run_spider.py"]
```

**关键特性**:
- ✅ 预装 Crawlo 框架
- ✅ 支持 Git 代码挂载
- ✅ 环境变量配置
- ✅ 日志标准输出
- ✅ 健康检查

### 2. TaskExecutor (任务执行器)

**位置**: `backend/app/services/task_executor.py`

**职责**: 在 Docker 容器中执行爬虫任务

**核心流程**:
```
1. 从 Git 拉取爬虫代码
2. 构建 Docker 容器配置
3. 创建并启动容器
4. 启动日志采集
5. 监控容器状态
6. 任务完成,清理资源
```

**关键代码**:
```python
async def execute_task(self, config: TaskConfig):
    # 1. Git 拉取
    code_dir = await self._clone_git_repository(config)
    
    # 2. 创建容器
    container = self.docker_client.containers.run(
        image='crawlopilot/spider-runner:latest',
        volumes={code_dir: {'bind': '/spider/code', 'mode': 'ro'}},
        environment={'SPIDER_NAME': config.spider_name}
    )
    
    # 3. 启动日志采集
    await collector.start_collecting(task_id, container.id)
```

### 3. LogCollector (日志采集器)

**位置**: `backend/app/services/log_collector.py`

**职责**: 从 Docker 容器采集日志,解析 Crawlo 日志格式

**核心功能**:
```python
class LogCollector:
    async def start_collecting(self, task_id, container_id):
        # 流式读取 Docker 日志
        logs = container.logs(stream=True, follow=True)
        
        for log_line in logs:
            # 解析 Crawlo 日志格式
            parsed = self._parse_log_line(log_line)
            
            # 提取指标
            # - 爬虫状态 (started/finished/failed)
            # - 页面数量 (pages_crawled)
            # - 数据条数 (items_scraped)
            # - 错误数量 (errors_count)
            
            # 更新数据库
            await self._update_task_metrics(task_id, parsed)
```

**日志格式解析**:
```
2024-04-12 10:00:00 [INFO] Spider of_week started
2024-04-12 10:00:01 [INFO] Crawled 100 pages, 50 items
2024-04-12 10:00:02 [ERROR] Failed to parse url: xxx
```

---

## 🚫 禁止的设计

### ❌ 错误示例 1: 强制爬虫导入外部依赖

```python
# ❌ 错误: 要求爬虫修改代码
from some_sdk import SomeMiddleware

class MySpider(Spider):
    def __init__(self):
        self.middleware = SomeMiddleware()  # 侵入式!
```

### ❌ 错误示例 2: 平台依赖外部 SDK

### ❌ 错误示例 3: 修改爬虫代码

```python
# ❌ 错误: 在爬虫代码中添加平台逻辑
class MySpider(Spider):
    async def parse(self, response):
        item = extract_data(response)
        await platform_client.upload(item)  # 不应该!
        return item
```

---

## ✅ 正确的设计

### ✅ 示例 1: 零侵入部署

```python
# 平台侧代码 (TaskExecutor)
container = docker_client.containers.run(
    image='crawlopilot/spider-runner:latest',
    volumes={
        '/path/to/spider/code': {'bind': '/spider/code', 'mode': 'ro'}
    },
    environment={
        'SPIDER_NAME': 'my_spider'
    }
)
# 爬虫代码完全不需要修改!
```

### ✅ 示例 2: 日志采集

```python
# 平台侧代码 (LogCollector)
logs = container.logs(stream=True, follow=True)
for log_line in logs:
    parsed = parse_crawlo_log(log_line)
    update_database(parsed)
# 爬虫只需正常输出日志即可!
```

### ✅ 示例 3: 爬虫完全独立

---

## 📋 开发检查清单

**添加新功能时,必须检查**:

- [ ] 是否要求爬虫修改代码? (应该: ❌ 否)
- [ ] 是否依赖外部 SDK? (应该: ❌ 否)
- [ ] 是否通过非侵入方式实现? (应该: ✅ 是)
- [ ] 爬虫能否独立运行? (应该: ✅ 能)
- [ ] 是否尊重零侵入原则? (应该: ✅ 是)

---

## 🎓 技术栈

### 平台技术栈

```
后端: FastAPI + Python 3.10
前端: Vue 3 + Element Plus
数据库: MySQL 8.0
缓存: Redis 7
异步任务: Celery + Redis
调度器: APScheduler
容器: Docker + docker-py
监控: Prometheus + Grafana
对象存储: MinIO
```

### 爬虫技术栈

```
框架: Crawlo (主要) / Scrapy (兼容)
运行环境: Docker (spider-runner)
代码管理: Git
```

---

## 🔄 完整工作流程

```
1. 用户操作
   └── 在 CrawloPilot 前端创建任务

2. Git 拉取
   └── TaskExecutor 从 Git 仓库拉取爬虫代码

3. 容器创建
   └── 使用 spider-runner 镜像创建 Docker 容器
   └── 挂载爬虫代码到 /spider/code
   └── 设置环境变量 (SPIDER_NAME, TASK_ID, etc.)

4. 爬虫运行
   └── 容器启动 run_spider.py
   └── run_spider.py 加载爬虫代码
   └── 调用 Crawlo 框架运行爬虫
   └── 爬虫正常执行,输出日志到 stdout

5. 日志采集
   └── LogCollector 流式读取 Docker 日志
   └── 解析 Crawlo 日志格式
   └── 提取指标 (进度/错误/统计数据)
   └── 更新数据库

6. 监控告警
   └── 容器指标采集 (CPU/内存/网络)
   └── 任务状态更新
   └── 异常告警

7. 任务完成
   └── 容器退出
   └── 日志采集停止
   └── 更新最终状态
   └── 清理资源
```

---

## 📝 总结

**CrawloPilot 的核心价值**:

1. **零侵入** - 爬虫代码完全独立
2. **标准化** - 通过 Docker/日志/API 管理
3. **可选增强** - SDK 仅为可选工具
4. **全生命周期** - 部署/调度/监控/告警

**开发准则**:

> 任何功能都不得破坏零侵入原则。
> 爬虫应该能够在完全不感知 CrawloPilot 的情况下正常运行。
> 平台是管理者,不是侵入者。

---

**本文档是 CrawloPilot 项目的核心设计文档,所有开发者必须严格遵守!** 🎯
