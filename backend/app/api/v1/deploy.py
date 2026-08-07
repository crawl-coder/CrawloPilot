"""
部署管理 API 路由
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from pydantic import BaseModel

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models import User, Deploy, DeployStatus, DeployStrategy
from app.services.deploy_service import DeployService

router = APIRouter(prefix="/deploys", tags=["部署管理"])


def _run_deploy_execute(deploy_id: int):
    """后台执行部署（独立 DB 会话，供 BackgroundTasks 调用）"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        DeployService(db).execute_deploy_sync(deploy_id)
    finally:
        db.close()


def _run_deploy_rollback(deploy_id: int):
    """后台回滚部署（独立 DB 会话，供 BackgroundTasks 调用）"""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        DeployService(db).rollback_deploy_sync(deploy_id)
    finally:
        db.close()


# ==================== Pydantic Schemas ====================

class DeployCreate(BaseModel):
    """创建部署请求"""
    project_id: int
    version_id: int
    strategy: DeployStrategy = DeployStrategy.RECREATE
    node_id: int
    target_env: str = "production"


class DeployResponse(BaseModel):
    """部署响应"""
    id: int
    project_id: int
    version_id: int
    strategy: DeployStrategy
    status: DeployStatus
    target_env: str
    node_id: Optional[int]
    container_ids: Optional[list]
    error_message: Optional[str]
    deployed_by: Optional[int]
    started_at: Optional[Any]
    finished_at: Optional[Any]
    created_at: Any
    
    class Config:
        from_attributes = True


# ==================== API Endpoints ====================

@router.post("", response_model=DeployResponse)
async def create_deploy(
    deploy_data: DeployCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建部署任务
    
    - **project_id**: 项目 ID
    - **version_id**: 版本 ID
    - **strategy**: 部署策略（blue_green/rolling/recreate）
    - **node_id**: 目标节点 ID
    - **target_env**: 目标环境（production/staging）
    """
    try:
        deploy_service = DeployService(db)
        
        # 创建部署记录
        deploy = await deploy_service.create_deploy(
            project_id=deploy_data.project_id,
            version_id=deploy_data.version_id,
            strategy=deploy_data.strategy,
            node_id=deploy_data.node_id,
            target_env=deploy_data.target_env,
            deployed_by=current_user.id
        )
        
        # 异步执行部署
        background_tasks.add_task(_run_deploy_execute, deploy.id)
        
        return deploy
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建部署失败: {str(e)}")


@router.get("")
async def list_deploys(
    project_id: Optional[int] = None,
    status: Optional[DeployStatus] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取部署列表(带分页)"""
    try:
        from app.core.pagination import clamp_pagination
        offset, limit = clamp_pagination(offset, limit, default_limit=50)
        deploy_service = DeployService(db)
        deploys = deploy_service.get_deploys(
            project_id=project_id,
            status=status,
            limit=limit,
            offset=offset
        )
        total = deploy_service.get_deploy_count(project_id=project_id, status=status)
        return {"total": total, "items": deploys, "skip": offset, "limit": limit}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取部署列表失败: {str(e)}")


@router.get("/{deploy_id}", response_model=DeployResponse)
async def get_deploy(
    deploy_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取部署详情"""
    try:
        deploy_service = DeployService(db)
        deploy = deploy_service.get_deploy(deploy_id)
        
        if not deploy:
            raise HTTPException(status_code=404, detail="部署记录不存在")
        
        return deploy
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取部署详情失败: {str(e)}")


@router.post("/{deploy_id}/rollback")
async def rollback_deploy(
    deploy_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    回滚部署
    
    - **deploy_id**: 部署 ID
    """
    try:
        deploy_service = DeployService(db)
        deploy = deploy_service.get_deploy(deploy_id)
        
        if not deploy:
            raise HTTPException(status_code=404, detail="部署记录不存在")
        
        if deploy.status == DeployStatus.SUCCESS:
            # 异步回滚
            background_tasks.add_task(_run_deploy_rollback, deploy_id)
            
            return {"message": "回滚任务已提交", "deploy_id": deploy_id}
        else:
            raise HTTPException(status_code=400, detail="只能回滚成功的部署")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"回滚部署失败: {str(e)}")


@router.post("/{deploy_id}/retry")
async def retry_deploy(
    deploy_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    重试部署
    
    - **deploy_id**: 部署 ID
    """
    try:
        deploy_service = DeployService(db)
        deploy = deploy_service.get_deploy(deploy_id)
        
        if not deploy:
            raise HTTPException(status_code=404, detail="部署记录不存在")
        
        if deploy.status == DeployStatus.FAILED:
            # 异步重试（重新执行一次部署）
            background_tasks.add_task(_run_deploy_execute, deploy_id)
            
            return {"message": "重试任务已提交", "deploy_id": deploy_id}
        else:
            raise HTTPException(status_code=400, detail="只能重试失败的部署")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"重试部署失败: {str(e)}")
