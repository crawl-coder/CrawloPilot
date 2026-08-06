from contextlib import asynccontextmanager
import logging
import asyncio
import os
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings

# 应用日志基础配置（uvicorn 默认不配置 root logger，业务模块的 INFO 日志会丢失）
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# SQLAlchemy echo 很吵，业务日志需要可读性
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def _run_node_health_check():
    """节点健康检查（在后台线程执行，避免同步探测阻塞事件循环）"""
    from app.core.database import SessionLocal
    from app.services.node_service import NodeService
    from app.services.server_service import ServerService
    db = SessionLocal()
    try:
        NodeService(db).check_all_nodes_health_light()
        ServerService(db).aggregate_all_servers()
    finally:
        db.close()


async def _node_health_monitor_loop():
    """后台节点健康检查：每 60 秒轻量探活一次"""
    while True:
        try:
            await asyncio.to_thread(_run_node_health_check)
        except Exception as e:
            logger.warning(f"节点健康检查失败: {e}")
        await asyncio.sleep(60)


async def _task_log_cleanup_loop():
    """任务日志保留清理：默认保留 30 天，可用 TASK_LOG_RETENTION_DAYS 配置（0 关闭）"""
    while True:
        try:
            retention_days = int(os.environ.get("TASK_LOG_RETENTION_DAYS", "30"))
            if retention_days > 0:
                logs_dir = Path(settings.UPLOAD_DIR) / "_task_logs"
                if logs_dir.is_dir():
                    cutoff = time.time() - retention_days * 86400
                    removed = 0
                    for f in logs_dir.glob("task_*.log"):
                        try:
                            if f.stat().st_mtime < cutoff:
                                f.unlink()
                                removed += 1
                        except OSError:
                            continue
                    if removed:
                        logger.info(f"任务日志清理: 删除 {removed} 个超过 {retention_days} 天的日志")
        except Exception as e:
            logger.warning(f"任务日志清理失败: {e}")
        await asyncio.sleep(86400)


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

    # 启动任务日志保留清理（每天执行一次）
    log_cleanup_task = asyncio.create_task(_task_log_cleanup_loop())

    # 启动定时调度器（进程内 APScheduler）
    from app.services.scheduler_service import get_scheduler_service
    scheduler_service = get_scheduler_service()
    scheduler_service.start()

    yield

    # 关闭时清理执行器
    try:
        health_task.cancel()
        log_cleanup_task.cancel()
        scheduler_service.shutdown()
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
from app.api.v1 import spiders, git_credentials
app.include_router(spiders.router, prefix=settings.API_PREFIX)
app.include_router(git_credentials.router, prefix=settings.API_PREFIX)

# 部署与节点
from app.api.v1 import deploy, nodes, agent, servers
app.include_router(deploy.router, prefix=settings.API_PREFIX)
app.include_router(nodes.router, prefix=settings.API_PREFIX)
app.include_router(agent.router, prefix=settings.API_PREFIX)
app.include_router(servers.router, prefix=settings.API_PREFIX)

# 任务
from app.api.v1 import tasks, execution
app.include_router(tasks.router, prefix=settings.API_PREFIX)
app.include_router(execution.router, prefix=settings.API_PREFIX)

# 定时任务
from app.api.v1 import schedules
app.include_router(schedules.router, prefix=settings.API_PREFIX)

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
