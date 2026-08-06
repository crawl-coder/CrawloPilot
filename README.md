# 🕷️ CrawloPilot

> Crawlo 爬虫框架的配套管理部署平台 —— 项目、爬虫、部署、任务一站式管理。

![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688.svg)
![Vue 3](https://img.shields.io/badge/Frontend-Vue3-4FC08D.svg)
![Crawlo](https://img.shields.io/badge/Crawlo-1.7.2-purple.svg)

CrawloPilot 是围绕 [Crawlo](https://github.com/crawl-coder/Crawlo) 爬虫框架构建的管理平台，
提供爬虫项目的全生命周期管理：创建项目、上传代码、创建爬虫、选择执行节点、
运行任务、实时查看状态与日志、统计运行指标。

## ✨ 特性

- **认证与权限**：JWT + RBAC，用户 / 角色 / 团队
- **项目管理**：项目 CRUD、版本、代码文件上传与在线编辑
- **爬虫管理**：爬虫 CRUD、代码文件树/编辑、运行与停止
- **四种执行模式**：本地进程 / SSH 远程 / Docker 直连 / Agent 节点，执行器可插拔
- **任务全生命周期**：状态机、实时日志（WebSocket）、暂停 / 恢复 / 停止 / 重试 / 删除
- **Server 实体**：真实服务器 × SSH/Docker/Agent 三种执行通道统一管理
- **运行统计**：自动解析爬虫指标（pages / items / errors），回写爬虫运行记录
- **仪表盘**：项目 / 爬虫 / 任务 / 节点概览

## 📚 文档

| 文档 | 说明 |
|------|------|
| [设计哲学](docs/DESIGN_PHILOSOPHY.md) | 项目为什么这样设计、核心决策 |
| [产品设计](docs/PRODUCT_DESIGN.md) | 产品定位、功能模块、技术方案 |
| [模块文档](docs/modules/) | 认证 / 项目 / 爬虫 / 部署执行 / 节点 / 任务 / 前端 / 测试 |
| [Server 管理设计](docs/designs/server-management.md) | 真实服务器实体管理方案 |
| [文档索引](docs/README.md) | 完整文档入口 |
| [Agent 使用说明](agent/README.md) | 节点 Agent 部署手册 |

## 🚀 快速开始

### 环境要求

- Python 3.10+（推荐 conda 环境 `crawlo_pilot`）
- Node.js 18+
- MySQL 8.0 + Redis 7.x（本机或 Docker）
- Docker（可选，仅容器模式需要）

### 本地开发

```bash
# 1. 配置数据库
cp .env.example .env          # 编辑 MySQL/Redis 连接信息（默认指向本机）

# 2. 启动后端
conda activate crawlo_pilot
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 3. 启动前端
cd ../frontend
npm install
npm run dev
```

访问：

- 前端界面：http://localhost:3000
- API 文档：http://localhost:8000/docs
- 默认账号：`admin / admin123`

> 也可以直接使用 `./start-dev.sh` 一键启动前后端。

### Docker Compose

```bash
docker-compose up -d
```

Compose 包含 v1 必需服务：`api-server`、`frontend`、`mysql`、`redis`。

## 🏗️ 架构

```mermaid
flowchart TB
    UI[Web UI (Vue3)] --> API[FastAPI 控制面]
    API --> DB[(MySQL)]
    API --> RD[(Redis)]
    API --> FS[uploads/ 代码与日志]

    subgraph 执行面
        LOCAL[LocalExecutor<br/>本机子进程]
        SSH[SSH 节点<br/>SshExecutor]
        DOCKER[Docker 节点<br/>DockerExecutor]
        AGENT[Agent 节点<br/>crawlo_agent.py]
    end

    API -- deploy_mode 分发 --> LOCAL
    API -- deploy_mode 分发 --> SSH
    API -- deploy_mode 分发 --> DOCKER
    API -- 任务领取/回报 --> AGENT
```

平台（控制面）负责编排、状态、日志与权限；节点（执行面）负责真正运行爬虫。
四种执行方式实现同一套执行器契约（启动 / 状态 / 日志 / 停止），按 `deploy_mode` 分发。

## 📁 项目结构

```text
CrawloPilot/
├── backend/            # FastAPI 后端（API / 服务 / 模型 / 执行器）
│   └── app/
│       ├── api/v1/     # 路由：认证/项目/爬虫/执行/节点/服务器/Agent
│       ├── services/   # 业务与执行器（local/ssh/docker/agent）
│       └── models/     # SQLAlchemy 模型
├── frontend/           # Vue3 前端
├── agent/              # 节点 Agent 程序（纯标准库）
├── docker/             # Docker 配置
├── docs/               # 设计哲学 / 产品设计 / 模块文档
├── examples/           # 示例爬虫（ofweek_standalone）
├── tests/              # 测试
└── docker-compose.yml
```

## ✅ 测试

```bash
# 部署流程验收测试（需先启动后端）
python tests/test_deployment_flow.py
```

完整测试说明见 [docs/modules/08-testing.md](docs/modules/08-testing.md)。

## 🗺️ 路线图

**V1（已完成）**：项目 / 爬虫 / 四种执行模式 / 任务与日志 / Server 实体

**V2（规划）**：调度系统、监控告警、Git 管理、数据质量、代理池 / API 管理、操作审计

详见 [docs/REMAINING_WORK.md](docs/REMAINING_WORK.md)。

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。开发前请先阅读 [docs/](docs/README.md) 下的设计哲学与模块文档。

## 📄 License

[MIT](LICENSE)
