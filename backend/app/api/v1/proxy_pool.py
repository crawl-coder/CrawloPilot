"""
Phase 6: 代理池管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, ProxyProtocol, ProxyStatus
from app.schemas.proxy_api import (
    ProxyCreate,
    ProxyResponse,
    ProxyCheckResponse,
    ProxyStatsResponse
)
from app.services.proxy_pool import proxy_pool_service

router = APIRouter(prefix="/proxy-pool", tags=["代理池管理"])


@router.post("/proxies", response_model=ProxyResponse)
async def add_proxy(
    proxy_data: ProxyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """添加代理"""
    proxy = proxy_pool_service.add_proxy(db, proxy_data.model_dump())
    return proxy


@router.post("/proxies/batch")
async def batch_add_proxies(
    proxies_data: list[ProxyCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量添加代理"""
    count = proxy_pool_service.batch_add_proxies(db, [p.model_dump() for p in proxies_data])
    return {"message": f"成功添加 {count} 个代理"}


@router.get("/proxies", response_model=list[ProxyResponse])
async def get_proxies(
    status: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取代理列表"""
    proxies = proxy_pool_service.get_proxies(
        db=db,
        status=ProxyStatus(status) if status else None,
        protocol=ProxyProtocol(protocol) if protocol else None,
        group_name=group_name,
        min_score=min_score,
        skip=skip,
        limit=limit
    )
    return proxies


@router.post("/proxies/check", response_model=ProxyCheckResponse)
async def check_all_proxies(
    test_url: str = Query("https://www.baidu.com"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查所有代理健康状态"""
    result = proxy_pool_service.check_all_proxies(db, test_url)
    return result


@router.get("/proxies/available")
async def get_available_proxy(
    strategy: str = Query("round_robin"),
    protocol: Optional[str] = Query(None),
    group_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取可用代理"""
    proxy = proxy_pool_service.get_available_proxy(
        db=db,
        strategy=strategy,
        protocol=ProxyProtocol(protocol) if protocol else None,
        group_name=group_name
    )
    
    if not proxy:
        raise HTTPException(status_code=404, detail="没有可用的代理")
    
    return ProxyResponse.model_validate(proxy)


@router.get("/stats", response_model=ProxyStatsResponse)
async def get_proxy_stats(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取代理统计"""
    stats = proxy_pool_service.get_proxy_stats(db, days)
    return stats


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除代理"""
    from app.models import ProxyPool
    
    proxy = db.query(ProxyPool).filter(ProxyPool.id == proxy_id).first()
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
    
    db.delete(proxy)
    db.commit()
    return {"message": "代理删除成功"}
