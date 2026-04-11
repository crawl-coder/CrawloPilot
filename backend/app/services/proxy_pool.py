"""
Phase 6: 代理池管理服务
"""
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import random
import httpx

from app.models import ProxyPool, ProxyProtocol, ProxyStatus
from app.models.proxy_api import ProxyCheckLog, ProxyUsageLog


class ProxyPoolService:
    """代理池管理服务"""
    
    @staticmethod
    def add_proxy(db: Session, proxy_data: Dict) -> ProxyPool:
        """添加代理"""
        proxy = ProxyPool(**proxy_data)
        db.add(proxy)
        db.commit()
        db.refresh(proxy)
        return proxy
    
    @staticmethod
    def batch_add_proxies(db: Session, proxies_data: List[Dict]) -> int:
        """批量添加代理"""
        count = 0
        for proxy_data in proxies_data:
            proxy = ProxyPool(**proxy_data)
            db.add(proxy)
            count += 1
        db.commit()
        return count
    
    @staticmethod
    async def check_proxy_health(proxy: ProxyPool, test_url: str = "https://www.baidu.com") -> Dict:
        """检查代理健康状态"""
        proxy_url = f"{proxy.protocol.value.lower()}://{proxy.ip}:{proxy.port}"
        
        try:
            async with httpx.AsyncClient(
                proxy=proxy_url,
                timeout=10.0
            ) as client:
                start_time = datetime.utcnow()
                response = await client.get(test_url)
                response_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                is_available = response.status_code == 200
                return {
                    "is_available": is_available,
                    "response_time": response_time,
                    "status_code": response.status_code,
                    "error_message": None
                }
        except Exception as e:
            return {
                "is_available": False,
                "response_time": None,
                "status_code": None,
                "error_message": str(e)
            }
    
    @staticmethod
    def update_proxy_score(proxy: ProxyPool, check_result: Dict, db: Session):
        """更新代理评分"""
        old_score = proxy.health_score
        
        if check_result["is_available"]:
            # 成功：根据响应时间评分
            response_time = check_result["response_time"] or 10000
            if response_time < 500:
                score_increment = 5
            elif response_time < 1000:
                score_increment = 3
            elif response_time < 2000:
                score_increment = 1
            else:
                score_increment = -1
            
            proxy.health_score = min(100.00, proxy.health_score + score_increment)
            proxy.status = ProxyStatus.ACTIVE
        else:
            # 失败：降低评分
            score_decrement = 10
            proxy.health_score = max(0.00, proxy.health_score - score_decrement)
            
            if proxy.health_score < 30:
                proxy.status = ProxyStatus.BLOCKED
            elif proxy.health_score < 60:
                proxy.status = ProxyStatus.INACTIVE
        
        proxy.last_checked_at = datetime.utcnow()
        
        # 记录检查日志
        check_log = ProxyCheckLog(
            proxy_id=proxy.id,
            is_available=check_result["is_available"],
            response_time=check_result["response_time"],
            status_code=check_result["status_code"],
            error_message=check_result["error_message"],
            health_score_before=old_score,
            health_score_after=proxy.health_score
        )
        db.add(check_log)
        db.commit()
    
    @staticmethod
    def check_all_proxies(db: Session, test_url: str = "https://www.baidu.com") -> Dict:
        """检查所有代理健康状态"""
        import asyncio
        
        proxies = db.query(ProxyPool).filter(
            ProxyPool.status != ProxyStatus.BLOCKED
        ).all()
        
        async def check_proxies_async():
            tasks = []
            for proxy in proxies:
                task = ProxyPoolService.check_proxy_health(proxy, test_url)
                tasks.append((proxy, task))
            
            results = {"total": len(proxies), "checked": 0, "available": 0, "unavailable": 0}
            
            for proxy, task in tasks:
                check_result = await task
                ProxyPoolService.update_proxy_score(proxy, check_result, db)
                results["checked"] += 1
                if check_result["is_available"]:
                    results["available"] += 1
                else:
                    results["unavailable"] += 1
            
            return results
        
        return asyncio.run(check_proxies_async())
    
    @staticmethod
    def get_available_proxy(
        db: Session,
        strategy: str = "round_robin",
        protocol: Optional[ProxyProtocol] = None,
        group_name: Optional[str] = None
    ) -> Optional[ProxyPool]:
        """获取可用代理（支持多种策略）"""
        query = db.query(ProxyPool).filter(
            and_(
                ProxyPool.status == ProxyStatus.ACTIVE,
                ProxyPool.health_score >= 60
            )
        )
        
        if protocol:
            query = query.filter(ProxyPool.protocol == protocol)
        if group_name:
            query = query.filter(ProxyPool.group_name == group_name)
        
        proxies = query.order_by(ProxyPool.health_score.desc()).all()
        
        if not proxies:
            return None
        
        if strategy == "round_robin":
            # 轮询：选择评分最高的
            return proxies[0]
        elif strategy == "random":
            # 随机：从 Top 10 中随机选择
            top_proxies = proxies[:10]
            return random.choice(top_proxies)
        elif strategy == "weighted":
            # 权重：根据评分权重选择
            scores = [float(p.health_score) for p in proxies]
            total_score = sum(scores)
            if total_score == 0:
                return proxies[0]
            weights = [s / total_score for s in scores]
            return random.choices(proxies, weights=weights, k=1)[0]
        elif strategy == "sticky":
            # 粘性：返回评分最高且最近使用过的
            return proxies[0]
        
        return proxies[0]
    
    @staticmethod
    def get_proxies(
        db: Session,
        status: Optional[ProxyStatus] = None,
        protocol: Optional[ProxyProtocol] = None,
        group_name: Optional[str] = None,
        min_score: Optional[float] = None,
        skip: int = 0,
        limit: int = 50
    ) -> List[ProxyPool]:
        """获取代理列表"""
        query = db.query(ProxyPool)
        
        if status:
            query = query.filter(ProxyPool.status == status)
        if protocol:
            query = query.filter(ProxyPool.protocol == protocol)
        if group_name:
            query = query.filter(ProxyPool.group_name == group_name)
        if min_score is not None:
            query = query.filter(ProxyPool.health_score >= min_score)
        
        query = query.order_by(ProxyPool.health_score.desc(), ProxyPool.created_at.desc())
        return query.offset(skip).limit(limit).all()
    
    @staticmethod
    def get_proxy_stats(db: Session, days: int = 30) -> Dict:
        """获取代理统计"""
        total = db.query(ProxyPool).count()
        active = db.query(ProxyPool).filter(ProxyPool.status == ProxyStatus.ACTIVE).count()
        inactive = db.query(ProxyPool).filter(ProxyPool.status == ProxyStatus.INACTIVE).count()
        blocked = db.query(ProxyPool).filter(ProxyPool.status == ProxyStatus.BLOCKED).count()
        
        avg_score = db.query(func.avg(ProxyPool.health_score)).scalar() or 0
        
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
            "blocked": blocked,
            "average_score": round(float(avg_score), 2)
        }


class ProxyUsageService:
    """代理使用统计服务"""
    
    @staticmethod
    def log_usage(
        db: Session,
        proxy_id: int,
        project_id: int,
        task_instance_id: int,
        success: bool,
        response_time: int
    ):
        """记录代理使用"""
        now = datetime.utcnow()
        window_start = now.replace(minute=0, second=0, microsecond=0)  # 按小时统计
        
        # 查找或创建使用记录
        usage = db.query(ProxyUsageLog).filter(
            and_(
                ProxyUsageLog.proxy_id == proxy_id,
                ProxyUsageLog.project_id == project_id,
                ProxyUsageLog.start_time == window_start
            )
        ).first()
        
        if not usage:
            usage = ProxyUsageLog(
                proxy_id=proxy_id,
                project_id=project_id,
                task_instance_id=task_instance_id,
                start_time=window_start,
                end_time=window_start + timedelta(hours=1)
            )
            db.add(usage)
            db.flush()
        
        usage.request_count += 1
        if success:
            usage.success_count += 1
        else:
            usage.failed_count += 1
        usage.total_response_time += response_time
        
        db.commit()
    
    @staticmethod
    def get_usage_stats(
        db: Session,
        proxy_id: Optional[int] = None,
        project_id: Optional[int] = None,
        days: int = 7
    ) -> Dict:
        """获取使用统计"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.query(ProxyUsageLog).filter(ProxyUsageLog.start_time >= start_date)
        if proxy_id:
            query = query.filter(ProxyUsageLog.proxy_id == proxy_id)
        if project_id:
            query = query.filter(ProxyUsageLog.project_id == project_id)
        
        total_requests = db.query(func.sum(ProxyUsageLog.request_count)).filter(
            ProxyUsageLog.start_time >= start_date
        )
        if proxy_id:
            total_requests = total_requests.filter(ProxyUsageLog.proxy_id == proxy_id)
        if project_id:
            total_requests = total_requests.filter(ProxyUsageLog.project_id == project_id)
        
        return {
            "total_requests": total_requests.scalar() or 0,
            "period_days": days
        }


proxy_pool_service = ProxyPoolService()
proxy_usage_service = ProxyUsageService()
