"""
Phase 7: 操作审计 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.services.audit import audit_service

router = APIRouter(prefix="/audit", tags=["操作审计"])


@router.get("/logs")
async def get_audit_logs(
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取审计日志"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    logs = audit_service.get_audit_logs(
        db=db,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        start_date=start_date,
        skip=skip,
        limit=limit
    )
    
    return [
        {
            'id': log.id,
            'user_id': log.user_id,
            'username': log.user.username if log.user else None,
            'action': log.action,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'old_value': log.old_value,
            'new_value': log.new_value,
            'ip_address': log.ip_address,
            'created_at': log.created_at
        }
        for log in logs
    ]


@router.get("/stats")
async def get_audit_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取审计统计"""
    stats = audit_service.get_audit_stats(db, days)
    return stats


@router.get("/user/{user_id}/activity")
async def get_user_activity(
    user_id: int,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取用户活动统计"""
    activity = audit_service.get_user_activity(db, user_id, days)
    return activity
