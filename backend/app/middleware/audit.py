"""
Phase 7: 审计中间件 - 自动记录所有写操作
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
import logging

from app.core.database import SessionLocal
from app.services.audit import audit_service

logger = logging.getLogger(__name__)


# 需要审计的 HTTP 方法
AUDIT_METHODS = ["POST", "PUT", "PATCH", "DELETE"]

# 不需要审计的路径
EXCLUDED_PATHS = [
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/metrics",
]

# 审计的操作映射
ACTION_MAP = {
    "POST": "CREATE",
    "PUT": "UPDATE",
    "PATCH": "UPDATE",
    "DELETE": "DELETE"
}


class AuditMiddleware(BaseHTTPMiddleware):
    """审计中间件 - 自动记录所有写操作"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录审计日志"""
        # 检查是否需要审计
        if not self._should_audit(request):
            return await call_next(request)
        
        # 获取响应
        response = await call_next(request)
        
        # 如果是成功的写操作，记录审计日志
        if response.status_code < 400 and request.method in AUDIT_METHODS:
            try:
                await self._log_audit(request, response)
            except Exception as e:
                logger.error(f"审计日志记录失败: {e}")
        
        return response
    
    def _should_audit(self, request: Request) -> bool:
        """判断是否需要审计"""
        # 排除静态路径
        path = request.url.path
        for excluded in EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False
        
        # 只审计写操作
        if request.method not in AUDIT_METHODS:
            return False
        
        return True
    
    async def _log_audit(self, request: Request, response: Response):
        """记录审计日志"""
        # 获取用户 ID（从请求属性中获取）
        user_id = getattr(request.state, "user_id", None)
        if not user_id:
            # 如果无法获取用户 ID，跳过审计
            return
        
        # 解析资源类型和 ID
        resource_type, resource_id = self._parse_resource(request.url.path)
        
        # 获取操作类型
        action = ACTION_MAP.get(request.method, request.method)
        
        # 获取 IP 地址
        client_ip = self._get_client_ip(request)
        
        # 在独立的数据库会话中记录审计日志
        db = SessionLocal()
        try:
            audit_service.log_action(
                db=db,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=client_ip
            )
        finally:
            db.close()
    
    def _parse_resource(self, path: str) -> tuple:
        """解析资源类型和 ID"""
        parts = [p for p in path.split("/") if p]
        
        # 例如: ["api", "v1", "projects", "5"]
        # 返回: ("project", 5)
        
        if len(parts) < 3:
            return ("unknown", None)
        
        resource_type = parts[2] if len(parts) > 2 else "unknown"
        resource_id = None
        
        # 尝试解析 ID
        if len(parts) > 3:
            try:
                resource_id = int(parts[3])
            except ValueError:
                resource_id = None
        
        return (resource_type, resource_id)
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端 IP 地址"""
        # 支持代理转发
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # 直接获取
        if request.client:
            return request.client.host
        
        return "unknown"
