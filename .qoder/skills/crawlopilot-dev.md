# CrawloPilot 项目开发规范

## 项目概述
CrawloPilot 是一个功能完整的爬虫管理平台，提供项目全生命周期管理能力。

## 技术栈
- **后端**: FastAPI, SQLAlchemy, Alembic, APScheduler, Redis
- **前端**: Vue3, Vite, Element Plus, Axios
- **数据库**: MySQL 8.0
- **缓存/队列**: Redis
- **监控**: Prometheus + Grafana
- **容器**: Docker + Docker Compose

## 项目结构
```
CrawloPilot/
├── backend/app/
│   ├── api/v1/          # API 路由（13个模块）
│   ├── core/            # 核心配置
│   ├── models/          # 数据库模型
│   ├── schemas/         # Pydantic schemas
│   ├── services/        # 业务服务层
│   ├── middleware/      # 中间件（审计/限流）
│   ├── scheduler/       # 任务调度
│   ├── monitoring/      # 监控告警
│   └── workers/         # Celery 异步任务
├── frontend/src/
│   ├── api/             # API 封装（10个模块）
│   ├── views/           # 页面组件（14个页面）
│   └── router/          # 路由配置
├── docker/              # Docker 配置
├── tests/               # 测试代码
└── docs/                # 项目文档
```

## 功能模块

### 已完成模块 ✅
1. **用户认证** - JWT Token, 权限控制
2. **项目管理** - CRUD, Git集成, 本地上传
3. **部署管理** - Docker容器化, 多节点部署
4. **任务调度** - Cron/间隔调度, DAG依赖
5. **监控告警** - Prometheus指标, 多渠道通知
6. **数据质量** - 检测规则, 统计分析
7. **代理池** - 健康检查, 智能分配
8. **API管理** - 配置管理, 限流熔断
9. **安全审计** - 操作日志, 权限审计

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
```bash
# 快速启动（推荐）
./start-dev.sh

# 或使用 dev.sh
./dev.sh
./dev.sh --stop
./dev.sh --restart
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
# 运行所有测试
python tests/run_all_tests.py

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/
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
- Element Plus `<el-option>` 的 value 不能使用 `null`，使用空字符串 `""`
- Axios请求会自动处理307重定向
- 使用 `Cmd + Shift + R` 强制刷新浏览器缓存
