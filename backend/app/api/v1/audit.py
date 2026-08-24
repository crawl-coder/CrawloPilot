"""
操作审计 API（Wave E）

查询审计记录（分页、按用户/资源/时间筛选）。
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.pagination import clamp_pagination
from app.models import User, AuditLog

router = APIRouter(prefix="/audit", tags=["操作审计"])


@router.get("/logs")
async def list_audit_logs(
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """审计日志列表（可按用户/资源/操作类型筛选）"""
    skip, limit = clamp_pagination(skip, limit, default_limit=50)
    q = db.query(AuditLog)
    if user_id:
        q = q.filter(AuditLog.user_id == user_id)
    if username:
        q = q.filter(AuditLog.username.ilike(f"%{username}%"))
    if action:
        q = q.filter(AuditLog.action == action)
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.filter(AuditLog.resource_id == str(resource_id))
    return [
        {
            "id": r.id,
            "user_id": r.user_id,
            "username": r.username,
            "action": r.action,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "resource_name": r.resource_name,
            "method": r.method,
            "path": r.path,
            "ip": r.ip,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in q.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit).all()
    ]
