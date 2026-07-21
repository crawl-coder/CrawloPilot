"""
CrawloPilot 后端应用

爬虫管理部署平台 - FastAPI 后端服务
"""
__version__ = "1.0.0"

# 确保 Docker Desktop 兼容性适配器在任何 docker.from_env() 调用前加载
from app.services.docker_service import _patch_docker_client
_patch_docker_client()
