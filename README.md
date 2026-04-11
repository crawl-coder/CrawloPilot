# CrawloPilot - 爬虫管理部署平台

CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台，提供爬虫项目全生命周期管理能力。

## 功能特性

### Phase 1：核心基座 ✅
- 用户认证与权限管理（JWT + RBAC）
- 项目管理与版本控制
- 基础 API 框架

### Phase 2-8：待实现
- 部署引擎（Docker 容器管理）
- 调度系统（APScheduler + Celery + DAG）
- 监控告警（Prometheus + WebSocket）
- 数据质量管理
- 代理池与 API 管理
- 生产加固（高可用 + 安全）
- 运维增强（扩缩容 + 成本）

## 技术栈

- **后端**: FastAPI + Uvicorn + SQLAlchemy + Celery + APScheduler
- **前端**: Vue3 + Element Plus + Pinia + Vue Router
- **数据库**: MySQL 8.0 + Redis 7.x
- **存储**: MinIO
- **容器**: Docker Engine API
- **监控**: Prometheus + Grafana
- **网关**: Nginx

## 快速开始

### 前置要求

- Docker >= 20.10
- Docker Compose >= 2.0
- Python 3.10+ (本地开发)
- Node.js 18+ (本地开发)

### 方式一：Docker Compose 一键部署（推荐）

```bash
# 1. 克隆项目
cd /Users/oscar/projects/CrawloPilot

# 2. 启动所有服务
docker-compose up -d

# 3. 查看服务状态
docker-compose ps

# 4. 查看日志
docker-compose logs -f

# 5. 停止所有服务
docker-compose down
```

### 方式二：本地开发环境

#### 后端启动

```bash
# 1. 激活 conda 环境
conda activate crawlo_pilot

# 2. 安装依赖
cd backend
pip install -r requirements.txt

# 3. 启动 MySQL 和 Redis（使用 Docker）
docker-compose up -d mysql redis

# 4. 运行数据库迁移
alembic upgrade head

# 5. 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问 API 文档：http://localhost:8000/docs

#### 前端启动

```bash
# 1. 安装依赖
cd frontend
npm install

# 2. 启动开发服务器
npm run dev
```

访问前端：http://localhost:3000

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| Nginx | 80 | 反向代理 |
| 后端 API | 8000 | FastAPI 服务 |
| 前端 | 3000/8080 | Vue3 开发/生产 |
| MySQL | 3306 | 数据库 |
| Redis | 6379 | 缓存/队列 |
| MinIO | 9000/9001 | 对象存储/API |
| Prometheus | 9090 | 监控指标 |
| Grafana | 3000 | 可视化面板 |

## 项目结构

```
CrawloPilot/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # API 路由
│   │   │   ├── auth.py     # 认证接口
│   │   │   └── projects.py # 项目接口
│   │   ├── core/           # 核心配置
│   │   │   ├── config.py   # 应用配置
│   │   │   ├── database.py # 数据库连接
│   │   │   ├── security.py # 安全认证
│   │   │   └── dependencies.py
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑
│   │   ├── workers/        # Celery 任务
│   │   ├── scheduler/      # APScheduler
│   │   └── main.py         # 应用入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   ├── src/
│   │   ├── api/            # API 调用
│   │   ├── components/     # 组件
│   │   ├── views/          # 页面
│   │   ├── store/          # Pinia 状态
│   │   ├── router/         # 路由
│   │   ├── App.vue
│   │   └── main.js
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.js
├── docker/                  # Docker 配置
│   ├── mysql/
│   ├── redis/
│   ├── minio/
│   ├── nginx/
│   └── prometheus/
├── docker-compose.yml
└── docs/
```

## API 文档

启动后端服务后，访问以下地址查看 API 文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 核心 API

#### 认证
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/auth/register` - 用户注册
- `GET /api/v1/auth/me` - 获取当前用户信息

#### 项目管理
- `GET /api/v1/projects/` - 项目列表
- `POST /api/v1/projects/` - 创建项目
- `GET /api/v1/projects/{id}` - 项目详情
- `PUT /api/v1/projects/{id}` - 更新项目
- `DELETE /api/v1/projects/{id}` - 删除项目
- `POST /api/v1/projects/{id}/versions` - 创建版本
- `GET /api/v1/projects/{id}/versions` - 版本列表

## 数据库模型

### 核心表
- `user` - 用户表
- `team` - 团队表
- `role` - 角色表
- `permission` - 权限表
- `project` - 项目表
- `project_version` - 项目版本表
- `schedule` - 调度配置表
- `task_instance` - 任务实例表
- `alert_rule` - 告警规则表
- `proxy_pool` - 代理池表
- `api_config` - API 配置表
- `audit_log` - 审计日志表

## 开发指南

### 添加新功能

1. **后端 API**
   - 在 `backend/app/api/v1/` 创建新的路由文件
   - 在 `backend/app/main.py` 中注册路由
   - 更新 `backend/app/models/` 数据模型
   - 更新 `backend/app/schemas/` 数据验证

2. **前端页面**
   - 在 `frontend/src/views/` 创建新页面
   - 在 `frontend/src/router/index.js` 添加路由
   - 在 `frontend/src/api/` 创建 API 调用
   - 在 `frontend/src/store/` 添加状态管理

### 数据库迁移

```bash
# 初始化 Alembic（首次）
cd backend
alembic init alembic

# 创建迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

## 环境变量

复制 `.env.example` 为 `.env` 并修改配置：

```bash
# 后端配置
MYSQL_HOST=mysql
MYSQL_PORT=3306
MYSQL_USER=crawlopilot
MYSQL_PASSWORD=crawlopilot123
MYSQL_DATABASE=crawlopilot

REDIS_HOST=redis
REDIS_PORT=6379

SECRET_KEY=your-secret-key-change-in-production

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
```

## 部署

### 生产环境

```bash
# 构建并启动
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 查看日志
docker-compose logs -f

# 扩容 API 服务
docker-compose up -d --scale api-server=3
```

## 监控

- **Prometheus**: http://localhost:9090
- **Grafana**: http://localhost:3000 (admin/admin)
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin123)

## 常见问题

### 1. 数据库连接失败
确保 MySQL 容器已启动并健康：
```bash
docker-compose ps mysql
docker-compose logs mysql
```

### 2. Redis 连接失败
```bash
docker-compose ps redis
docker-compose logs redis
```

### 3. 端口冲突
修改 `docker-compose.yml` 中的端口映射。

## 许可证

MIT License

## 贡献

欢迎提交 Issue 和 Pull Request！

## 联系方式

- 项目地址: https://github.com/your-org/CrawloPilot
- 文档: ./docs/
