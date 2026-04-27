from app.api.v1 import auth, projects, deploy, nodes, schedules, tasks, monitoring, alerts, data_quality, proxy_pool, api_management, audit, project_git, users, project_files, spiders, spider_git, execution, websocket
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
from app.core.config import settings
from app.scheduler import scheduler_manager
from prometheus_client import make_asgi_app
import logging

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
    
    # 关闭时停止调度器和执行器（使用 try 防止热重载时被中断导致警告）
    try:
        logger.info("Shutting down scheduler...")
        scheduler_manager.shutdown_scheduler()
        logger.info("Scheduler shutdown complete")
    except Exception as e:
        logger.warning(f"Scheduler shutdown was interrupted: {e}")
    
    try:
        logger.info("Cleaning up TaskExecutor...")
        await executor.cleanup()
        logger.info("TaskExecutor cleanup complete")
    except Exception as e:
        logger.warning(f"TaskExecutor cleanup was interrupted: {e}")


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

# 审计中间件（Phase 7）
from app.middleware.audit import AuditMiddleware
app.add_middleware(AuditMiddleware)

# API请求频率限制中间件
from app.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(projects.router, prefix=settings.API_PREFIX)
app.include_router(project_git.router, prefix=settings.API_PREFIX)
app.include_router(project_files.router, prefix=settings.API_PREFIX)
app.include_router(spiders.router, prefix=settings.API_PREFIX)
app.include_router(spider_git.router, prefix=settings.API_PREFIX)
app.include_router(deploy.router, prefix=settings.API_PREFIX)
app.include_router(nodes.router, prefix=settings.API_PREFIX)
app.include_router(schedules.router, prefix=settings.API_PREFIX)
app.include_router(tasks.router, prefix=settings.API_PREFIX)
app.include_router(monitoring.router, prefix=settings.API_PREFIX)
app.include_router(alerts.router, prefix=settings.API_PREFIX)
app.include_router(data_quality.router, prefix=settings.API_PREFIX)
app.include_router(proxy_pool.router, prefix=settings.API_PREFIX)
app.include_router(api_management.router, prefix=settings.API_PREFIX)
app.include_router(audit.router, prefix=settings.API_PREFIX)
app.include_router(execution.router, prefix=settings.API_PREFIX)

# WebSocket 路由 (不需要 prefix)
app.include_router(websocket.router)

# Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.APP_VERSION}


@app.get("/")
def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }
