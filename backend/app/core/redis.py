"""
Redis 连接管理（Wave D）

提供全局 Redis 连接池，启动时自动探测可用性。
REDIS_URL 未配置或连接失败时退化为 no-op（不影响 V1 standalone 模式）。
"""
import logging
import os
from typing import Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_pool: Optional[redis.ConnectionPool] = None
_client: Optional[redis.Redis] = None
_available = False


def init_redis() -> bool:
    """初始化 Redis 连接池。返回是否可用。"""
    global _pool, _client, _available

    url = settings.REDIS_URL
    if not url:
        logger.info("Redis: REDIS_URL 未配置，分布式模式不可用（standalone 模式不受影响）")
        _available = False
        return False

    try:
        _pool = redis.ConnectionPool.from_url(url, max_connections=20, decode_responses=True)
        _client = redis.Redis(connection_pool=_pool)
        _client.ping()
        _available = True
        settings.REDIS_ENABLED = True
        logger.info(f"Redis: 连接成功 ({url})")
        return True
    except Exception as e:
        logger.warning(f"Redis: 连接失败 ({url}): {e}，分布式模式不可用")
        _available = False
        settings.REDIS_ENABLED = False
        return False


def get_redis() -> Optional[redis.Redis]:
    """获取 Redis 客户端（不可用时返回 None）"""
    return _client if _available else None


def is_redis_available() -> bool:
    """Redis 是否可用"""
    return _available


def redis_health() -> dict:
    """健康检查信息"""
    if not settings.REDIS_URL:
        return {"status": "not_configured", "message": "REDIS_URL 未设置"}
    if not _available:
        return {"status": "unavailable", "message": "Redis 连接不可用"}
    try:
        _client.ping()
        info = _client.info("server")
        return {
            "status": "connected",
            "version": info.get("redis_version", "unknown"),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
