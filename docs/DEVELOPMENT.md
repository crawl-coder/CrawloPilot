# CrawloPilot 开发指南

## 当前进度

### ✅ Phase 1: 核心基座（已完成）
- [x] 项目结构搭建
- [x] 数据库模型设计
- [x] JWT 认证系统
- [x] 用户注册/登录 API
- [x] 项目管理 CRUD API
- [x] 项目版本管理 API
- [x] 前端登录页面
- [x] 前端主布局
- [x] 前端项目管理页面
- [x] Docker Compose 配置

### ✅ Phase 2: 部署引擎（已完成）
- [x] 数据库模型扩展（Deploy/Node/Container）
- [x] Docker 服务层（镜像/容器/网络管理）
- [x] 部署服务层（3 种部署策略）
- [x] Celery 异步任务
- [x] 部署管理 API
- [x] 节点管理 API
- [x] 前端部署管理页面
- [x] 前端节点管理页面

### ✅ Phase 3: 调度系统（已完成）
- [x] APScheduler 调度器集成
- [x] DAG 依赖解析器
- [x] 调度任务存储
- [x] Celery 调度任务
- [x] 调度配置 API
- [x] 任务实例 API
- [x] 前端调度管理页面
- [x] 前端任务实例页面

### ✅ Phase 4: 监控告警（已完成）
- [x] Prometheus 监控指标
- [x] 告警引擎和规则管理
- [x] 通知器（邮件/钉钉/企微）
- [x] 监控数据 API
- [x] 告警管理 API
- [x] 前端监控 Dashboard
- [x] 前端告警管理页面

### 🚧 Phase 5-8: 待开发

## 如何继续开发

### Phase 2: 部署引擎（Docker 容器管理）

#### 需要创建的文件：

1. **后端服务层**
```bash
backend/app/services/
├── docker_service.py      # Docker Engine 封装
├── deploy_service.py      # 部署策略实现
└── node_service.py        # 节点管理
```

2. **Celery 任务**
```bash
backend/app/workers/
├── celery_app.py          # Celery 应用配置
├── deploy_tasks.py        # 部署任务
└── container_tasks.py     # 容器管理任务
```

3. **API 路由**
```bash
backend/app/api/v1/
├── deploy.py              # 部署接口
└── nodes.py               # 节点管理接口
```

4. **前端页面**
```bash
frontend/src/views/
├── Deploy.vue             # 部署管理
├── Nodes.vue              # 节点管理
└── Containers.vue         # 容器监控
```

#### 核心实现要点：

```python
# backend/app/services/docker_service.py 示例
import docker
from app.core.config import settings

class DockerService:
    def __init__(self):
        self.client = docker.DockerClient(base_url=settings.DOCKER_HOST)
    
    def build_image(self, project_path, tag):
        """构建 Docker 镜像"""
        image, logs = self.client.images.build(
            path=project_path,
            tag=tag,
            rm=True
        )
        return image
    
    def create_container(self, image, name, environment=None):
        """创建容器"""
        container = self.client.containers.run(
            image,
            name=name,
            environment=environment,
            detach=True,
            restart_policy={"Name": "unless-stopped"}
        )
        return container
    
    def get_container_logs(self, container_id):
        """获取容器日志"""
        container = self.client.containers.get(container_id)
        return container.logs()
```

---

### Phase 3: 调度系统

#### 需要创建的文件：

1. **调度器**
```bash
backend/app/scheduler/
├── scheduler.py           # APScheduler 配置
├── dag_parser.py          # DAG 依赖解析
└── job_store.py           # 任务存储
```

2. **Celery 任务**
```bash
backend/app/workers/
└── schedule_tasks.py      # 调度任务
```

3. **API 路由**
```bash
backend/app/api/v1/
├── schedules.py           # 调度配置接口
└── tasks.py               # 任务实例接口
```

4. **前端页面**
```bash
frontend/src/views/
├── Schedules.vue          # 调度列表
├── ScheduleForm.vue       # 调度配置
├── Tasks.vue              # 任务实例
└── TaskDetail.vue         # 任务详情
```

#### 核心实现要点：

```python
# backend/app/scheduler/scheduler.py 示例
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.config import settings
from app.core.database import engine

scheduler = AsyncIOScheduler()

jobstores = {
    'default': SQLAlchemyJobStore(
        engine=engine,
        tablename='apscheduler_jobs'
    )
}

scheduler.configure(jobstores=jobstores)

def add_cron_job(job_id, func, cron_expr, args=None):
    """添加 Cron 定时任务"""
    scheduler.add_job(
        func,
        'cron',
        cron_expr,
        args=args,
        id=job_id,
        replace_existing=True
    )

def start_scheduler():
    scheduler.start()
```

---

### Phase 4: 监控告警

#### 需要创建的文件：

1. **监控服务**
```bash
backend/app/services/
├── monitor_service.py     # 监控数据采集
├── alert_service.py       # 告警引擎
└── log_service.py         # 日志管理
```

2. **WebSocket 处理器**
```bash
backend/app/websockets/
├── __init__.py
└── logs.py                # 日志推送
```

3. **API 路由**
```bash
backend/app/api/v1/
├── monitor.py             # 监控接口
└── alerts.py              # 告警接口
```

4. **前端页面**
```bash
frontend/src/views/
├── Monitor.vue            # 监控 Dashboard
├── Logs.vue               # 日志查看
└── Alerts.vue             # 告警管理
```

#### WebSocket 实现：

```python
# backend/app/websockets/logs.py
from fastapi import WebSocket
from typing import Dict

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[task_id] = websocket
    
    async def send_log(self, task_id: str, message: str):
        if task_id in self.active_connections:
            await self.active_connections[task_id].send_text(message)

manager = ConnectionManager()
```

---

### Phase 5: 数据质量

#### 需要创建的文件：

```bash
backend/app/services/
└── quality_service.py     # 数据质量检测

backend/app/api/v1/
└── quality.py             # 数据质量接口

frontend/src/views/
├── Quality.vue            # 质量报告
└── QualityDetail.vue      # 质量详情
```

---

### Phase 6: 代理池与 API 管理

#### 需要创建的文件：

```bash
backend/app/services/
├── proxy_service.py       # 代理池管理
└── api_manager.py         # API 管理

backend/app/api/v1/
├── proxies.py             # 代理池接口
└── api_configs.py         # API 配置接口

frontend/src/views/
├── Proxies.vue            # 代理池管理
└── ApiConfigs.vue         # API 配置
```

---

### Phase 7: 生产加固

#### 需要实现的功能：

1. **高可用**
   - Redis 分布式锁实现
   - Scheduler 主备切换
   - 数据库连接池优化

2. **安全**
   - HTTPS 配置
   - AES-256 加密
   - IP 白名单
   - 审计日志

3. **灾备**
   - 数据库备份脚本
   - 数据恢复流程

---

### Phase 8: 运维增强

#### 需要实现的功能：

1. **自动扩缩容**
2. **成本控制**
3. **数据导出**
4. **文档中心**

---

## 开发规范

### 后端开发规范

1. **代码风格**
   - 遵循 PEP 8
   - 使用类型提示
   - 添加文档字符串

2. **API 设计**
   - RESTful 风格
   - 统一响应格式
   - 适当的错误处理

3. **数据库**
   - 使用 Alembic 管理迁移
   - 添加索引优化查询
   - 使用事务保证一致性

### 前端开发规范

1. **组件设计**
   - 单一职责
   - Props 验证
   - 事件命名规范

2. **状态管理**
   - 使用 Pinia
   - 模块化组织
   - 持久化存储

3. **样式**
   - 使用 scoped 样式
   - 遵循 Element Plus 设计规范
   - 响应式布局

---

## 测试

### 后端测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio httpx

# 运行测试
pytest backend/tests/
```

### 前端测试

```bash
# 安装测试依赖
npm install --save-dev vitest @vue/test-utils

# 运行测试
npm run test
```

---

## 部署

### 开发环境

```bash
# 启动所有服务
./start.sh

# 查看日志
docker-compose logs -f api-server

# 重启服务
docker-compose restart api-server
```

### 生产环境

```bash
# 使用生产配置
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 扩容
docker-compose up -d --scale api-server=3
```

---

## 常见问题

### 1. 数据库迁移

```bash
cd backend

# 创建迁移
alembic revision --autogenerate -m "add new table"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

### 2. 前端构建

```bash
cd frontend

# 开发模式
npm run dev

# 生产构建
npm run build
```

### 3. Docker 问题

```bash
# 清理无用镜像
docker system prune

# 重建镜像
docker-compose build --no-cache

# 查看容器日志
docker-compose logs -f
```

---

## 下一步行动

1. **立即可做**
   - 启动项目：`./start.sh`
   - 访问 API 文档：http://localhost:8000/docs
   - 测试用户注册登录
   - 测试项目管理功能

2. **短期目标**
   - 完善 Phase 1 的用户管理页面
   - 实现项目包上传功能
   - 添加单元测试

3. **中期目标**
   - 开发 Phase 2 部署引擎
   - 集成 Docker Engine API
   - 实现容器生命周期管理

4. **长期目标**
   - 完成所有 Phase 功能
   - 性能优化
   - 生产环境部署

---

## 资源链接

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [Vue3 文档](https://vuejs.org/)
- [Element Plus 文档](https://element-plus.org/)
- [Docker SDK for Python](https://docker-py.readthedocs.io/)
- [APScheduler 文档](https://apscheduler.readthedocs.io/)
- [Celery 文档](https://docs.celeryq.dev/)
