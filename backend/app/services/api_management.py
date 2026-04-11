"""
Phase 6: API 管理服务（限流、熔断、统计）
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.models import ApiConfig
from app.models.proxy_api import ApiCallLog, ApiRateLimit


class ApiService:
    """API 管理服务"""
    
    @staticmethod
    def create_api_config(db: Session, api_data: Dict) -> ApiConfig:
        """创建 API 配置"""
        api_config = ApiConfig(**api_data)
        db.add(api_config)
        db.commit()
        db.refresh(api_config)
        return api_config
    
    @staticmethod
    def check_rate_limit(db: Session, api_config_id: int, limit_count: int, window_minutes: int = 1) -> bool:
        """检查限流（返回 True 表示被限流）"""
        now = datetime.utcnow()
        window_start = now - timedelta(minutes=window_minutes)
        window_end = now + timedelta(minutes=1)
        
        # 查找当前窗口的限流记录
        rate_limit = db.query(ApiRateLimit).filter(
            and_(
                ApiRateLimit.api_config_id == api_config_id,
                ApiRateLimit.window_start >= window_start,
                ApiRateLimit.window_end <= window_end
            )
        ).first()
        
        if not rate_limit:
            # 创建新的限流窗口
            rate_limit = ApiRateLimit(
                api_config_id=api_config_id,
                window_start=now,
                window_end=now + timedelta(minutes=window_minutes),
                limit_count=limit_count
            )
            db.add(rate_limit)
            db.commit()
            return False
        
        # 检查是否超过限制
        if rate_limit.request_count >= limit_count:
            rate_limit.is_limited = True
            db.commit()
            return True
        
        # 增加计数
        rate_limit.request_count += 1
        db.commit()
        return False
    
    @staticmethod
    def check_circuit_breaker(db: Session, api_config_id: int, threshold: int = 10) -> bool:
        """检查熔断器（返回 True 表示熔断器打开）"""
        # 查找最近的连续失败次数
        recent_logs = db.query(ApiCallLog).filter(
            and_(
                ApiCallLog.api_config_id == api_config_id,
                ApiCallLog.called_at >= datetime.utcnow() - timedelta(minutes=5)
            )
        ).order_by(ApiCallLog.called_at.desc()).limit(threshold).all()
        
        if len(recent_logs) < threshold:
            return False
        
        # 检查是否全部失败
        consecutive_failures = 0
        for log in recent_logs:
            if not log.is_success:
                consecutive_failures += 1
            else:
                break
        
        return consecutive_failures >= threshold
    
    @staticmethod
    def log_api_call(
        db: Session,
        api_config_id: int,
        project_id: int,
        task_instance_id: Optional[int],
        endpoint: str,
        method: str,
        status_code: int,
        response_time: int,
        is_success: bool,
        error_message: Optional[str] = None
    ) -> ApiCallLog:
        """记录 API 调用"""
        # 检查熔断器状态
        api_config = db.query(ApiConfig).filter(ApiConfig.id == api_config_id).first()
        circuit_breaker_open = False
        
        if api_config:
            recent_failures = db.query(func.count(ApiCallLog.id)).filter(
                and_(
                    ApiCallLog.api_config_id == api_config_id,
                    ApiCallLog.is_success == False,
                    ApiCallLog.called_at >= datetime.utcnow() - timedelta(minutes=5)
                )
            ).scalar() or 0
            
            circuit_breaker_open = recent_failures >= api_config.circuit_breaker_threshold
        
        call_log = ApiCallLog(
            api_config_id=api_config_id,
            project_id=project_id,
            task_instance_id=task_instance_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time=response_time,
            is_success=is_success,
            error_message=error_message,
            circuit_breaker_open=circuit_breaker_open,
            consecutive_failures=0
        )
        
        db.add(call_log)
        db.commit()
        db.refresh(call_log)
        return call_log
    
    @staticmethod
    def get_api_configs(
        db: Session,
        project_id: Optional[int] = None,
        enabled: Optional[bool] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ApiConfig]:
        """获取 API 配置列表"""
        query = db.query(ApiConfig)
        
        if project_id:
            query = query.filter(ApiConfig.project_id == project_id)
        if enabled is not None:
            query = query.filter(ApiConfig.enabled == enabled)
        
        query = query.order_by(ApiConfig.created_at.desc())
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_api_stats(
        db: Session,
        api_config_id: Optional[int] = None,
        project_id: Optional[int] = None,
        days: int = 30
    ) -> Dict:
        """获取 API 统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(ApiCallLog).filter(ApiCallLog.called_at >= start_date)
        if api_config_id:
            query = query.filter(ApiCallLog.api_config_id == api_config_id)
        if project_id:
            query = query.filter(ApiCallLog.project_id == project_id)
        
        total_calls = query.count()
        success_calls = query.filter(ApiCallLog.is_success == True).count()
        failed_calls = query.filter(ApiCallLog.is_success == False).count()
        
        avg_response_time = db.query(func.avg(ApiCallLog.response_time)).filter(
            ApiCallLog.called_at >= start_date
        )
        if api_config_id:
            avg_response_time = avg_response_time.filter(ApiCallLog.api_config_id == api_config_id)
        if project_id:
            avg_response_time = avg_response_time.filter(ApiCallLog.project_id == project_id)
        
        avg_response_time = avg_response_time.scalar() or 0
        
        # 获取熔断器状态
        circuit_breaker_trips = db.query(func.count(ApiCallLog.id)).filter(
            and_(
                ApiCallLog.called_at >= start_date,
                ApiCallLog.circuit_breaker_open == True
            )
        )
        if api_config_id:
            circuit_breaker_trips = circuit_breaker_trips.filter(ApiCallLog.api_config_id == api_config_id)
        
        return {
            "total_calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "success_rate": round((success_calls / total_calls * 100) if total_calls > 0 else 0, 2),
            "average_response_time": round(float(avg_response_time), 2),
            "circuit_breaker_trips": circuit_breaker_trips.scalar() or 0,
            "period_days": days
        }
    
    @staticmethod
    def get_api_trend(
        db: Session,
        api_config_id: Optional[int] = None,
        project_id: Optional[int] = None,
        days: int = 30
    ) -> List[Dict]:
        """获取 API 调用趋势"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(
            func.date(ApiCallLog.called_at).label('date'),
            func.count(ApiCallLog.id).label('total_calls'),
            func.sum(func.cast(ApiCallLog.is_success, db.query(ApiCallLog).statement.with_only_columns([1]).label('success_calls'))).label('success_calls'),
            func.avg(ApiCallLog.response_time).label('avg_response_time')
        ).filter(
            ApiCallLog.called_at >= start_date
        )
        
        if api_config_id:
            query = query.filter(ApiCallLog.api_config_id == api_config_id)
        if project_id:
            query = query.filter(ApiCallLog.project_id == project_id)
        
        results = query.group_by(func.date(ApiCallLog.called_at)).order_by(func.date(ApiCallLog.called_at)).all()
        
        return [
            {
                "date": str(row.date),
                "total_calls": row.total_calls,
                "success_calls": row.success_calls or 0,
                "avg_response_time": round(float(row.avg_response_time or 0), 2)
            }
            for row in results
        ]


api_service = ApiService()
