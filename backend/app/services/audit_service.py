"""
操作审计服务（Wave E）

提供 record_audit() 供中间件和业务层调用，以及查询接口。
"""
import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.time_utils import cn_now
from app.models import AuditLog

logger = logging.getLogger(__name__)

# 路径→资源类型映射（RESTful 风格推断）
_RESOURCE_MAP = {
    "/projects": "project",
    "/spiders": "spider",
    "/schedules": "schedule",
    "/execution/tasks": "task",
    "/nodes": "node",
    "/users": "user",
    "/alerts/rules": "alert_rule",
    "/alerts/channels": "alert_channel",
    "/alerts/records": "alert_record",
    "/auth": "auth",
}

# HTTP 方法→动作映射
_ACTION_MAP = {
    "POST": "create",
    "PUT": "update",
    "PATCH": "update",
    "DELETE": "delete",
}

# 需要跳过审计的路径（健康检查、查询类、Agent 内部通信）
_SKIP_PATTERNS = [
    r"/health",
    r"/docs",
    r"/openapi",
    r"/api/v1/auth/login",  # 登录有专门的 login_log
    r"/api/v1/nodes/agent/",  # Agent 内部通信（心跳/领任务/上报，频率太高）
    r"/api/v1/execution/tasks/\d+/status$",  # 状态轮询
    r"/api/v1/execution/tasks/\d+/logs$",  # 日志查询
    r"/api/v1/execution/tasks/running$",
    r"/api/v1/execution/tasks/recent$",
    r"/api/v1/execution/tasks/stats",
    r"/api/v1/monitoring",
]


def _infer_resource(path: str) -> tuple:
    """从路径推断 resource_type 和 resource_id"""
    for prefix, rtype in _RESOURCE_MAP.items():
        if prefix in path:
            # 提取 ID：/projects/123 → 123
            m = re.search(rf"{re.escape(prefix)}/(\d+)", path)
            rid = m.group(1) if m else None
            return rtype, rid
    return None, None


def _infer_action(method: str, path: str) -> str:
    """从方法和路径推断动作"""
    # 特殊动作
    if "/run-now" in path:
        return "execute"
    if "/stop" in path:
        return "stop"
    if "/enable" in path:
        return "enable"
    if "/disable" in path:
        return "disable"
    if "/retry" in path:
        return "retry"
    if "/acknowledge" in path:
        return "acknowledge"
    if "/run" in path and "run-now" not in path:
        return "execute"
    if "/clone" in path:
        return "clone"
    if "/upload" in path:
        return "upload"
    if "/deploy" in path:
        return "deploy"
    return _ACTION_MAP.get(method, method.lower())


def _should_skip(path: str) -> bool:
    """是否跳过审计"""
    for pattern in _SKIP_PATTERNS:
        if re.search(pattern, path):
            return True
    return False


def record_audit(
    method: str,
    path: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    resource_name: Optional[str] = None,
    detail: Optional[str] = None,
):
    """记录一条审计日志（异步写入，不阻塞请求）"""
    if _should_skip(path):
        return

    # 推断资源类型（如未显式指定）
    if not resource_type:
        resource_type, rid = _infer_resource(path)
        if not resource_id and rid:
            resource_id = rid

    action = _infer_action(method, path)

    try:
        db = SessionLocal()
        try:
            log = AuditLog(
                user_id=user_id,
                username=username,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                resource_name=resource_name,
                method=method,
                path=path,
                ip=ip,
                user_agent=(user_agent or "")[:256],
                detail=detail,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"审计记录写入失败: {e}")
