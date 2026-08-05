# CrawloPilot - 爬虫管理部署平台

CrawloPilot 是 Crawlo 爬虫框架的配套管理部署平台，提供爬虫项目全生命周期管理能力。

## V1 功能特性

- 用户认证与权限管理（JWT + RBAC）
- 项目管理 + 代码文件上传（本地文件系统存储）
- 爬虫管理（创建、代码文件浏览/编辑、运行/停止）
- 部署执行（本地进程为默认；支持 SSH / Docker 直连 / Agent 三种节点模式）
- 任务管理（状态查询、实时日志、WebSocket 推送、停止/重试）
- 仪表盘（项目/爬虫/任务/节点统计）

## V2 规划（v1 已裁剪）

Git 仓库管理、调度系统（APScheduler + Celery + DAG）、监控告警、数据质量、代理池、API 管理、操作审计。

## 技术栈

- **后端**: FastAPI + Uvicorn + SQLAlchemy
- **前端**: Vue3 + Element Plus + Pinia + Vue Router
- **数据库**: MySQL 8.0 + Redis 7.x
- **执行引擎**: 本地进程（subprocess）/ SSH / Docker

## 快速开始

### 前置要求

- Python 3.10+（本地开发，推荐 conda 环境 `crawlo_pilot`）
- Node.js 18+（本地开发）
- MySQL 8.0 + Redis（本地 Docker 或已有实例均可）
- Docker（可选，仅容器模式需要）

### 本地开发环境（推荐，无需 Docker）

```bash
# 1. 激活 conda 环境并安装依赖
conda activate crawlo_pilot
cd backend
pip install -r requirements.txt

# 2. 配置数据库连接（编辑 .env，或使用 Docker 启动 MySQL/Redis）
#    docker-compose up -d mysql redis

# 3. 启动后端
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问 API 文档：http://localhost:8000/docs

```bash
# 4. 启动前端
cd frontend
npm install
npm run dev
```

访问前端：http://localhost:3000

### Docker Compose 部署

```bash
docker-compose up -d
docker-compose ps
docker-compose logs -f
```

Compose 仅包含 v1 必需服务：`api-server`、`frontend`、`mysql`、`redis`。

## 爬虫部署流程（v1）

```text
登录 → 创建项目 → 创建爬虫 → 上传/复制爬虫代码
  → 触发运行（本地进程模式）→ 查看任务状态/实时日志 → 停止/重试
```

无 Docker 环境下默认使用本地进程模式执行，不依赖 Celery Worker，一次运行即可打通
「项目 → 爬虫 → 代码 → 执行 → 状态 → 日志」全链路。

分布式节点三种接入方式：

- **SSH 直连**：控制端通过 SSH 上传代码并远程执行
- **Docker 直连**：直连节点 Docker API，基础镜像复用 + 任务镜像秒级构建
- **Agent 代理**：节点上运行轻量 agent 程序反向注册（见 `agent/` 目录）

## 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI 服务 |
| 前端 | 3000/8080 | Vue3 开发/生产 |
| MySQL | 3306 | 数据库 |
| Redis | 6379 | 缓存/队列 |

## 项目结构

```
CrawloPilot/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/v1/         # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # SQLAlchemy 模型
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # 业务逻辑（部署/执行/节点/日志）
│   │   └── main.py         # 应用入口
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Vue3 前端
│   ├── src/
│   │   ├── api/            # API 调用
│   │   ├── components/     # 组件
│   │   ├── views/          # 页面
│   │   └── router/         # 路由
│   ├── Dockerfile
│   └── package.json
├── docker/                  # Docker 配置（mysql/redis/spider-runner）
├── docker-compose.yml
├── examples/                # 示例爬虫（ofweek_standalone）
├── tests/                   # 测试（test_deployment_flow.py 为部署流程验收测试）
└── docs/                    # 文档
```

## API 文档

启动后端服务后访问：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 项目文档

完整文档见 [docs/README.md](docs/README.md)，重点先读：

- [设计哲学](docs/DESIGN_PHILOSOPHY.md) —— 项目为什么这样设计
- [部署执行](docs/modules/04-execution.md) —— 本地/SSH/Docker/Agent 四种执行方式
- [节点管理](docs/modules/05-nodes.md) —— 分布式节点接入
- [任务与实时日志](docs/modules/06-tasks.md) —— 可观测性设计

## 数据库

主要表：`user`、`role`、`team`、`project`、`project_version`、`spider`、
`task_instance`、`node`、`container`、`deploy`、`schedule`、`environment_config`。

## 测试

```bash
# 部署流程验收测试（需先启动后端）
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000
python tests/test_deployment_flow.py
```

## 许可证

MIT License
