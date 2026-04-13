# CrawloPilot 多爬虫支持与 run_spider.py 逻辑说明

**时间**: 2026-04-12  
**主题**: 多爬虫并发、入口文件机制

---

## 📋 问题解答

### 问题 1: run_spider.py 为什么需要自己启动爬虫?

**你的观察非常正确!** 

ofweek 项目本身有 `run.py` 入口文件,但 `spider-runner/run_spider.py` 不能直接调用它,原因如下:

#### ❌ 错误方式: 直接调用 run.py

```python
# 这样不行!
os.system("cd /spider/code && python run.py")
```

**问题**:
1. 无法动态指定爬虫名称 (run.py 硬编码了 `of_week`)
2. 无法获取任务 ID 等环境变量
3. 无法统一日志格式
4. 无法控制超时和错误处理

#### ✅ 正确方式: 使用 Crawlo 框架 API

```python
# spider-runner/run_spider.py
from crawlo.crawler import CrawlerProcess

# 从环境变量读取爬虫名称
spider_name = os.environ['SPIDER_NAME']  # of_week

# 动态启动指定爬虫
process = CrawlerProcess()
await process.crawl(spider_name)  # 可以指定任意爬虫!
```

**优势**:
- ✅ 动态指定爬虫名称
- ✅ 统一的环境变量管理
- ✅ 统一的日志格式
- ✅ 完整的错误处理
- ✅ 支持超时控制

---

### 问题 2: 一个爬虫项目有多个爬虫,如何支持?

#### ofweek 项目的爬虫列表

```
examples/ofweek_standalone/ofweek_standalone/spiders/
├── of_week.py                  # 爬虫 1: of_week
├── of_week_adaptive.py         # 爬虫 2: of_week_adaptive
├── of_week_with_db.py          # 爬虫 3: of_week_with_db
└── of_week_with_notifications.py  # 爬虫 4: of_week_with_notifications
```

每个文件定义了一个爬虫类:

```python
# of_week.py
class OfWeekSpider(Spider):
    name = 'of_week'  # 爬虫名称

# of_week_adaptive.py
class OfWeekAdaptiveSpider(Spider):
    name = 'of_week_adaptive'

# of_week_with_db.py
class OfWeekWithDBSpider(Spider):
    name = 'of_week_with_db'
```

#### Crawlo 框架的自动发现机制

```python
# Crawlo 框架会自动扫描 spiders/ 目录
# 并通过元类注册所有爬虫

from crawlo.spider import Spider

class SpiderMeta(type):
    """爬虫元类 - 自动注册"""
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        
        # 自动注册到全局注册表
        spider_name = namespace.get('name')
        _SPIDER_REGISTRY[spider_name] = cls
        
        return cls
```

#### 如何运行指定爬虫

```python
# 方式 1: 运行单个爬虫
await CrawlerProcess().crawl('of_week')

# 方式 2: 运行另一个爬虫
await CrawlerProcess().crawl('of_week_adaptive')

# 方式 3: 同时运行多个爬虫
await CrawlerProcess().crawl(['of_week', 'of_week_adaptive'])
```

---

## 🎯 CrawloPilot 多爬虫支持方案

### 方案 1: 每个任务运行一个爬虫 (当前方案)

```
任务 1: of_week
  └─ 容器 1: spider-runner
       └─ SPIDER_NAME=of_week

任务 2: of_week_adaptive
  └─ 容器 2: spider-runner
       └─ SPIDER_NAME=of_week_adaptive

任务 3: of_week_with_db
  └─ 容器 3: spider-runner
       └─ SPIDER_NAME=of_week_with_db
```

**优点**:
- ✅ 容器隔离,互不影响
- ✅ 独立资源限制 (CPU/内存)
- ✅ 独立日志采集
- ✅ 独立状态监控

**缺点**:
- ❌ 资源开销较大 (每个容器 ~50MB)

### 方案 2: 一个容器运行多个爬虫 (未来优化)

```
任务: ofweek 全部爬虫
  └─ 容器 1: spider-runner
       ├─ SPIDER_NAMES=of_week,of_week_adaptive,of_week_with_db
       └─ 同时运行多个爬虫
```

**实现**:
```python
# 支持多爬虫名称 (逗号分隔)
spider_names = os.environ.get('SPIDER_NAMES', '').split(',')

# 同时运行多个爬虫
process = CrawlerProcess()
await process.crawl(spider_names)  # 传入列表
```

---

## 📊 完整运行流程对比

### 直接使用项目的 run.py

```bash
# ofweek_standalone/run.py
python run.py  # 硬编码运行 of_week
python run.py of_week_adaptive  # ❌ 不支持参数!
```

**run.py 的代码**:
```python
# 硬编码了爬虫名称!
asyncio.run(CrawlerProcess().crawl('of_week'))
```

### 使用 spider-runner/run_spider.py

```bash
# 通过环境变量指定爬虫
docker run \
  -e SPIDER_NAME=of_week \
  crawlopilot/spider-runner:latest

docker run \
  -e SPIDER_NAME=of_week_adaptive \
  crawlopilot/spider-runner:latest
```

**run_spider.py 的代码**:
```python
# 从环境变量动态读取
spider_name = os.environ['SPIDER_NAME']

# 启动指定爬虫
process = CrawlerProcess()
await process.crawl(spider_name)
```

---

## 🔧 run_spider.py 的核心职责

### 1. 环境准备

```python
def check_environment():
    """检查环境变量"""
    spider_name = os.environ.get('SPIDER_NAME')
    if not spider_name:
        logger.error("SPIDER_NAME 未设置")
        sys.exit(1)
    
    return spider_name

def load_spider_project():
    """加载爬虫项目"""
    code_dir = Path('/spider/code')
    
    # 添加到 Python 路径
    sys.path.insert(0, str(code_dir))
    
    return code_dir
```

### 2. 统一启动逻辑

```python
async def run_spider(spider_name: str):
    """运行爬虫"""
    # 导入 Crawlo 框架
    from crawlo.crawler import CrawlerProcess
    
    # 创建爬虫进程
    process = CrawlerProcess()
    
    # 运行指定爬虫
    await process.crawl(spider_name)
```

### 3. 错误处理

```python
try:
    await process.crawl(spider_name)
except ImportError as e:
    logger.error(f"导入 Crawlo 框架失败: {e}")
    sys.exit(1)
except KeyboardInterrupt:
    logger.warning("爬虫被用户中断")
except Exception as e:
    logger.error(f"爬虫运行失败: {e}")
    sys.exit(1)
```

### 4. 日志标准化

```python
# 统一日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 输出关键信息
logger.info(f"CrawloPilot Spider Runner 启动")
logger.info(f"Spider Name: {spider_name}")
logger.info(f"Task ID: {os.environ.get('TASK_ID', 'N/A')}")
```

---

## 📈 多爬虫并发测试

### 测试脚本

```python
#!/usr/bin/env python3
"""测试同时运行多个爬虫"""

import subprocess
import time

# 定义要运行的爬虫
spiders = [
    'of_week',
    'of_week_adaptive',
    'of_week_with_db'
]

# 并行启动多个容器
containers = []
for i, spider_name in enumerate(spiders):
    container_id = f"test_spider_{i}"
    
    result = subprocess.run([
        'docker', 'run', '-d', '--rm',
        '--name', container_id,
        '-v', '/path/to/ofweek:/spider/code',
        '-e', f'SPIDER_NAME={spider_name}',
        '-e', f'TASK_ID=task_{i}',
        'crawlopilot/spider-runner:latest'
    ], capture_output=True, text=True)
    
    containers.append(container_id)
    print(f"启动 {spider_name}: {container_id}")

# 监控所有容器
time.sleep(10)

for container_id in containers:
    result = subprocess.run([
        'docker', 'logs', container_id
    ], capture_output=True, text=True)
    
    print(f"\n{container_id} 日志:")
    print(result.stdout[-200:])  # 最后 200 字符

# 停止所有容器
for container_id in containers:
    subprocess.run(['docker', 'stop', container_id])
```

---

## 🎯 总结

### run_spider.py 的必要性

| 对比项 | 项目 run.py | spider-runner/run_spider.py |
|--------|------------|---------------------------|
| 爬虫名称 | ❌ 硬编码 | ✅ 环境变量动态指定 |
| 任务 ID | ❌ 不支持 | ✅ 支持 |
| 日志格式 | ❌ 各自定义 | ✅ 统一格式 |
| 错误处理 | ❌ 简单 | ✅ 完整 |
| 超时控制 | ❌ 无 | ✅ 有 |
| 平台集成 | ❌ 无 | ✅ 完整 |

### 多爬虫支持

```
当前方案:
✅ 每个任务运行一个爬虫
✅ 容器隔离,独立管理
✅ 支持任意爬虫名称

未来优化:
🔄 支持一个容器运行多个爬虫
🔄 资源更高效
🔄 减少容器开销
```

### Crawlo 框架的灵活性

```python
# Crawlo 框架支持:

# 1. 单个爬虫
await CrawlerProcess().crawl('of_week')

# 2. 多个爬虫
await CrawlerProcess().crawl(['of_week', 'of_week_adaptive'])

# 3. 自动发现
# 框架会自动扫描 spiders/ 目录
# 注册所有定义的爬虫类

# 4. 动态指定
# 通过爬虫名称字符串启动
# 不需要导入具体的爬虫类
```

---

## ✅ 回答你的疑问

### 1. 为什么不用项目的 run.py?

**答**: 项目的 run.py 硬编码了爬虫名称,无法动态指定。spider-runner/run_spider.py 通过环境变量动态读取,支持运行项目中的任意爬虫。

### 2. 如何支持多个爬虫?

**答**: 
- **当前**: 每个任务创建一个容器,通过 `SPIDER_NAME` 环境变量指定运行哪个爬虫
- **未来**: 可以支持 `SPIDER_NAMES=spider1,spider2,spider3`,一个容器运行多个爬虫

### 3. run_spider.py 的作用是什么?

**答**: 
1. **统一入口** - 所有爬虫都通过它启动
2. **动态配置** - 通过环境变量指定爬虫名称
3. **标准化** - 统一日志格式、错误处理
4. **平台集成** - 支持任务 ID、API 等平台特性
5. **资源控制** - Docker 容器级别的资源限制

---

**run_spider.py 是 CrawloPilot 平台的标准启动器,不是替代项目的 run.py,而是提供更灵活、更标准化的运行方式!** 🎯
