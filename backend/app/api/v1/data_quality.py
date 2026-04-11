"""
Phase 5: 数据质量 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.data_quality import (
    DataQualityCheckCreate,
    DataQualityCheckResponse,
    DataQualityRuleCreate,
    DataQualityRuleResponse,
    DataStatisticsResponse,
    QualityStatsResponse,
    SummaryStatsResponse
)
from app.services.data_quality import data_quality_service, data_statistics_service

router = APIRouter(prefix="/data-quality", tags=["数据质量"])


# ==================== 数据质量检测 ====================

@router.post("/checks", response_model=DataQualityCheckResponse)
async def create_quality_check(
    data: DataQualityCheckCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建数据质量检测记录"""
    quality_data = data_quality_service.evaluate_quality(**data.quality_data)
    check = data_quality_service.create_quality_check(
        db=db,
        task_instance_id=data.task_instance_id,
        project_id=data.project_id,
        spider_name=data.spider_name,
        quality_data=quality_data
    )
    return check


@router.get("/checks", response_model=list[DataQualityCheckResponse])
async def get_quality_checks(
    project_id: Optional[int] = Query(None),
    spider_name: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    days: int = Query(30, ge=1, le=365),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取数据质量检测记录"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    checks = data_quality_service.get_quality_checks(
        db=db,
        project_id=project_id,
        spider_name=spider_name,
        status=status,
        start_date=start_date,
        skip=skip,
        limit=limit
    )
    return checks


@router.get("/checks/stats", response_model=QualityStatsResponse)
async def get_quality_stats(
    project_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取数据质量统计"""
    stats = data_quality_service.get_quality_stats(
        db=db,
        project_id=project_id,
        days=days
    )
    return stats


# ==================== 数据质量规则 ====================

@router.post("/rules", response_model=DataQualityRuleResponse)
async def create_quality_rule(
    rule_data: DataQualityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建数据质量检测规则"""
    from app.models.data_quality import DataQualityRule
    
    rule = DataQualityRule(**rule_data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/rules", response_model=list[DataQualityRuleResponse])
async def get_quality_rules(
    project_id: Optional[int] = Query(None),
    spider_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取数据质量检测规则"""
    from app.models.data_quality import DataQualityRule
    
    query = db.query(DataQualityRule)
    if project_id:
        query = query.filter(DataQualityRule.project_id == project_id)
    if spider_name:
        query = query.filter(DataQualityRule.spider_name == spider_name)
    
    return query.order_by(DataQualityRule.created_at.desc()).all()


@router.put("/rules/{rule_id}", response_model=DataQualityRuleResponse)
async def update_quality_rule(
    rule_id: int,
    rule_data: DataQualityRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新数据质量检测规则"""
    from app.models.data_quality import DataQualityRule
    
    rule = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    for key, value in rule_data.model_dump().items():
        setattr(rule, key, value)
    
    db.commit()
    db.refresh(rule)
    return rule


@router.delete("/rules/{rule_id}")
async def delete_quality_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除数据质量检测规则"""
    from app.models.data_quality import DataQualityRule
    
    rule = db.query(DataQualityRule).filter(DataQualityRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    
    db.delete(rule)
    db.commit()
    return {"message": "规则删除成功"}


# ==================== 数据统计 ====================

@router.get("/statistics/project", response_model=list[DataStatisticsResponse])
async def get_project_statistics(
    project_id: int = Query(...),
    stat_type: str = Query("daily", regex="^(hourly|daily|weekly|monthly)$"),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目统计数据"""
    stats = data_statistics_service.get_project_statistics(
        db=db,
        project_id=project_id,
        stat_type=stat_type,
        days=days
    )
    return stats


@router.get("/statistics/spider", response_model=list[DataStatisticsResponse])
async def get_spider_statistics(
    project_id: int = Query(...),
    spider_name: str = Query(...),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取爬虫统计数据"""
    stats = data_statistics_service.get_spider_statistics(
        db=db,
        project_id=project_id,
        spider_name=spider_name,
        days=days
    )
    return stats


@router.get("/statistics/summary", response_model=SummaryStatsResponse)
async def get_summary_statistics(
    project_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取汇总统计"""
    stats = data_statistics_service.get_summary_statistics(
        db=db,
        project_id=project_id,
        days=days
    )
    return stats


@router.post("/statistics/record", response_model=DataStatisticsResponse)
async def record_statistics(
    project_id: int,
    spider_name: str,
    task_instance_id: int,
    stats_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """记录统计数据"""
    stat = data_statistics_service.record_statistics(
        db=db,
        project_id=project_id,
        spider_name=spider_name,
        task_instance_id=task_instance_id,
        stats_data=stats_data
    )
    return stat
