# 爬虫管理开发指南

## 概述
爬虫管理是 CrawloPilot 的核心功能,提供爬虫的创建、编辑、运行、代码管理和监控能力。

## 项目定位
- **平台类型**: 爬虫项目部署和管理平台(类似 Scrapy Cloud)
- **主打框架**: Crawlo 框架(分布式爬虫框架)
- **支持框架**: Crawlo ⭐、Scrapy、Selenium、Playwright、Requests、自定义

---

## 爬虫创建流程

### 分步向导设计

#### 步骤1: 基本信息
- 爬虫名称(必填)
- 所属项目(必填,支持URL参数预填)
- 爬虫类型(下拉选择,**Crawlo 排在第一位并标记推荐**)
  - Crawlo ⭐推荐 - 分布式爬虫框架
  - Scrapy - Python爬虫框架
  - Selenium - 浏览器自动化
  - Playwright - 现代浏览器自动化
  - Requests - HTTP请求库
  - 自定义 - 其他框架或脚本
- 描述(可选)

#### 步骤2: 代码来源(三选一)
1. **从 Git 仓库导入**
   - Git 仓库地址(必填)
   - 认证方式(密码/Token 或 SSH)
   - 分支名称(默认 main)
   - 自动克隆按钮

2. **本地上传代码**
   - 拖拽上传区域
   - 支持 zip 文件
   - 自动解压到爬虫目录

3. **创建空爬虫**
   - 自动生成基础目录结构
   - 根据框架类型生成模板文件
   - 后续在详情页编写代码

#### 步骤3: 运行配置(可选)
- 入口文件路径
- 调度配置(是否定时运行)
- 超时时间
- 重试策略

---

## 列表页面

### 视图模式
支持**卡片视图**和**列表视图**切换,默认卡片视图。

### 卡片视图特性
- 框架类型使用彩色标签
- 显示成功率百分比
- 相对时间显示(刚刚、X分钟前、X小时前)
- 快捷操作按钮(运行、代码、更多)
- hover悬浮效果

### 框架标签配色
```javascript
const colorMap = {
  crawlo: '#722ED1',    // 紫色 - Crawlo ⭐
  scrapy: '#FA8C16',    // 橙色
  selenium: '#1890FF',  // 蓝色
  playwright: '#52C41A', // 绿色
  requests: '#8C8C8C',  // 灰色
  custom: '#13C2C2'     // 青色
}
```

---

## 详情页面

### Tab 结构(按使用频率)
1. **代码结构**(默认) - 文件树 + 代码编辑器
2. **运行监控** - 运行状态、统计、日志
3. **调度配置** - 定时任务设置
4. **Git 管理** - 版本控制
5. **基本信息** - 爬虫元数据

### 顶部操作栏
- 左侧: 返回按钮 + 爬虫名称 + 框架标签 + 状态标签
- 右侧: 运行按钮 + 代码按钮 + 更多操作下拉菜单

---

## 数据模型

### SpiderType 枚举
**重要**: 数据库模型、Pydantic Schema、前端枚举必须保持一致!

```python
# backend/app/models/__init__.py
class SpiderType(str, enum.Enum):
    CRAWLO = "crawlo"              # Crawlo 框架(主打)
    SCRAPY = "scrapy"              # Scrapy 框架
    SELENIUM = "selenium"          # Selenium
    PLAYWRIGHT = "playwright"      # Playwright
    REQUESTS = "requests"          # Requests
    CUSTOM = "custom"              # 自定义

# backend/app/schemas/spider.py
class SpiderType(str, Enum):
    CRAWLO = "crawlo"
    SCRAPY = "scrapy"
    SELENIUM = "selenium"
    PLAYWRIGHT = "playwright"
    REQUESTS = "requests"
    CUSTOM = "custom"
```

### Spider 模型关键字段
```python
class Spider(Base):
    __tablename__ = "spider"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True)
    project_id = Column(BigInteger, ForeignKey("project.id"), nullable=False)
    description = Column(Text)
    spider_type = Column(Enum(SpiderType, values_callable=lambda e: [x.value for x in e]), default=SpiderType.CRAWLO)
    status = Column(Enum(SpiderStatus), default=SpiderStatus.DRAFT)
    
    # Git相关
    git_url = Column(String(512))
    git_auth_type = Column(String(32), default="password")
    git_username = Column(String(128))
    git_password = Column(String(256))
    git_ssh_key = Column(Text)
    git_branch = Column(String(128), default="main")
    
    # 代码相关
    code_path = Column(String(512))
    entry_file = Column(String(256))
    
    # 统计
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
```

---

## API 接口

### 爬虫管理 API
```python
GET    /api/v1/spiders              # 获取爬虫列表
POST   /api/v1/spiders              # 创建爬虫
GET    /api/v1/spiders/{id}         # 获取爬虫详情
PUT    /api/v1/spiders/{id}         # 更新爬虫
DELETE /api/v1/spiders/{id}         # 删除爬虫
POST   /api/v1/spiders/{id}/run     # 运行爬虫
POST   /api/v1/spiders/{id}/stop    # 停止爬虫
```

### Git 管理 API
```python
POST   /api/v1/spiders/{id}/git/clone      # 克隆仓库
POST   /api/v1/spiders/{id}/git/pull       # 拉取代码
POST   /api/v1/spiders/{id}/git/push       # 推送代码
GET    /api/v1/spiders/{id}/git/branches   # 获取分支列表
POST   /api/v1/spiders/{id}/git/branch     # 切换分支
GET    /api/v1/spiders/{id}/git/commits    # 获取提交历史
GET    /api/v1/spiders/{id}/git/status     # 获取仓库状态
```

### 文件管理 API
```python
GET    /api/v1/spiders/{id}/files/tree     # 获取文件树
GET    /api/v1/spiders/{id}/files/content  # 获取文件内容
POST   /api/v1/spiders/{id}/files/content  # 保存文件内容
POST   /api/v1/spiders/{id}/files/create   # 创建文件/目录
DELETE /api/v1/spiders/{id}/files          # 删除文件/目录
```

---

## 前端组件

### 关键文件
- `/frontend/src/views/Spiders.vue` - 爬虫列表和创建
- `/frontend/src/views/SpiderDetail.vue` - 爬虫详情
- `/frontend/src/api/spider.js` - 爬虫 API
- `/frontend/src/api/spider-git.js` - Git 管理 API

### Element Plus 注意事项
```vue
<!-- ✅ 正确: el-radio-button 使用 value -->
<el-radio-button value="git">Git 仓库</el-radio-button>

<!-- ❌ 错误: 不要使用 label -->
<el-radio-button label="git">Git 仓库</el-radio-button>

<!-- ✅ 正确: el-option value 使用字符串 -->
<el-option label="全部" value="">

<!-- ❌ 错误: value 不能使用 null -->
<el-option label="全部" :value="null">
```

---

## 常见问题

### 1. 500 错误: ResponseValidationError
**原因**: 数据库中有 `spider_type='crawlo'` 的数据,但 Pydantic Schema 中没有定义 `CRAWLO` 枚举值。

**解决**: 确保 `backend/app/schemas/spider.py` 中的 `SpiderType` 枚举包含所有数据库中的值。

```python
class SpiderType(str, Enum):
    CRAWLO = "crawlo"  # 必须添加
    SCRAPY = "scrapy"
    # ...
```

### 2. 枚举值不匹配
**原因**: 数据库模型的 Enum 和 Pydantic Schema 的 Enum 不一致。

**解决**: 
- 数据库模型使用 `values_callable=lambda e: [x.value for x in e]` 存储小写值
- Pydantic Schema 直接使用枚举值
- 两者必须保持一致

### 3. 前端视图不更新
**解决**: 
- 使用 `Cmd + Shift + R` 强制刷新浏览器
- 检查 Vite HMR 是否正常工作
- 清除浏览器缓存和 Service Worker

---

## 最佳实践

### 创建爬虫
1. 优先推荐 Crawlo 框架
2. 提供清晰的示例和说明
3. 支持多种代码来源方式
4. 自动生成基础结构

### 代码管理
1. 优先使用 Git 集成
2. 支持本地上传作为备选
3. 提供在线代码编辑器
4. 自动保存和版本控制

### 运行监控
1. 实时显示运行状态
2. 统计成功率和运行次数
3. 提供详细的运行日志
4. 支持手动触发运行

---

## 示例数据

项目包含示例爬虫数据,可通过以下脚本添加:

```bash
cd backend
python add_sample_data.py
```

示例数据包括:
- 电商数据采集项目(3个Crawlo爬虫)
- 新闻资讯采集项目(2个爬虫)

---

**最后更新**: 2026-04-27

---

## 本地爬虫执行（LocalExecutor）

### 概述
当 Docker 不可用时，系统自动使用 `LocalExecutor` 在本地通过 subprocess 运行爬虫。

### 核心文件
- `backend/app/services/local_executor.py`

### 架构

```
API端点 (spiders.py/execution.py)
    ↓
LocalExecutor (单例，管理所有进程)
    ├── LocalSpiderProcess (task_id_1)  ← stdout读取线程
    ├── LocalSpiderProcess (task_id_2)  ← stdout读取线程
    └── LocalSpiderProcess (task_id_3)  ← 监控线程
            ↓
        日志文件: uploads/_task_logs/task_{id}.log
        数据库: TaskInstance (status/duration/pages/items/errors)
```

### 执行流程

```
1. POST /api/v1/spiders/{id}/run
   ↓
2. execute_task(config) 创建 LocalSpiderProcess
   ↓
3. process.start(config)
   ├── 构建命令: entry_file → crawlo run → run.py → Python内联
   ├── 创建日志文件
   └── 启动 subprocess.Popen
   ↓
4. 启动两个守护线程
   ├── stdout读取线程: 实时写入日志文件
   └── 进程监控线程: wait() → 解析指标 → 更新DB → 延迟清理
   ↓
5. 进程完成或超时
   ├── 收集剩余输出
   ├── parse_metrics_from_logs() 解析 pages/items/errors
   └── _update_task_completion() 更新数据库终态
```

### 自动命令发现（_build_command）

LocalSpiderProcess 按以下优先级自动选择执行命令：

1. **entry_file 指定**: 如果 config.entry_file 非空且文件存在，使用它；.py 用 python，.sh 用 bash
2. **crawlo run**: 如果 spider_name_to_run 有值且系统安装了 crawlo CLI
3. **自动发现**: 在代码目录查找 `run.py` → `main.py` → `crawl.py` → `start.py`
4. **直接 Python**: 使用 `python -c "import asyncio; from crawlo.crawler import CrawlerProcess; ..."` 内联执行

### 进程生命周期状态

| 状态 | 说明 | 触发条件 |
|------|------|----------|
| PENDING | 等待执行 | 刚创建 |
| RUNNING | 运行中 | process.start() 成功后 |
| PAUSED | 已暂停 | pause_task() → 发送 SIGSTOP/SIGBREAK |
| SUCCESS | 成功完成 | 进程 exit_code == 0 |
| FAILED | 执行失败 | 进程 exit_code != 0 或异常 |
| TIMEOUT | 执行超时 | 超过 config.timeout |
| CANCELLED | 用户取消 | stop_task() 被调用 |

### 日志持久化

- **目录**: `backend/uploads/_task_logs/task_{task_id}.log`
- **方式**: stdout 通过守护线程实时写入
- **编码**: UTF-8，errors='replace' 容错
- **读取**: `get_task_logs(tail=100)` 从文件读取末尾N行

### 爬虫指标自动统计

从日志文件中使用正则表达式解析：

```python
# pages/items 解析
r'(?:Crawled|crawled|已爬取)\s+(\d+)\s+(?:pages?|页).*?(\d+)\s+(?:items?|条)'

# errors 统计
r'\[(?:ERROR|WARNING)\]'  # 统计匹配次数
```

解析结果写入 TaskInstance 表：`pages_crawled`, `items_scraped`, `errors_count`, `duration`

### 停止/暂停/恢复

| API | 方法 |
|-----|------|
| 停止 | `stop_task()` → 发送 SIGTERM → 超时后 SIGKILL → 更新 CANCELLED |
| 暂停 | `pause_task()` → Windows: SIGBREAK / Linux: SIGSTOP |
| 恢复 | `resume_task()` → Linux: SIGCONT（Windows不支持） |

### 超时控制

- 默认超时: 3600秒（1小时），通过 `config.timeout` 配置
- 超时后: 先 SIGTERM 等待5秒，再 SIGKILL 强制终止
- 超时任务状态: `TIMEOUT`

### 清理策略

- 进程完成后延迟 300秒（5分钟）从 `active_tasks` 字典中移除
- 延迟清理期间仍可通过 `get_task_status()` 和 `get_task_logs()` 查询
- 日志文件保留在磁盘上，不做自动删除
