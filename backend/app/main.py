from contextlib import asynccontextmanager
import logging
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _node_health_monitor_loop():
    """后台节点健康检查：每 60 秒轻量探活一次"""
    while True:
        try:
            from app.core.database import SessionLocal
            from app.services.node_service import NodeService
            db = SessionLocal()
            try:
                NodeService(db).check_all_nodes_health_light()
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"节点健康检查失败: {e}")
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动和关闭时的生命周期管理"""
    # 初始化任务执行器
    from app.services.task_executor import get_executor
    executor = get_executor()
    await executor.initialize()
    logger.info("TaskExecutor initialized successfully")

    # 启动节点健康检查后台任务
    health_task = asyncio.create_task(_node_health_monitor_loop())
    logger.info("Node health monitor started")

    yield

    # 关闭时清理执行器
    try:
        health_task.cancel()
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

### 功能模块 (v1)
- **用户认证**: 用户登录、注册、Token管理
- **项目管理**: 项目CRUD、版本管理、代码上传
- **爬虫管理**: 爬虫CRUD、代码文件管理、运行/停止
- **部署执行**: 本地进程 / SSH 远程节点 / Docker
- **任务管理**: 任务实例、状态、日志、WebSocket 实时推送

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

# 请求指标中间件
from app.middleware.metrics import MetricsMiddleware
app.add_middleware(MetricsMiddleware)

# ====== 路由注册 ======

# 认证与用户/团队管理
from app.api.v1 import auth, users, teams
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(users.router, prefix=settings.API_PREFIX)
app.include_router(teams.router, prefix=settings.API_PREFIX)

# 项目管理
from app.api.v1 import projects, project_files
app.include_router(projects.router, prefix=settings.API_PREFIX)
app.include_router(project_files.router, prefix=settings.API_PREFIX)

# 爬虫管理
from app.api.v1 import spiders
app.include_router(spiders.router, prefix=settings.API_PREFIX)

# 部署与节点
from app.api.v1 import deploy, nodes, agent
app.include_router(deploy.router, prefix=settings.API_PREFIX)
app.include_router(nodes.router, prefix=settings.API_PREFIX)
app.include_router(agent.router, prefix=settings.API_PREFIX)

# 任务
from app.api.v1 import tasks, execution
app.include_router(tasks.router, prefix=settings.API_PREFIX)
app.include_router(execution.router, prefix=settings.API_PREFIX)

# 监控（仪表盘与健康检查）
from app.api.v1 import monitoring
app.include_router(monitoring.router, prefix=settings.API_PREFIX)

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

    return health_info


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/health"
    }
