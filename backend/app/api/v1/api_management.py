"""
Phase 6: API 管理路由
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, ApiConfig
from app.schemas.proxy_api import (
    ApiConfigCreate,
    ApiConfigResponse,
    ApiStatsResponse,
    ApiTrendResponse
)
from app.services.api_management import api_service

router = APIRouter(prefix="/api-management", tags=["API管理"])


@router.post("/configs", response_model=ApiConfigResponse)
async def create_api_config(
    api_data: ApiConfigCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建 API 配置"""
    config = api_service.create_api_config(db, api_data.model_dump())
    return config


@router.get("/configs", response_model=list[ApiConfigResponse])
async def get_api_configs(
    project_id: Optional[int] = Query(None),
    enabled: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 API 配置列表"""
    configs = api_service.get_api_configs(db, project_id, enabled, skip, limit)
    return configs


@router.get("/configs/{config_id}", response_model=ApiConfigResponse)
async def get_api_config(
    config_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 API 配置详情"""
    config = db.query(ApiConfig).filter(ApiConfig.id == config_id).first()
    if not config:
        raise HTTPException(status_code=404, detail="API 配置不存在")
    return config


@router.get("/stats", response_model=ApiStatsResponse)
async def get_api_stats(
    api_config_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 API 统计"""
    stats = api_service.get_api_stats(db, api_config_id, project_id, days)
    return stats


@router.get("/trend", response_model=list[ApiTrendResponse])
async def get_api_trend(
    api_config_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取 API 调用趋势"""
    trend = api_service.get_api_trend(db, api_config_id, project_id, days)
    return trend
