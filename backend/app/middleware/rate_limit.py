"""
API请求频率限制中间件
使用Redis实现滑动窗口限流算法
"""
import time
import redis
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Callable, Optional
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """基于Redis的滑动窗口限流器"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.prefix = "rate_limit:"
    
    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int, int]:
        """
        检查请求是否允许通过
        
        Args:
            key: 限流键（通常是IP或用户ID）
            max_requests: 时间窗口内最大请求数
            window_seconds: 时间窗口（秒）
        
        Returns:
            tuple: (是否允许, 剩余请求数, 重置时间秒数)
        """
        now = time.time()
        window_start = now - window_seconds
        
        redis_key = f"{self.prefix}{key}"
        
        try:
            # 使用Redis事务
            pipe = self.redis.pipeline()
            
            # 移除过期的请求记录
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # 获取当前窗口内的请求数
            pipe.zcard(redis_key)
            
            # 添加当前请求
            pipe.zadd(redis_key, {str(now): now})
            
            # 设置过期时间
            pipe.expire(redis_key, window_seconds + 1)
            
            results = pipe.execute()
            current_count = results[1]
            
            if current_count >= max_requests:
                # 计算重置时间
                oldest = self.redis.zrange(redis_key, 0, 0, withscores=True)
                if oldest:
                    reset_time = int(oldest[0][1] + window_seconds - now)
                else:
                    reset_time = window_seconds
                
                return False, 0, reset_time
            
            remaining = max_requests - current_count - 1
            return True, remaining, window_seconds
            
        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Redis错误时允许请求通过，避免服务不可用
            return True, max_requests, window_seconds


class RateLimitMiddleware(BaseHTTPMiddleware):
    """API请求频率限制中间件"""
    
    # 不同路径的限流配置
    RATE_LIMITS = {
        # 认证接口：较严格限制（开发环境放宽）
        '/api/v1/auth/login': {'requests': 100, 'window': 60},     # 每分钟100次
        '/api/v1/auth/register': {'requests': 30, 'window': 300},  # 每5分钟30次
        
        # 一般API：中等限制（开发环境放宽）
        '/api/v1/': {'requests': 500, 'window': 60},               # 每分钟500次
        
        # 监控接口：宽松限制
        '/api/v1/monitor/': {'requests': 500, 'window': 60},       # 每分钟500次
        
        # 数据导出：严格限制
        '/api/v1/exports': {'requests': 50, 'window': 60},         # 每分钟50次
    }
    
    # 白名单路径（不限流）
    WHITE_LIST = [
        '/health',
        '/metrics',
        '/docs',
        '/redoc',
        '/openapi.json',
    ]
    
    def __init__(self, app, redis_client: Optional[redis.Redis] = None):
        super().__init__(app)
        if redis_client:
            self.redis = redis_client
        else:
            # 优化Redis连接配置，避免连接超时阻塞
            self.redis = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=2,  # 连接超时2秒
                socket_timeout=2,  # 读写超时2秒
                retry_on_timeout=True,  # 超时自动重试
                health_check_interval=10,  # 每10秒检查连接健康
                max_connections=10  # 最大连接数
            )
        self.limiter = RateLimiter(self.redis)
    
    def _get_rate_limit_key(self, request: Request) -> str:
        """获取限流键"""
        # 优先使用用户ID，其次使用IP
        user_id = getattr(request.state, 'user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # 获取客户端IP
        forwarded = request.headers.get('X-Forwarded-For')
        if forwarded:
            ip = forwarded.split(',')[0].strip()
        else:
            ip = request.client.host if request.client else 'unknown'
        
        return f"ip:{ip}"
    
    def _get_rate_limit_config(self, path: str) -> tuple[int, int]:
        """获取路径对应的限流配置"""
        # 检查白名单
        for white_path in self.WHITE_LIST:
            if path.startswith(white_path):
                return 0, 0  # 不限流
        
        # 查找匹配的限流配置
        for route_path, config in self.RATE_LIMITS.items():
            if path.startswith(route_path):
                return config['requests'], config['window']
        
        # 默认配置
        return 100, 60
    
    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        
        # 获取限流配置
        max_requests, window_seconds = self._get_rate_limit_config(path)
        
        # 白名单路径直接通过
        if max_requests == 0:
            return await call_next(request)
        
        # 获取限流键
        key = self._get_rate_limit_key(request)
        
        # 检查是否允许请求（处理Redis连接异常）
        try:
            allowed, remaining, reset_time = self.limiter.is_allowed(
                key, max_requests, window_seconds
            )
        except Exception as e:
            # Redis完全不可用时，降级为不限流
            logger.warning(f"Rate limiter unavailable, allowing request: {e}")
            allowed, remaining, reset_time = True, max_requests, window_seconds
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {key} on {path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "请求过于频繁，请稍后再试",
                    "retry_after": reset_time
                },
                headers={
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                    "Retry-After": str(reset_time)
                }
            )
        
        # 执行请求
        response = await call_next(request)
        
        # 添加限流头
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response


# 装饰器版本的限流器，用于细粒度控制
def rate_limit(max_requests: int = 100, window_seconds: int = 60, key_func: Callable = None):
    """
    限流装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window_seconds: 时间窗口（秒）
        key_func: 自定义键函数，接收request参数
    """
    def decorator(func):
        async def wrapper(*args, **kwargs):
            # 从参数中获取request
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if request:
                redis_client = redis.Redis(
                    host=settings.REDIS_HOST,
                    port=settings.REDIS_PORT,
                    db=settings.REDIS_DB,
                    password=settings.REDIS_PASSWORD,
                    decode_responses=True
                )
                limiter = RateLimiter(redis_client)
                
                if key_func:
                    key = key_func(request)
                else:
                    key = f"{request.client.host}:{request.url.path}"
                
                allowed, remaining, reset_time = limiter.is_allowed(
                    key, max_requests, window_seconds
                )
                
                if not allowed:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"请求过于频繁，请在{reset_time}秒后重试"
                    )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
