"""
Phase 7: 操作审计服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.models import AuditLog


class AuditService:
    """操作审计服务"""
    
    @staticmethod
    def log_action(
        db: Session,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[int] = None,
        old_value: Optional[Dict] = None,
        new_value: Optional[Dict] = None,
        ip_address: Optional[str] = None
    ) -> AuditLog:
        """记录操作日志"""
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log
    
    @staticmethod
    def get_audit_logs(
        db: Session,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[AuditLog]:
        """获取审计日志"""
        query = db.query(AuditLog)
        
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        if action:
            query = query.filter(AuditLog.action == action)
        if resource_type:
            query = query.filter(AuditLog.resource_type == resource_type)
        if start_date:
            query = query.filter(AuditLog.created_at >= start_date)
        if end_date:
            query = query.filter(AuditLog.created_at <= end_date)
        
        query = query.order_by(AuditLog.created_at.desc())
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_audit_stats(
        db: Session,
        days: int = 30
    ) -> Dict:
        """获取审计统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        total = db.query(AuditLog).filter(AuditLog.created_at >= start_date).count()
        
        # 按操作类型统计
        action_stats = db.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= start_date
        ).group_by(AuditLog.action).all()
        
        # 按资源类型统计
        resource_stats = db.query(
            AuditLog.resource_type,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= start_date
        ).group_by(AuditLog.resource_type).all()
        
        # 按用户统计
        user_stats = db.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.created_at >= start_date
        ).group_by(AuditLog.user_id).all()
        
        return {
            'total': total,
            'action_stats': [{'action': s.action, 'count': s.count} for s in action_stats],
            'resource_stats': [{'resource_type': s.resource_type, 'count': s.count} for s in resource_stats],
            'user_stats': [{'user_id': s.user_id, 'count': s.count} for s in user_stats],
            'period_days': days
        }
    
    @staticmethod
    def get_user_activity(
        db: Session,
        user_id: int,
        days: int = 30
    ) -> Dict:
        """获取用户活动统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        total_actions = db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= start_date
            )
        ).count()
        
        # 按天统计
        daily_stats = db.query(
            func.date(AuditLog.created_at).label('date'),
            func.count(AuditLog.id).label('count')
        ).filter(
            and_(
                AuditLog.user_id == user_id,
                AuditLog.created_at >= start_date
            )
        ).group_by(func.date(AuditLog.created_at)).all()
        
        return {
            'user_id': user_id,
            'total_actions': total_actions,
            'daily_stats': [{'date': str(s.date), 'count': s.count} for s in daily_stats],
            'period_days': days
        }


audit_service = AuditService()
