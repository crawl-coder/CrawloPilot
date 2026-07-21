from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.scheduler import scheduler_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 启动时初始化调度器和执行器
    logger.info("Initializing scheduler...")
    scheduler_manager.init_scheduler()
    scheduler_manager.start_scheduler()
    logger.info("Scheduler started successfully")
    
    # 初始化任务执行器
    from app.services.task_executor import get_executor
    executor = get_executor()
    await executor.initialize()
    logger.info("TaskExecutor initialized successfully")
    
    yield
    
    # 关闭时停止调度器和执行器
    logger.info("Shutting down scheduler...")
    scheduler_manager.shutdown_scheduler()
    logger.info("Scheduler shutdown complete")
    
    # 清理执行器资源
    logger.info("Cleaning up TaskExecutor...")
    await executor.cleanup()
    logger.info("TaskExecutor cleanup complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## CrawloPilot API

Crawlo 爬虫框架管理平台，提供爬虫项目全生命周期管理能力。

### 功能模块
- **用户认证**: 用户登录、注册、Token管理
- **项目管理**: 项目CRUD、版本管理、部署
- **任务调度**: Cron调度、间隔调度、手动触发
- **运行监控**: 实时监控、指标采集、告警
- **数据质量**: 质量检测、统计报表
- **代理池**: 代理管理、健康检查
- **API管理**: API配置、限流、熔断
- **安全审计**: 操作日志、权限管理

### 认证方式
使用 JWT Bearer Token 认证，在请求头中添加:
```
Authorization: Bearer <your_token>
```

### 错误码说明
| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未认证或Token失效 |
| 403 | 无权限访问 |
| 404 | 资源不存在 |
| 422 | 参数验证失败 |
| 429 | 请求频率超限 |
| 500 | 服务器内部错误 |
""",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "CrawloPilot Team",
        "email": "support@crawlopilot.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 审计中间件
from app.middleware.audit import AuditMiddleware
app.add_middleware(AuditMiddleware)

# API请求频率限制中间件
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# 请求指标中间件
from app.middleware.metrics import MetricsMiddleware
app.add_middleware(MetricsMiddleware)

# ====== 路由注册 ======

# 认证与用户管理
from app.api.v1 import auth, users
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)

# 项目管理
from app.api.v1 import projects, project_git, project_files
app.include_router(projects.router, prefix=settings.API_PREFIX)
app.include_router(project_git.router, prefix=settings.API_PREFIX)
app.include_router(project_files.router, prefix=settings.API_PREFIX)

# 爬虫管理
from app.api.v1 import spiders, spider_git
app.include_router(spiders.router, prefix=settings.API_PREFIX)
app.include_router(spider_git.router, prefix=settings.API_PREFIX)

# 部署与节点
from app.api.v1 import deploy, nodes
app.include_router(deploy.router, prefix=settings.API_PREFIX)
app.include_router(nodes.router, prefix=settings.API_PREFIX)

# 调度与任务
from app.api.v1 import schedules, tasks, execution
app.include_router(schedules.router, prefix=settings.API_PREFIX)
app.include_router(tasks.router, prefix=settings.API_PREFIX)
app.include_router(execution.router, prefix=settings.API_PREFIX)

# 监控与告警
from app.api.v1 import monitoring, alerts
app.include_router(monitoring.router, prefix=settings.API_PREFIX)
app.include_router(alerts.router, prefix=settings.API_PREFIX)

# 数据质量
from app.api.v1 import data_quality
app.include_router(data_quality.router, prefix=settings.API_PREFIX)

# 代理池与 API 管理
from app.api.v1 import proxy_pool, api_management
app.include_router(proxy_pool.router, prefix=settings.API_PREFIX)
app.include_router(api_management.router, prefix=settings.API_PREFIX)

# 审计
from app.api.v1 import audit
app.include_router(audit.router, prefix=settings.API_PREFIX)

# WebSocket 路由 (不需要 prefix)
from app.api.v1 import websocket
app.include_router(websocket.router)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health_check():
    """详细的健康检查端点"""
    import redis as redis_lib
    from sqlalchemy import text

    health_info = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "services": {}
    }

    # 检查数据库
    from app.core.database import SessionLocal
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_info["services"]["database"] = "connected"
    except Exception as e:
        health_info["services"]["database"] = f"error: {str(e)}"
        health_info["status"] = "degraded"

    # 检查 Redis
    try:
        r = redis_lib.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            password=settings.REDIS_PASSWORD,
            socket_connect_timeout=3,
            socket_timeout=3
        )
        r.ping()
        r.close()
        health_info["services"]["redis"] = "connected"
    except Exception as e:
        health_info["services"]["redis"] = f"error: {str(e)}"
        health_info["status"] = "degraded"

    # 检查调度器
    try:
        if scheduler_manager.scheduler and scheduler_manager.scheduler.running:
            health_info["services"]["scheduler"] = "running"
        else:
            health_info["services"]["scheduler"] = "stopped"
            health_info["status"] = "degraded"
    except Exception as e:
        health_info["services"]["scheduler"] = f"error: {str(e)}"

    return health_info


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }
