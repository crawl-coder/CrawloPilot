# CrawloPilot 项目开发规范

## 项目概述
CrawloPilot 是一个功能完整的爬虫项目部署和管理平台,支持 Crawlo、Scrapy 等多种爬虫框架。

## 项目定位
- **主要功能**: 部署和管理爬虫项目(类似 Scrapy Cloud)
- **主打框架**: Crawlo 框架(分布式爬虫框架)
- **支持框架**: Crawlo ⭐推荐、Scrapy、Selenium、Playwright、Requests、自定义
- **执行模式**: 本地进程模式（默认） / Docker容器模式（需 Docker Desktop）
- **当前状态**: 测试通过率 **100% (18/18)** ✅，P0/P1 问题已修复

## 技术栈
- **后端**: FastAPI, SQLAlchemy, Alembic, APScheduler, Redis
- **前端**: Vue3, Vite, Element Plus, Axios
- **数据库**: MySQL 8.0（远程 117.72.16.51:3306）
- **缓存/队列**: Redis
- **监控**: Prometheus + Grafana
- **容器**: Docker + Docker Compose（当前不可用）
- **爬虫运行**: 本地 subprocess 模式（无需 Docker）

## 项目结构
```
CrawloPilot/
├── backend/app/
│   ├── api/v1/          # API 路由（15个模块）
│   │   ├── spiders.py   # 爬虫管理（含 run/stop 端点）
│   │   ├── execution.py # 任务执行（status/logs/duration）
│   │   └── ...
│   ├── core/            # 核心配置
│   ├── models/          # 数据库模型
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # 业务服务层
│   │   ├── local_executor.py  # ⭐本地爬虫执行引擎（2026-04-27 重写）
│   │   └── ...
│   ├── middleware/      # 中间件（审计/限流）
│   ├── scheduler/       # 任务调度
│   ├── monitoring/      # 监控告警
│   └── workers/         # Celery 异步任务
├── frontend/src/
│   ├── api/             # API 封装（10个模块）
│   ├── views/           # 页面组件（14个页面）
│   └── router/          # 路由配置
├── docker/              # Docker 配置
├── tests/
│   ├── unit/            # 单元测试（9个文件）
│   ├── test_deployment_flow.py  # ⭐核心部署流测试（18项）
│   ├── test_phase3.py ~ test_phase7.py  # 阶段测试
│   └── run_all_tests.py
├── .qoder/skills/       # ⭐AI辅助开发技能说明
└── docs/                # 项目文档
```

## 功能模块

### 已完成模块 ✅
1. **用户认证** - JWT Token, 权限控制
2. **项目管理** - CRUD, Git集成, 本地上传
3. **爬虫管理** - 分步创建向导、卡片/列表视图、代码编辑、Git管理
4. **部署管理** - Docker容器化, 多节点部署
5. **任务调度** - Cron/间隔调度, DAG依赖
6. **监控告警** - Prometheus指标, 多渠道通知
7. **数据质量** - 检测规则, 统计分析
8. **代理池** - 健康检查, 智能分配
9. **API管理** - 配置管理, 限流熔断
10. **安全审计** - 操作日志, 权限审计

### 近期修复 🔧
1. **LocalExecutor** - 完整重写，支持本地进程生命周期管理
2. **进程监控** - 线程自动监控进程完成，更新DB终态
3. **日志持久化** - stdout实时写入 `uploads/_task_logs/task_{id}.log`
4. **指标统计** - 自动解析 pages/items/errors 并入库
5. **asyncio.run() 修复** - 改为 await 避免事件循环冲突
6. **MySQL ENUM 修复** - 添加 PAUSED/CANCELLED 枚举值

## 开发规范

### 后端规范
1. **代码风格**: PEP 8, 使用类型提示
2. **数据库**: 使用 Alembic 管理迁移
3. **API 设计**: RESTful 风格, 统一响应格式
4. **错误处理**: 使用 HTTPException, 适当的错误码
5. **异步任务**: 使用 Celery, 任务放在 workers/ 目录

### 前端规范
1. **组件**: 单一职责, 使用 Composition API
2. **状态管理**: 优先使用局部状态
3. **样式**: 使用 scoped 样式, 遵循 Element Plus 设计
4. **API 调用**: 统一封装在 api/ 目录
5. **Element Plus**: el-radio-button 使用 value 而非 label (3.0兼容)
6. **ElOption**: value 不能使用 null, 使用空字符串 ""

### Git 提交规范
- feat: 新功能
- fix: 修复 bug
- docs: 文档更新
- style: 代码格式
- refactor: 重构
- test: 测试
- chore: 构建/工具

## 常用命令

### 启动服务

**Windows (PowerShell) ⭐推荐**
```powershell
# 一键启动前后端
.\start-dev.ps1

# 停止服务
.\start-dev.ps1 -stop

# 重启
.\start-dev.ps1 -restart
```

**Linux/macOS (Bash)**
```bash
./start-dev.sh
```

**手动启动**
```bash
# 后端
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 前端（新终端）
cd frontend
npm run dev
```

### 数据库操作
```bash
cd backend
alembic revision --autogenerate -m "描述"
alembic upgrade head
alembic downgrade -1
```

### 测试
```bash
# 运行完整的部署流程测试（18项）
cd backend
python ../tests/test_deployment_flow.py

# 运行所有测试
python ../tests/run_all_tests.py

# 运行单元测试
pytest ../tests/unit/ -v

# 运行阶段测试
python ../tests/test_phase7.py
```

## 默认账号
- 用户名: admin
- 密码: admin123

## 访问地址
- 前端: http://localhost:3000
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

## 重要配置

### API路径规范
- 所有列表查询API使用**无尾部斜杠**: `/projects`, `/deploys`
- FastAPI自动307重定向会保留Authorization header
- 具体资源API: `/projects/1`, `/schedules/5`

### 前端开发注意
- Element Plus `<el-radio-button>` 使用 `value` 属性而非 `label` (3.0兼容)
- Element Plus `<el-option>` 的 value 不能使用 `null`,使用空字符串 `""`
- Axios请求会自动处理307重定向
- 使用 `Cmd + Shift + R` 强制刷新浏览器缓存
- Vite代理配置使用 `127.0.0.1` 而非 `localhost` 避免IPv6解析问题

### 爬虫管理注意
- 爬虫类型枚举: crawlo(主打), scrapy, selenium, playwright, requests, custom
- Pydantic Schema 和数据库模型枚举值必须保持一致
- 创建爬虫采用分步向导: 基本信息 → 代码来源 → 运行配置
- 列表页支持卡片视图和列表视图切换
- 详情页Tab顺序: 代码结构 → 运行监控 → 调度配置 → Git管理 → 基本信息

## 已知问题 🐛

1. **Docker 模式不支持**：当前环境 Docker Desktop 不可用，所有任务以本地进程模式运行
2. **Celery 调度报错**：`execute_schedule_task()` 参数传递异常（APScheduler + Celery 兼容性问题），控制台会周期性打印 TypeError，但不影响主流程
3. **前端未联调**：前端可能不兼容新的本地模式 API 响应格式
4. **并发未限制**：当前无同时运行进程数上限

## 关键文件（继续工作从这里开始）

### 核心服务
- `backend/app/services/local_executor.py` - 本地爬虫执行引擎，管理进程生命周期
- `backend/app/api/v1/spiders.py` - 爬虫 API（run/stop 端点）
- `backend/app/api/v1/execution.py` - 任务执行 API（status/logs 端点）
- `backend/app/models/__init__.py` - 数据模型（TaskInstance 含 pages/items/errors/duration）

### 测试
- `tests/test_deployment_flow.py` - 完整部署流程测试（18项，100%通过）
- `tests/unit/` - 模块级单元测试（9个文件）

### 配置
- `.env` - 远程 MySQL 连接配置
- `backend/app/core/config.py` - 配置类（支持 SQLite/MySQL 切换）
- `start-dev.ps1` - PowerShell 快速启动脚本
- `start-dev.sh` - Bash 快速启动脚本
